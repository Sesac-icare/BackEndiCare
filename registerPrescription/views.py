from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import OCRRequestSerializer, OCRResultSerializer
import json
import requests
import uuid
import time
import re
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Prescription, Medicine
from .serializers import PrescriptionSerializer, MedicineSerializer
from children.models import Children

class OCRAPIView(APIView):
    def extract_info(self, extracted_text):
        """OCR 결과에서 특정 키워드 기반으로 데이터를 정리하여 JSON 형식으로 변환"""
        data = {
            "약국명": None,
            "처방전번호": None,
            "처방일자": None,
            "약품명": [],
            "복용량": [],
            "수량": [],
        }

        temp_medicines = []  # 약품명 임시 저장
        temp_dosages = []  # 복용량 임시 저장
        temp_quantities = []  # 수량 임시 저장

        for i, text in enumerate(extracted_text):
            if "약국" in text:
                data["약국명"] = text

            elif re.match(r'\d{8}-\d{8}', text):  # 처방전 번호 형식 예시
                data["처방전번호"] = text

            elif "조제일자" in text or "조제일" in text:
                match = re.search(r"\d{4}-\d{2}-\d{2}", text)
                if match:
                    data["처방일자"] = match.group()

            elif re.search(r"정|시럽|캡슐|정제", text):
                temp_medicines.append(text)
                if i + 1 < len(extracted_text) and extracted_text[i + 1].isdigit():
                    temp_dosages.append(extracted_text[i + 1])
                if i + 2 < len(extracted_text) and extracted_text[i + 2].isdigit():
                    temp_quantities.append(extracted_text[i + 2])

        data["약품명"] = temp_medicines
        data["복용량"] = temp_dosages
        data["수량"] = temp_quantities

        return data

    def call_ocr(self, image_path):
        """CLOVA OCR API 요청 및 결과 출력"""
        API_URL = ""  # CLOVA OCR API URL
        SECRET_KEY = ""  # Your Secret Key

        request_json = {
            "images": [{"format": "jpg", "name": "ocr_image"}],
            "requestId": str(uuid.uuid4()),
            "version": "V2",
            "timestamp": int(round(time.time() * 1000)),
        }

        with open(image_path, "rb") as image_file:
            files = [("file", image_file)]
            headers = {"X-OCR-SECRET": SECRET_KEY}
            response = requests.post(
                API_URL, 
                headers=headers, 
                data={"message": json.dumps(request_json)}, 
                files=files
            )

        if response.status_code == 200:
            ocr_data = response.json()
            extracted_text = [field["inferText"] for field in ocr_data["images"][0]["fields"] if "inferText" in field]
            parsed_data = self.extract_info(extracted_text)
            return parsed_data
        else:
            return {"error": f"OCR 요청 실패 상태 코드: {response.status_code}", "message": response.text}

    def post(self, request):
        serializer = OCRRequestSerializer(data=request.data)
        if serializer.is_valid():
            image_file = request.FILES["image"]
            child_id = serializer.validated_data['child_id']
            
            try:
                child = Children.objects.get(id=child_id)
            except Children.DoesNotExist:
                return Response({"error": "Child not found"}, status=status.HTTP_404_NOT_FOUND)

            file_path = default_storage.save(
                f"uploads/{image_file.name}", 
                ContentFile(image_file.read())
            )

            parsed_data = self.call_ocr(file_path)
            result_serializer = OCRResultSerializer(data=parsed_data)
            
            if result_serializer.is_valid():
                prescription = Prescription.objects.create(
                    child=child,
                    pharmacy_name=parsed_data['약국명'],
                    prescription_number=parsed_data['처방전번호'],
                    prescription_date=parsed_data['처방일자']
                )

                # 약품 정보 저장
                for name, dosage, quantity in zip(
                    parsed_data['약품명'],
                    parsed_data['복용량'],
                    parsed_data['수량']
                ):
                    Medicine.objects.create(
                        prescription=prescription,
                        name=name,
                        dosage=dosage,
                        quantity=quantity
                    )

                prescription_serializer = PrescriptionSerializer(prescription)
                return Response(prescription_serializer.data, status=status.HTTP_201_CREATED)
                
            return Response(result_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PrescriptionListView(APIView):
    def get(self, request):
        # user의 모든 자녀들의 처방전을 조회
        prescriptions = Prescription.objects.filter(child__user=request.user)
        serializer = PrescriptionSerializer(prescriptions, many=True)
        return Response(serializer.data)

class PrescriptionDetailView(APIView):
    def get(self, request, pk):
        try:
            # user의 자녀의 처방전인지 확인
            prescription = Prescription.objects.get(pk=pk, child__user=request.user)
            serializer = PrescriptionSerializer(prescription)
            return Response(serializer.data)
        except Prescription.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


