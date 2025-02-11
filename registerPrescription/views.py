from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import OCRRequestSerializer, OCRResultSerializer
import json
import requests
import uuid
import time
import re
import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import models
from users.models import User
from children.models import Children
from .models import PharmacyEnvelope  # 모델을 import

# 환경변수에서 시크릿 키 불러오기
from django.conf import settings
SECRET_KEY_OCR = getattr(settings, 'SECRET_KEY_OCR', None)

if not SECRET_KEY_OCR:
    raise ValueError("SECRET_KEY_OCR is not set in environment variables")

class OCRAPIView(APIView):
    def extract_info(self, extracted_text):
        """OCR 결과에서 특정 키워드 기반으로 데이터를 정리하여 JSON 형식으로 변환"""
        data = {
            "pharmacy_name": None,
            "prescription_number": None,
            "prescription_date": None,
        }

        for text in extracted_text:
            if "약국" in text:
                data["pharmacy_name"] = text
            elif re.match(r'\d{8}-\d{8}', text):
                data["prescription_number"] = text
            elif "조제일자" in text or "조제일" in text:
                match = re.search(r"\d{4}-\d{2}-\d{2}", text)
                if match:
                    data["prescription_date"] = match.group()

        return data

    def call_ocr(self, image_path):
        """CLOVA OCR API 요청 및 결과 출력"""
        API_URL = "https://3ja254nf6l.apigw.ntruss.com/custom/v1/38065/f6e2a7f6d39340c1a967762f8265e55ed0cf9e441f30ee185ba6a26df73d34db/general"
        SECRET_KEY = SECRET_KEY_OCR

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
                child = Children.objects.get(child_id=child_id)
            except Children.DoesNotExist:
                return Response({"error": "Child not found"}, status=status.HTTP_404_NOT_FOUND)

            file_path = default_storage.save(
                f"uploads/{image_file.name}", 
                ContentFile(image_file.read())
            )

            parsed_data = self.call_ocr(file_path)
            
            try:
                # 처방전 정보 저장
                envelope = PharmacyEnvelope.objects.create(
                    child=child,
                    pharmacy_name=parsed_data['pharmacy_name'],
                    prescription_number=parsed_data['prescription_number'],
                    prescription_date=parsed_data['prescription_date']
                )
                
                return Response({
                    "envelope_id": envelope.envelope_id,
                    "pharmacy_name": envelope.pharmacy_name,
                    "prescription_number": envelope.prescription_number,
                    "prescription_date": envelope.prescription_date,
                    "child_id": envelope.child.child_id
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EnvelopeListView(APIView):
    def get(self, request):
        # user의 모든 자녀들의 처방전을 조회
        envelopes = PharmacyEnvelope.objects.filter(child__user=request.user)
        data = [{
            "envelope_id": env.envelope_id,
            "pharmacy_name": env.pharmacy_name,
            "prescription_number": env.prescription_number,
            "prescription_date": env.prescription_date,
            "child_id": env.child.child_id,
            "created_at": env.created_at
        } for env in envelopes]
        return Response(data)

class EnvelopeDetailView(APIView):
    def get(self, request, envelope_id):
        try:
            # user의 자녀의 처방전인지 확인
            envelope = PharmacyEnvelope.objects.get(
                envelope_id=envelope_id, 
                child__user=request.user
            )
            data = {
                "envelope_id": envelope.envelope_id,
                "pharmacy_name": envelope.pharmacy_name,
                "prescription_number": envelope.prescription_number,
                "prescription_date": envelope.prescription_date,
                "child_id": envelope.child.child_id,
                "created_at": envelope.created_at
            }
            return Response(data)
        except PharmacyEnvelope.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


