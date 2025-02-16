import os
import time
import uuid
import requests
import logging
import base64
import json
import pandas as pd
from django.db import transaction
from children.models import Children
from .models import PharmacyEnvelope, Medicine

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

logger = logging.getLogger(__name__)


# 환경 변수 로드
load_dotenv()

CLOVA_OCR_SECRET = os.getenv("CLOVA_OCR_SECRET")
    
# APIGW에서 제공하는 실제 Invoke URL (NCP 콘솔에서 확인한 URL로 교체)
OCR_API_URL = "https://3ja254nf6l.apigw.ntruss.com/custom/v1/38065/f6e2a7f6d39340c1a967762f8265e55ed0cf9e441f30ee185ba6a26df73d34db/general"


class ClovaOCRAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    authentication_classes = [TokenAuthentication]  # 명시적으로 지정
    permission_classes = [IsAuthenticated]  # 명시적으로 지정
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 클래스 초기화 시 WAL 모드 설정
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA busy_timeout=10000')

    def extract_table_from_ocr(self, ocr_result):
        """
        OCR 결과의 table 영역을 판다스 DataFrame으로 변환.
        """
        table_data = []

        for image in ocr_result.get("images", []):
            for table in image.get("tables", []):
                row_dict = {}  # {row_y: [(x, text)]}

                for cell in table.get("cells", []):
                    # 안전하게 cellTextLines와 cellWords 접근
                    cell_text_lines = cell.get("cellTextLines", [])
                    if not cell_text_lines:
                        continue
                    # 첫 번째 cellTextLine 사용 (여러 줄이 있는 경우 추가 처리가 필요함)
                    cell_line = cell_text_lines[0]
                    cell_words = cell_line.get("cellWords", [])
                    if not cell_words:
                        continue

                    # 셀 내 텍스트 결합 (각 단어의 inferText 값을 공백으로 결합)
                    cell_text = " ".join(
                        [word.get("inferText", "").strip() for word in cell_words]
                    )

                    # 셀의 bounding box 좌표 추출
                    vertices = cell_line.get("boundingPoly", {}).get("vertices", [])
                    if not vertices:
                        continue  # 좌표 정보가 없으면 무시

                    # 좌표 정보: x, y 최소값 사용 (상단 왼쪽 기준)
                    min_x = min(v.get("x", 0) for v in vertices)
                    min_y = min(v.get("y", 0) for v in vertices)

                    # y 좌표를 기준으로 행(row) 그룹화 (비슷한 y 값끼리 같은 행으로 처리)
                    matched_row = None
                    for row_y in row_dict.keys():
                        if (
                            abs(row_y - min_y) < 20
                        ):  # 임계값 20픽셀 내에서 같은 행으로 간주
                            matched_row = row_y
                            break

                    if matched_row is None:
                        matched_row = min_y
                        row_dict[matched_row] = []

                    row_dict[matched_row].append((min_x, cell_text))

                # 행별로 x 좌표 기준 정렬하여 2차원 리스트 형태로 변환
                sorted_rows = []
                for row_y in sorted(row_dict.keys()):
                    sorted_row = sorted(
                        row_dict[row_y], key=lambda x: x[0]
                    )  # x값(열 위치) 기준 정렬
                    sorted_rows.append([text for _, text in sorted_row])

                table_data.extend(sorted_rows)

        # 판다스 DataFrame으로 변환
        df = pd.DataFrame(table_data)
        return df

    def process_extracted_table(self, table_df, child_name):
        """
        추출된 DataFrame에서 최종적으로 원하는 항목들을 매핑하여 결과 dict로 구성.

        최종 항목:
          - 자녀 이름 (OCR에서는 "환자성명"을 활용)
          - 조제일자(발행일) (우선 "발행일", 없으면 "조제일자")
          - 상 호(약국명)
          - 교부번호 (없으면 기본값 "1")
          - 주소 (예: "서울시"로 시작하는 주소)
          - 총수납금액 합계 (우선 "합 계", 없으면 "총수납금액" 관련 값)
          - 각 약에 따른 투약량, 횟수, 일수 (없으면 기본값 1)
        """
        result = {}
        # DataFrame의 NaN을 빈 문자열로 치환하고 리스트로 변환
        rows = table_df.fillna("").values.tolist()

        # 1. 자녀 이름 (프론트엔드에서 받은 값 사용)
        result["자녀 이름"] = child_name

        # 2. 조제일자(발행일): "발행일"이 있으면 그 값, 없으면 "조제일자"의 값 사용
        result["조제일자(발행일)"] = None
        for row in rows:
            if row[0] and "발행일" in row[0]:
                result["조제일자(발행일)"] = row[1]
                break
        if not result["조제일자(발행일)"]:
            for row in rows:
                if row[0] and "조제일자" in row[0]:
                    result["조제일자(발행일)"] = row[1]
                    break
        if not result["조제일자(발행일)"]:
            result["조제일자(발행일)"] = ""

        # 3. 상 호(약국명): "상 호" 행의 두 번째 열
        result["상 호(약국명)"] = ""
        for row in rows:
            if row[0] and "상 호" in row[0]:
                result["상 호(약국명)"] = row[1]
                break

        # 4. 교부번호: "교부번호"라는 키워드가 없으면 기본값 "1"
        result["교부번호"] = ""
        for row in rows:
            if row[0] and "교부번호" in row[0]:
                result["교부번호"] = row[1]
                break
        if not result["교부번호"]:
            result["교부번호"] = "1"

        # 5. 주소: "서울시"로 시작하는 행의 첫 번째 열 활용
        result["주소"] = ""
        for row in rows:
            if row[0] and "서울시" in row[0]:
                result["주소"] = row[0]
                break

        # 6. 총수납금액 합계: 우선 "합 계" 행의 두 번째 열, 없으면 "총수납금액" 행의 값을 활용
        result["총수납금액 합계"] = ""
        for row in rows:
            if row[0] and "합 계" in row[0]:
                result["총수납금액 합계"] = row[1]
                break
        if not result["총수납금액 합계"]:
            for row in rows:
                if row[0] and "총수납금액" in row[0]:
                    # 예제에서는 세 번째 열에 값이 있음
                    result["총수납금액 합계"] = row[2]
                    break

        # 7. 각 약에 따른 투약량, 횟수, 일수: 해당 정보가 OCR 결과에 없으면 기본값 1
        result["투약량"] = 1
        result["횟수"] = 1
        result["일수"] = 1

        return result

    def post(self, request, *args, **kwargs):
        if "image" not in request.data or "child_name" not in request.data:
            logger.error("No image file or child name provided in the request data.")
            return Response({'error': 'No image file or child name provided'}, status=400)

        # OCR 처리는 트랜잭션 밖에서 수행
        try:
            image_file = request.data['image']
            image_file.seek(0)
            image_data = image_file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # OCR API 호출 및 결과 처리
            ocr_result = self._process_ocr(image_base64, image_file.name)
            table_df = self.extract_table_from_ocr(ocr_result)
            final_result = self.process_extracted_table(table_df, request.data['child_name'])
            
            # 데이터베이스 작업은 짧은 트랜잭션으로 처리
            return self._save_prescription_data(request, final_result)

        except Exception as e:
            logger.exception("Error in prescription processing")
            return Response({
                'error': f'처방전 처리 중 오류가 발생했습니다: {str(e)}'
            }, status=500)

    def _process_ocr(self, image_base64, filename):
        """OCR 처리를 위한 별도 메서드"""
        timestamp = int(time.time() * 1000)
        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": timestamp,
            "lang": "ko",
            "images": [
                {
                    "format": "jpg",
                    "name": filename,
                    "data": image_base64
                }
            ],
            "enableTableDetection": True
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-OCR-SECRET": CLOVA_OCR_SECRET
        }
        
        response = requests.post(OCR_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()

    @transaction.atomic
    def _save_prescription_data(self, request, final_result):
        """데이터베이스 저장을 위한 별도 메서드"""
        # 자녀 정보 처리
        try:
            child = Children.objects.select_for_update(nowait=True).get(
                user=request.user,
                child_name=request.data['child_name']
            )
        except Children.DoesNotExist:
            child = Children.objects.create(
                user=request.user, child_name=request.data["child_name"]
            )
        
        # 유니크한 교부번호 생성
        unique_number = f"{final_result['교부번호']}_{uuid.uuid4().hex[:8]}"
        
        # 처방전 정보 저장
        envelope = PharmacyEnvelope.objects.create(
            child=child,
            pharmacy_name=final_result['상 호(약국명)'],
            prescription_number=unique_number,
            prescription_date=final_result['조제일자(발행일)']
        )

        response_data = {
            'message': '처방전이 성공적으로 등록되었습니다.',
            'envelope_id': envelope.envelope_id,
            'child_name': child.child_name,
            'pharmacy_name': envelope.pharmacy_name,
            'prescription_date': envelope.prescription_date,
            'user_email': request.user.email
        }
        
        return Response(response_data, status=201)

class PrescriptionListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="현재 로그인한 사용자의 모든 자녀들의 처방전을 조회합니다.",
        responses={
            200: openapi.Response(description="처방전 목록 조회 성공"),
            400: openapi.Response(description="처방전 조회 중 오류가 발생했습니다."),
        },
    )
    def get(self, request):
        try:
            # 현재 로그인한 사용자의 모든 자녀들의 처방전 조회
            prescriptions = (
                PharmacyEnvelope.objects.filter(child__user=request.user)
                .select_related("child")
                .order_by("-created_at")
            )

            prescription_list = []
            for prescription in prescriptions:
                prescription_data = {
                    "envelope_id": prescription.envelope_id,
                    "child_name": prescription.child.child_name,
                    "pharmacy_name": prescription.pharmacy_name,
                    "prescription_number": prescription.prescription_number,
                    "prescription_date": prescription.prescription_date,
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


# TODO : 테스트 필요
class PrescriptionListByDateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="현재 로그인한 사용자의 모든 자녀들의 처방전을 조제일자 기준으로 내림차순 정렬하여 조회합니다.",
        responses={
            200: openapi.Response(description="처방전 목록 조회 성공"),
            400: openapi.Response(description="처방전 조회 중 오류가 발생했습니다."),
        },
    )
    def get(self, request):
        try:
            # 현재 로그인한 사용자의 모든 자녀들의 처방전 조회
            prescriptions = (
                PharmacyEnvelope.objects.filter(child__user=request.user)
                .select_related("child")
                .order_by("-prescription_date")  # prescription_date 기준 내림차순 정렬
            )

            prescription_list = []
            for prescription in prescriptions:
                prescription_data = {
                    "envelope_id": prescription.envelope_id,
                    "child_name": prescription.child.child_name,
                    "pharmacy_name": prescription.pharmacy_name,
                    "prescription_number": prescription.prescription_number,
                    "prescription_date": prescription.prescription_date,
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


# TODO : 테스트 필요
class PrescriptionDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="특정 envelope_id를 가진 처방전을 삭제합니다.",
        responses={
            200: openapi.Response(description="처방전이 성공적으로 삭제되었습니다."),
            404: openapi.Response(description="해당 처방전을 찾을 수 없습니다."),
            400: openapi.Response(description="처방전 삭제 중 오류가 발생했습니다."),
        },
    )
    def delete(self, request, envelope_id):
        try:
            # 현재 로그인한 사용자의 자녀들의 처방전 중에서 해당 envelope_id를 가진 데이터 삭제
            prescription = PharmacyEnvelope.objects.get(
                child__user=request.user, envelope_id=envelope_id
            )
            prescription.delete()

            return Response(
                {"message": "처방전이 성공적으로 삭제되었습니다."},
                status=status.HTTP_200_OK,
            )

        except PharmacyEnvelope.DoesNotExist:
            return Response(
                {"error": "해당 처방전을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            return Response(
                {"error": f"처방전 삭제 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
