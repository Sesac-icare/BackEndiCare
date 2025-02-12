# import os
# import time
# import uuid
# import requests
# import logging

# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser, FormParser

# logger = logging.getLogger(__name__)

# class ClovaOCRAPIView(APIView):
#     parser_classes = (MultiPartParser, FormParser)
    
#     def post(self, request, *args, **kwargs):
#         # 파일이 제대로 전달되었는지 확인
#         if 'image' not in request.data:
#             logger.error("No image file provided in the request data.")
#             return Response({'error': 'No image file provided'}, status=400)
        
#         image_file = request.data['image']
#         image_file.seek(0)  # 파일 포인터를 처음 위치로 이동
        
#         # 파일 구성: (파일명, 파일 객체, content_type)
#         files = {
#             "file": (image_file.name, image_file, image_file.content_type)
#         }
        
#         # OCR API에 필요한 추가 데이터
#         data = {
#             "version": "V2",
#             "requestId": str(uuid.uuid4()),
#             "timestamp": str(int(time.time() * 1000)),
#             "lang": "ko"
#         }
        
#         # 환경변수에서 클로바 OCR 시크릿키 가져오기
#         clova_secret = os.environ.get("SECRET_KEY_OCR")
#         if not clova_secret:
#             logger.error("CLOVA_OCR_SECRET 환경변수가 설정되어 있지 않습니다.")
#             return Response({'error': 'CLOVA_OCR_SECRET is not set in environment.'}, status=500)
        
#         headers = {
#             "X-OCR-SECRET": clova_secret
#         }
        
#         # 클로바 OCR API 엔드포인트
#         ocr_url = "https://naveropenapi.apigw.ntruss.com/vision-ocr/v1/ocr"
        
#         try:
#             response = requests.post(ocr_url, headers=headers, data=data, files=files)
#             response.raise_for_status()  # HTTP 에러 상태면 예외 발생
#         except requests.RequestException as e:
#             logger.exception("Error calling Clova OCR API")
#             return Response({'error': 'Error calling Clova OCR API', 'detail': str(e)}, status=500)
        
#         try:
#             ocr_result = response.json()
#         except ValueError:
#             logger.exception("Error parsing JSON response from Clova OCR API")
#             return Response({'error': 'Invalid JSON response from Clova OCR API'}, status=500)
        
#         return Response(ocr_result)


import os
import time
import uuid
import requests
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

logger = logging.getLogger(__name__)

# 직접 하드코딩한 클로바 OCR 시크릿키 (운영 환경에서는 환경변수 사용 권장)
CLOVA_OCR_SECRET = ""

# APIGW에서 제공하는 실제 Invoke URL (NCP 콘솔에서 확인한 URL로 교체)


OCR_API_URL = "https://3ja254nf6l.apigw.ntruss.com/custom/v1/38065/f6e2a7f6d39340c1a967762f8265e55ed0cf9e441f30ee185ba6a26df73d34db/general"  

class ClovaOCRAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        if 'image' not in request.data:
            logger.error("No image file provided in the request data.")
            return Response({'error': 'No image file provided'}, status=400)
        
        image_file = request.data['image']
        image_file.seek(0)
        
        files = {
            "file": (image_file.name, image_file, image_file.content_type)
        }
        
        data = {
            "version": "V2",  # 혹은 API 문서에 따른 버전을 사용
            "requestId": str(uuid.uuid4()),
            "timestamp": str(int(time.time() * 1000)),
            "lang": "ko"
        }
        
        headers = {
            "X-OCR-SECRET": CLOVA_OCR_SECRET
        }
        
        try:
            response = requests.post(OCR_API_URL, headers=headers, data=data, files=files)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.exception("Error calling Clova OCR API")
            return Response({'error': 'Error calling Clova OCR API', 'detail': str(e)}, status=500)
        
        try:
            ocr_result = response.json()
        except ValueError:
            logger.exception("Error parsing JSON response from Clova OCR API")
            return Response({'error': 'Invalid JSON response from Clova OCR API'}, status=500)
        
        return Response(ocr_result)

