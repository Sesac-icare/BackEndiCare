# drugapp/views.py
import requests
import xmltodict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# API 키를 환경 변수에서 가져오기
service_key = os.getenv('DRUG_API_KEY')

class DrugSearchAPIView(APIView):
    """
    POST 요청으로 전달된 drugName(약품명)을 이용하여 
    외부 공공 데이터 API에서 해당 약품 정보를 조회하고,
    itemName(제품명), efcyQesitm(약의 효능), atpnQesitm(주의사항),
    depositMethodQesitm(보관 방법) 필드를 추출하여 JSON으로 반환합니다.
    """
    def post(self, request, *args, **kwargs):
        drug_name = request.data.get("drugName")
        if not drug_name:
            return Response(
                {"error": "drugName 파라미터가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 공공 데이터 API 엔드포인트
        base_url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        
        # API 요청 파라미터 구성
        params = {
            "serviceKey": service_key,
            "itemName": drug_name,
            "pageNo": 1,
            "startPage": 1,
            "numOfRows": 10,
            "_type": "xml"
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            
            # XML 응답을 dict로 파싱
            data_dict = xmltodict.parse(response.text)
            
            # 응답 구조 확인
            body = data_dict.get("response", {}).get("body", {})
            
            # 결과가 없는 경우 체크
            total_count = int(body.get("totalCount", 0))
            if total_count == 0:
                return Response({
                    "type": "no_results",
                    "message": f"'{drug_name}'에 해당하는 약 정보가 없습니다.",
                    "data": []
                }, status=status.HTTP_200_OK)  # 200 상태코드로 변경
            
            # 결과가 있는 경우 처리
            items = body.get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            
            results = []
            for item in items:
                extracted = {
                    "itemName": item.get("itemName", "N/A"),
                    "efcyQesitm": item.get("efcyQesitm", "N/A"),
                    "atpnQesitm": item.get("atpnQesitm", "N/A"),
                    "depositMethodQesitm": item.get("depositMethodQesitm", "N/A"),
                    "entpName": item.get("entpName", "N/A"),
                }
                results.append(extracted)
            
            return Response({
                "type": "success",
                "message": "약 정보를 찾았습니다.",
                "data": results
            }, status=status.HTTP_200_OK)
        
        except requests.exceptions.RequestException as e:
            return Response({
                "type": "error",
                "message": "약 정보 조회 중 오류가 발생했습니다.",
                "error_details": str(e),
                "data": []
            }, status=status.HTTP_200_OK)  # API 오류도 200으로 반환
        
        except Exception as ex:
            return Response({
                "type": "error",
                "message": "약 정보 조회 중 오류가 발생했습니다.",
                "error_details": str(ex),
                "data": []
            }, status=status.HTTP_200_OK)  # 일반 오류도 200으로 반환
