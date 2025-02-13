# drugapp/views.py
import requests
import xmltodict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

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
        
        
        service_key = ''
        # 공공 데이터 API 엔드포인트
        base_url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        
        # API 요청 파라미터 구성 (검색할 약품명을 itemName 파라미터에 전달)
        params = {
            "serviceKey": service_key,
            "itemName": drug_name,
            "pageNo": 1,
            "startPage": 1,
            "numOfRows": 10,
            "_type": "xml"  # XML 응답을 받음
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            
            # XML 응답을 dict로 파싱
            data_dict = xmltodict.parse(response.text)
            # 응답 구조: response -> body -> items -> item
            items = data_dict.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            # 단일 항목일 경우 dict로 반환될 수 있으므로 리스트로 변환
            if isinstance(items, dict):
                items = [items]
            
            if not items:
                return Response(
                    {"message": f"'{drug_name}'에 해당하는 데이터가 없습니다."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 원하는 필드만 추출하여 결과 리스트 구성
            results = []
            for item in items:
                extracted = {
                    "itemName": item.get("itemName", "N/A"),
                    "efcyQesitm": item.get("efcyQesitm", "N/A"),
                    "atpnQesitm": item.get("atpnQesitm", "N/A"),
                    "depositMethodQesitm": item.get("depositMethodQesitm", "N/A")
                }
                results.append(extracted)
            
            return Response(results, status=status.HTTP_200_OK)
        
        except requests.exceptions.RequestException as e:
            return Response(
                {"error": "API 요청 중 오류 발생", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as ex:
            return Response(
                {"error": "오류 발생", "details": str(ex)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
