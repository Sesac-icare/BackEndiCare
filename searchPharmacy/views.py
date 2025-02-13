import requests
import xml.etree.ElementTree as ET
import math
from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response

def haversine(lat1, lon1, lat2, lon2):
    """
    두 좌표 간의 거리를 킬로미터 단위로 계산 (Haversine 공식)
    """
    if None in (lat1, lon1, lat2, lon2):  
        return float("inf")  # 위도/경도 값이 없으면 가장 먼 거리로 설정

    R = 6371  # 지구 반경 (km)
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def fetch_pharmacies():
    """
    Open API를 통해 전국 약국 정보를 가져옵니다.
    """
    url = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyFullDown"
    service_key = ""
    
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 1000,  # 약국 범위를 전국으로 하나, 반경을 10km이내로 잡고 정보를 끌어오는 형식으로 코드 변경 창동역을 기준으로 1km 이내 약국 약 10개정도 나오는 것을 확인
        "type": "xml"
    }
    
    response = requests.get(url, params=params)
    pharmacies = []
    
    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            for item in root.iter("item"):
                dutyName = item.findtext("dutyName")
                dutyAddr = item.findtext("dutyAddr")
                dutyTel1 = item.findtext("dutyTel1")  # 대표전화
                
                lat_text = item.findtext("wgs84Lat")
                lon_text = item.findtext("wgs84Lon")

                try:
                    lat = float(lat_text) if lat_text else None
                    lon = float(lon_text) if lon_text else None
                except ValueError:
                    lat, lon = None, None
                    
                if lat is not None and lon is not None:
                    dutyTime = {day: {"start": item.findtext(f"dutyTime{i}s"), 
                                      "close": item.findtext(f"dutyTime{i}c")} for i, day in 
                                enumerate(["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"], start=1)}

                    # 현재 요일 및 시간 정보
                    current_time = int(datetime.now().strftime("%H%M"))
                    day_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
                    today_name = day_names[datetime.now().weekday()]
                    
                    today_hours = dutyTime.get(today_name)
                    today_status = "정보없음"
                    if today_hours and today_hours["start"] and today_hours["close"]:
                        try:
                            start_time = int(today_hours["start"])
                            close_time = int(today_hours["close"])
                            today_status = "영업중" if start_time <= current_time < close_time else "영업종료"
                        except ValueError:
                            pass
                    
                    pharmacy_info = {
                        "name": dutyName,
                        "address": dutyAddr,
                        "tel": dutyTel1,
                        "lat": lat,
                        "lon": lon,
                        "operating_hours": dutyTime,
                        "today_status": today_status
                    }
                    
                    pharmacies.append(pharmacy_info)
        except ET.ParseError as e:
            print("XML 파싱 에러:", e)
    
    return pharmacies

def format_pharmacy_data(pharmacy_info):
    """
    약국 정보를 보기 쉽게 한국어 key 값으로 변환
    """
    today = datetime.today().strftime("%A")  
    korean_days = {
        "Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
        "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일", "Sunday": "일요일"
    }
    today_korean = korean_days[today]

    open_time = pharmacy_info["operating_hours"].get(today_korean, {}).get("start", "0800")
    close_time = pharmacy_info["operating_hours"].get(today_korean, {}).get("close", "2100")
    
    open_time = f"{open_time[:2]}:{open_time[2:]}"
    close_time = f"{close_time[:2]}:{close_time[2:]}"
    
    formatted_operating_hours = f"{open_time} ~ {close_time}"
    distance_km = round(pharmacy_info["distance_km"], 1)

    return {
        "약국명": pharmacy_info["name"],
        "영업 상태": pharmacy_info["today_status"],
        "영업 시간": formatted_operating_hours,
        "거리": f"{distance_km}km",
        "주소": pharmacy_info["address"],
        "전화": pharmacy_info["tel"]
    }

class PharmacyListAPIView(APIView):
    """
    GET 요청 시 반경 10km 이내의 약국만 반환합니다.
    """
    def get(self, request, *args, **kwargs):
        # 기준 위치: 창동역
        ref_lat = 37.65276
        ref_lon = 127.047945

        pharmacies = fetch_pharmacies()

        # 반경 10km 이내 약국 필터링
        nearby_pharmacies = []
        for pharmacy in pharmacies:
            if pharmacy["lat"] is not None and pharmacy["lon"] is not None:
                distance = haversine(ref_lat, ref_lon, pharmacy["lat"], pharmacy["lon"])
                if distance <= 10:  # 반경 10km 이내
                    pharmacy["distance_km"] = distance
                    nearby_pharmacies.append(pharmacy)

        # 거리를 기준으로 정렬 (가까운 순)
        pharmacies_sorted = sorted(nearby_pharmacies, key=lambda x: x["distance_km"])

        for pharmacy in pharmacies_sorted:
            pharmacy.pop("lat", None)
            pharmacy.pop("lon", None)

        formatted_pharmacies = [format_pharmacy_data(p) for p in pharmacies_sorted]

        # 프론트에 넘겨주기
        return Response(formatted_pharmacies)
