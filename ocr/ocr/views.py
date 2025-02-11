import os
import json
import requests
import uuid
import time
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view
from django.core.files.storage import default_storage

# 네이버 CLOVA OCR API 정보
API_URL = ""
SECRET_KEY = ""

@api_view(["POST"])
def ocr_process(request):
    """OCR 기능: React Native에서 업로드한 이미지 처리"""
    try:
        if "file" in request.FILES:
            image_file = request.FILES["file"]
            file_path = default_storage.save("media/" + image_file.name, image_file)
            full_file_path = Path(settings.BASE_DIR) / file_path  # ✅ 전체 경로 설정

            # OCR 요청 데이터 구성
            request_json = {
                "images": [{"format": "jpg", "name": "ocr_image"}],
                "requestId": str(uuid.uuid4()),
                "version": "V2",
                "timestamp": int(round(time.time() * 1000)),
            }

            payload = {"message": json.dumps(request_json).encode("UTF-8")}
            files = [("file", open(full_file_path, "rb"))]  # ✅ 저장된 파일 열기
            headers = {"X-OCR-SECRET": SECRET_KEY}

            # 네이버 CLOVA OCR API 호출
            response = requests.post(API_URL, headers=headers, data=payload, files=files)
            os.remove(full_file_path)  # ✅ 처리 후 파일 삭제

            if response.status_code == 200:
                ocr_data = response.json()
                extracted_text = [
                    field["inferText"] for field in ocr_data["images"][0]["fields"] if "inferText" in field
                ]

                return JsonResponse({"status": "success", "text": extracted_text}, status=200)
            else:
                return JsonResponse({"status": "error", "message": "OCR 요청 실패"}, status=500)

        else:
            return JsonResponse({"status": "error", "message": "파일이 없습니다."}, status=400)

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
