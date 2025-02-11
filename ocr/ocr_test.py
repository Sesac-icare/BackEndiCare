import json
import requests
import uuid
import time
from pathlib import Path
import re

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# CLOVA OCR API 정보
API_URL = ""
SECRET_KEY = ""

# OCR 테스트할 약 봉투 이미지 파일
IMAGE_PATH = "yourim.jpg"  # OCR로 읽을 파일명 확인!

# OCR 결과에서 필요한 정보만 추출하는 함수
def extract_info(extracted_text):
    """OCR 결과에서 특정 키워드 기반으로 데이터를 정리하여 JSON 형식으로 변환"""
    data = {
        "합    계": None,
        "환자성명": None,
        "조제일자": None,
        "약품명": [],
        "횟수": [],
        "일수": [],
    }

    temp_medicines = []  # 약품명 임시 저장
    temp_counts = []  # 횟수 임시 저장
    temp_days = []  # 일수 임시 저장

    for i, text in enumerate(extracted_text):
        if "합    계" in text:
            match = re.search(r"(\d+[,.\d]*)원", text)  # 숫자와 "원" 포함된 값 찾기
            if match:
                data["합    계"] = match.group(1) + "원"

        elif "환자성명" in text or "성명" in text:
            data["환자성명"] = extracted_text[i + 1] if i + 1 < len(extracted_text) else None

        elif "조제일자" in text or "조제일" in text:
            match = re.search(r"\d{4}-\d{2}-\d{2}", text)  # 날짜 형식 찾기
            if match:
                data["조제일자"] = match.group()

        # 약품명, 횟수, 일수 패턴 자동 추출
        elif re.search(r"정|시럽|캡슐|정제", text):  # 약품명 패턴 인식
            temp_medicines.append(text)
            if i + 1 < len(extracted_text) and extracted_text[i + 1].isdigit():  # 횟수
                temp_counts.append(extracted_text[i + 1])
            if i + 2 < len(extracted_text) and extracted_text[i + 2].isdigit():  # 일수
                temp_days.append(extracted_text[i + 2])

    # 결과 저장
    data["약품명"] = temp_medicines
    data["횟수"] = temp_counts
    data["일수"] = temp_days

    return data

# CLOVA OCR API 호출 함수
def call_ocr(image_path):
    """CLOVA OCR API 요청 및 결과 출력"""
    request_json = {
        "images": [{"format": "jpg", "name": "ocr_image"}],
        "requestId": str(uuid.uuid4()),
        "version": "V2",
        "timestamp": int(round(time.time() * 1000)),
    }

#     request_json = {
#     "images": [
#         {
#             "format": "jpg",
#             "name": "ocr_image",
#             "templateIds": [12345], 
#             "table": True 
#         }
#     ],
#     "requestId": str(uuid.uuid4()),
#     "version": "V2",
#     "timestamp": int(round(time.time() * 1000)),
# }


    with open(image_path, "rb") as image_file:
        files = [("file", image_file)]
        headers = {"X-OCR-SECRET": SECRET_KEY}

        response = requests.post(API_URL, headers=headers, data={"message": json.dumps(request_json)}, files=files)

    if response.status_code == 200:
        ocr_data = response.json()
        extracted_text = [field["inferText"] for field in ocr_data["images"][0]["fields"] if "inferText" in field]
        parsed_data = extract_info(extracted_text)
        return parsed_data
    else:
        return {"error": f"OCR 요청 실패 상태 코드: {response.status_code}", "message": response.text}
        
@csrf_exempt
def ocr_api(request):
    if request.method == "POST" and request.FILES.get("image"):
        image_file = request.FILES["image"]
        file_path = default_storage.save(f"uploads/{image_file.name}", ContentFile(image_file.read()))

        # OCR 실행
        parsed_data = call_ocr(file_path)

        # json 응답 반환
        return JsonResponse(parsed_data)
    return JsonResponse({"error": "이미지를 업로드 하세용걔륑"}, status = 400)
        
        
        
        # JSON 형태로 출력
    #     print("\n🔍 OCR 정리된 결과 (JSON):")
    #     print(json.dumps(parsed_data, ensure_ascii=False, indent=4))

    # else:
    #     print(f" OCR 요청 실패! 상태 코드: {response.status_code}")
    #     print(response.text)

# OCR 실행
# if __name__ == "__main__":
#     if Path(IMAGE_PATH).exists():
#         call_ocr(IMAGE_PATH)
#     else:
#         print(f" 오류: 파일 '{IMAGE_PATH}' 을(를) 찾을 수 없습니다!")


