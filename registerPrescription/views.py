import os
import time
import uuid
import requests
import logging
import base64
import json
import pandas as pd
import openai  # GPT API 호출용
from openai import ChatCompletion  # 새 인터페이스 사용
from django.db import transaction
from children.models import Children
from .models import Prescription, Medicine

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from django.db.models import F
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import connection
from dotenv import load_dotenv
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()

CLOVA_OCR_SECRET = os.getenv("CLOVA_OCR_SECRET")

# OpenAI API 키 (환경 변수 또는 직접 입력)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


# APIGW에서 제공하는 실제 Invoke URL (NCP 콘솔에서 확인한 URL로 교체)
OCR_API_URL = "https://3ja254nf6l.apigw.ntruss.com/custom/v1/38065/f6e2a7f6d39340c1a967762f8265e55ed0cf9e441f30ee185ba6a26df73d34db/general"


class ClovaOCRAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # multipart/form-data 요청을 처리

    def post(self, request):
        try:
            if 'image' not in request.FILES:
                return Response({
                    "success": False,
                    "error": "이미지 파일이 필요합니다."
                }, status=status.HTTP_400_BAD_REQUEST)

            image_file = request.FILES['image']
            
            # OCR API 요청 데이터 구성
            request_json = {
                "version": "V2",
                "requestId": str(uuid.uuid4()),
                "timestamp": int(round(time.time() * 1000)),
                "lang": "ko",
                "images": [
                    {
                        "format": "jpg",
                        "name": "ocr_image"
                    }
                ]
            }

            # 멀티파트 폼 데이터 구성
            files = {
                'message': (None, json.dumps(request_json), 'application/json'),
                'file': (image_file.name, image_file, image_file.content_type or "image/jpeg")
            }

            headers = {
                "X-OCR-SECRET": CLOVA_OCR_SECRET
            }

            # OCR API 호출
            response = requests.post(OCR_API_URL, headers=headers, files=files)
            
            if response.status_code != 200:
                return Response({
                    "success": False,
                    "error": f"OCR API 오류: {response.text}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # OCR 결과 처리
            ocr_result = response.json()
            
            # fields에서 텍스트 추출
            extracted_text = [
                field["inferText"] 
                for field in ocr_result["images"][0]["fields"] 
                if "inferText" in field
            ]

            # GPT 처리를 위한 테이블 생성
            table_df = pd.DataFrame([" ".join(extracted_text)])
            
            # 나머지 처리 계속...
            final_result = self.process_extracted_table(table_df, request.data.get('child_name'))
            
            return self._save_prescription_data(request, final_result)

        except Exception as e:
            logger.exception("Error in prescription processing")
            return Response({
                'error': f'처방전 처리 중 오류가 발생했습니다: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def extract_table_from_ocr(self, ocr_result):
        """
        OCR 결과의 table 영역을 판다스 DataFrame으로 변환.
        """
        table_data = []

        for image in ocr_result.get("images", []):
            for table in image.get("tables", []):
                row_dict = {}  # {row_y: [(x, text)]}

                for cell in table.get("cells", []):
                    cell_text_lines = cell.get("cellTextLines", [])
                    if not cell_text_lines:
                        continue
                    cell_line = cell_text_lines[0]
                    cell_words = cell_line.get("cellWords", [])
                    if not cell_words:
                        continue

                    cell_text = " ".join([word.get("inferText", "").strip() for word in cell_words])
                    vertices = cell_line.get("boundingPoly", {}).get("vertices", [])
                    if not vertices:
                        continue

                    min_x = min(v.get("x", 0) for v in vertices)
                    min_y = min(v.get("y", 0) for v in vertices)

                    matched_row = None
                    for row_y in row_dict.keys():
                        if abs(row_y - min_y) < 20:
                            matched_row = row_y
                            break

                    if matched_row is None:
                        matched_row = min_y
                        row_dict[matched_row] = []

                    row_dict[matched_row].append((min_x, cell_text))

                sorted_rows = []
                for row_y in sorted(row_dict.keys()):
                    sorted_row = sorted(row_dict[row_y], key=lambda x: x[0])
                    sorted_rows.append([text for _, text in sorted_row])

                table_data.extend(sorted_rows)

        df = pd.DataFrame(table_data)
        return df

    def process_extracted_table(self, table_df, child_name):
        try:
            unique_id = str(uuid.uuid4())[:8]
            prescription_number = f"RX-{unique_id}"
            current_date = datetime.now().strftime('%Y-%m-%d')

            # 테이블 데이터를 문자열로 변환
            table_text = ""
            for _, row in table_df.iterrows():
                row_text = " ".join([str(val) for val in row.values if pd.notna(val)])
                if row_text.strip():
                    table_text += row_text + "\n"

            prompt = f"""
                다음은 처방전에서 OCR로 추출한 텍스트입니다:
                {table_text}

                위 텍스트에서 다음 정보를 추출하여 JSON 형식으로 반환해주세요:
                1. 약국명 (상호 다음에 나오는 이름)
                2. 처방전번호: "{prescription_number}"
                3. 조제일자: 조제일자 또는 발행일 다음에 나오는 날짜
                4. 약국주소: 사업장소재지 다음에 나오는 주소
                5. 총수납금액: 합계 다음에 나오는 금액 (숫자만)
                6. 투약일수: 투약일수 다음에 나오는 숫자
                7. 약품목록: 약품명, 투약량, 투약횟수, 투약일수가 있는 행들

                출력은 반드시 아래 JSON 형식으로 해주세요
                JSON 형식을 제외한 어느 말도 하지 마세요:
                
                
                {{
                    "약국명": "찾은 약국명",
                    "처방전번호": "{prescription_number}",
                    "조제일자": "찾은 날짜",
                    "약국주소": "찾은 주소",
                    "총수납금액": "찾은 금액",
                    "투약일수": "찾은 투약일수",
                    "약품목록": [
                        {{
                            "약품명": "약품명",
                            "투약량": "투약량",
                            "투약횟수": "횟수",
                            "투약일수": "일수"
                        }}
                    ]
                }}
                """
            # OpenAI GPT 호출
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # gpt-4o -> gpt-4로 수정
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            
            gpt_response = response.choices[0].message.content.strip()
            
            # ```json과 같은 마크다운 태그 제거
            if gpt_response.startswith('```'):
                gpt_response = gpt_response.split('\n', 1)[1]  # 첫 줄 제거
            if gpt_response.endswith('```'):
                gpt_response = gpt_response.rsplit('\n', 1)[0]  # 마지막 줄 제거
            
            try:
                result = json.loads(gpt_response)
                logger.info(f"파싱된 결과: {result}")  # 로깅 추가
                return result
            except json.JSONDecodeError as e:
                logger.error(f"GPT 응답 JSON 파싱 오류: {e}\n응답 내용: {gpt_response}")
                # 기본 응답 생성
                result = {
                    "약국명": "",
                    "처방전번호": prescription_number,
                    "조제일자": current_date,
                    "약국주소": "",
                    "총수납금액": "0",
                    "투약일수": "0",
                    "약품목록": []
                }
                return result

        except Exception as e:
            logger.error(f"데이터 처리 중 오류 발생: {str(e)}")
            raise

    @transaction.atomic
    def _save_prescription_data(self, request, final_result):
        try:
            # 자녀 정보 조회 또는 생성
            child, created = Children.objects.get_or_create(
                user=request.user,
                child_name=request.data.get('child_name'),
                defaults={'user': request.user}
            )

            # Prescription 저장
            prescription = Prescription.objects.create(
                child=child,
                pharmacy_name=final_result.get('약국명', ''),
                prescription_number=final_result.get('처방전번호'),
                prescription_date=final_result.get('조제일자'),
                pharmacy_address=final_result.get('약국주소', ''),
                total_amount=final_result.get('총수납금액', '0'),
                duration=final_result.get('투약일수', '0')
            )

            # Medicine 테이블에 약품 목록 저장
            medicines = final_result.get('약품목록', [])
            for med in medicines:
                Medicine.objects.create(
                    prescription=prescription,
                    name=med.get('약품명', ''),
                    dosage=med.get('투약량', 1),
                    frequency=med.get('투약횟수', 1),
                    duration=med.get('투약일수', 1)
                )

            return Response({
                "success": True,
                "data": {
                    "prescription_id": prescription.prescription_id,
                    "pharmacy_info": {
                        "name": prescription.pharmacy_name,
                        "address": prescription.pharmacy_address
                    },
                    "prescription_number": prescription.prescription_number,
                    "prescription_date": prescription.prescription_date,
                    "total_amount": prescription.total_amount,
                    "duration": prescription.duration,
                    "medicines": [
                        {
                            "medicine_name": med.name,
                            "dosage": med.dosage,
                            "frequency": med.frequency,
                            "duration": med.duration,
                            "total_count": med.frequency * med.duration
                        } for med in prescription.medicines.all()
                    ],
                    "child_name": child.child_name,
                    "created_at": prescription.created_at
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("처방전 저장 중 오류 발생")
            return Response({
                "success": False,
                "error": f"처방전 저장 중 오류가 발생했습니다: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PrescriptionListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            prescriptions = (
                Prescription.objects.filter(child__user=request.user)
                .select_related("child")
                .order_by("-created_at")
            )

            prescription_list = []
            for prescription in prescriptions:
                # 투약 종료일 계산
                start_date = prescription.prescription_date
                duration_days = int(prescription.duration or 0)
                end_date = start_date + timedelta(days=duration_days) if start_date else None

                prescription_data = {
                    "prescription_id": prescription.prescription_id,
                    "child_name": prescription.child.child_name,
                    "pharmacy_name": prescription.pharmacy_name,
                    "prescription_number": prescription.prescription_number,
                    "prescription_date": prescription.prescription_date,
                    "pharmacy_address": prescription.pharmacy_address,
                    "total_amount": prescription.total_amount,
                    "duration": prescription.duration,  # 투약일수 추가
                    "end_date": end_date,  # 투약 종료일 추가
                    "created_at": prescription.created_at,
                }
                prescription_list.append(prescription_data)

            return Response(
                {"count": len(prescription_list), "results": prescription_list},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"처방전 조회 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PrescriptionListByDateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            prescriptions = (
                Prescription.objects.filter(child__user=request.user)
                .select_related("child")
                .order_by("-prescription_date")
            )

            prescription_list = []
            for prescription in prescriptions:
                # 투약 종료일 계산
                start_date = prescription.prescription_date
                duration_days = int(prescription.duration or 0)
                end_date = start_date + timedelta(days=duration_days) if start_date else None

                prescription_data = {
                    "prescription_id": prescription.prescription_id,
                    "child_name": prescription.child.child_name,
                    "pharmacy_name": prescription.pharmacy_name,
                    "prescription_number": prescription.prescription_number,
                    "prescription_date": prescription.prescription_date,
                    "pharmacy_address": prescription.pharmacy_address,
                    "total_amount": prescription.total_amount,
                    "duration": prescription.duration,  # 투약일수 추가
                    "end_date": end_date,  # 투약 종료일 추가
                    "created_at": prescription.created_at,
                }
                prescription_list.append(prescription_data)

            return Response(
                {"count": len(prescription_list), "results": prescription_list},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"처방전 조회 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PrescriptionDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="특정 prescription_id를 가진 처방전을 삭제합니다.",
        responses={
            200: openapi.Response(description="처방전이 성공적으로 삭제되었습니다."),
            404: openapi.Response(description="해당 처방전을 찾을 수 없습니다."),
            400: openapi.Response(description="처방전 삭제 중 오류가 발생했습니다."),
        },
    )
    def delete(self, request, prescription_id):
        try:
            prescription = Prescription.objects.get(
                child__user=request.user, 
                prescription_id=prescription_id
            )
            prescription.delete()

            return Response(
                {"message": "처방전이 성공적으로 삭제되었습니다."},
                status=status.HTTP_200_OK,
            )

        except Prescription.DoesNotExist:
            return Response(
                {"error": "해당 처방전을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            return Response(
                {"error": f"처방전 삭제 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PrescriptionDetailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="처방전 ID로 상세 정보를 조회합니다.",
        manual_parameters=[
            openapi.Parameter(
                'prescription_id',
                openapi.IN_PATH,
                description="조회할 처방전 ID",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="처방전 상세 정보",
                examples={
                    "application/json": {
                        "success": True,
                        "data": {
                            "child_name": "최지아",
                            "pharmacy_info": {
                                "name": "창동메디컬약국",
                                "address": "서울시 도봉구 마들로13길61"
                            },
                            "prescription_date": "2025-02-17",
                            "total_amount": "6400",
                            "medicines": [
                                {
                                    "name": "타이레놀",
                                    "dosage": "1",
                                    "frequency": 3,
                                    "duration": 3
                                }
                            ]
                        }
                    }
                }
            ),
            404: "처방전을 찾을 수 없습니다."
        }
    )
    def get(self, request, prescription_id):
        try:
            # 처방전 조회 (자녀 정보도 함께 가져옴)
            prescription = Prescription.objects.select_related('child').get(
                prescription_id=prescription_id,
                child__user=request.user  # 현재 로그인한 사용자의 자녀의 처방전만 조회
            )

            # 약품 정보 조회
            medicines = prescription.medicines.all()

            response_data = {
                "success": True,
                "data": {
                    "child_name": prescription.child.child_name,
                    "pharmacy_info": {
                        "name": prescription.pharmacy_name,
                        "address": prescription.pharmacy_address
                    },
                    "prescription_date": prescription.prescription_date,
                    "total_amount": prescription.total_amount,
                    "medicines": [
                        {
                            "name": medicine.name,
                            "dosage": medicine.dosage,
                            "frequency": medicine.frequency,
                            "duration": medicine.duration
                        } for medicine in medicines
                    ]
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Prescription.DoesNotExist:
            return Response(
                {"success": False, "error": "처방전을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"success": False, "error": f"처방전 조회 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
