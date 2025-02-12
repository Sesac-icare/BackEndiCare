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
    R = 6371  # 지구 반경 (km)
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (
        math.sin(dLat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dLon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def fetch_pharmacies():
    """
    Open API를 통해 전체 약국 데이터를 받아와서, 주소에 '서울'이 포함된 항목만 반환합니다.
    추가로 각 약국의 대표전화와 요일별 진료시간 및 오늘의 영업 상태(영업중/영업종료) 정보를 포함합니다.
    """
    url = (
        "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyFullDown"
    )
    service_key = ""

    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 10,  # 필요에 따라 조정
        "type": "xml",
    }

    response = requests.get(url, params=params)
    pharmacies = []

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            # XML의 각 <item> 태그를 순회
            for item in root.iter("item"):
                dutyName = item.findtext("dutyName")
                dutyAddr = item.findtext("dutyAddr")
                dutyTel1 = item.findtext("dutyTel1")  # 대표전화

                # 주소에 '서울'이 포함된 데이터만 선택
                if dutyAddr and "서울" in dutyAddr:
                    lat_text = item.findtext("wgs84Lat")
                    lon_text = item.findtext("wgs84Lon")

                    try:
                        lat = float(lat_text) if lat_text else None
                        lon = float(lon_text) if lon_text else None
                    except ValueError:
                        lat, lon = None, None

                    if lat is not None and lon is not None:
                        # 요일별 진료시간 추출 (월요일 ~ 일요일)
                        dutyTime1s = item.findtext("dutyTime1s")  # 월요일 시작
                        dutyTime1c = item.findtext("dutyTime1c")  # 월요일 종료
                        dutyTime2s = item.findtext("dutyTime2s")  # 화요일 시작
                        dutyTime2c = item.findtext("dutyTime2c")  # 화요일 종료
                        dutyTime3s = item.findtext("dutyTime3s")  # 수요일 시작
                        dutyTime3c = item.findtext("dutyTime3c")  # 수요일 종료
                        dutyTime4s = item.findtext("dutyTime4s")  # 목요일 시작
                        dutyTime4c = item.findtext("dutyTime4c")  # 목요일 종료
                        dutyTime5s = item.findtext("dutyTime5s")  # 금요일 시작
                        dutyTime5c = item.findtext("dutyTime5c")  # 금요일 종료
                        dutyTime6s = item.findtext("dutyTime6s")  # 토요일 시작
                        dutyTime6c = item.findtext("dutyTime6c")  # 토요일 종료
                        dutyTime7s = item.findtext("dutyTime7s")  # 일요일 시작
                        dutyTime7c = item.findtext("dutyTime7c")  # 일요일 종료

                        # 운영시간 정보를 딕셔너리로 구성
                        operating_hours = {
                            "월요일": {"start": dutyTime1s, "close": dutyTime1c},
                            "화요일": {"start": dutyTime2s, "close": dutyTime2c},
                            "수요일": {"start": dutyTime3s, "close": dutyTime3c},
                            "목요일": {"start": dutyTime4s, "close": dutyTime4c},
                            "금요일": {"start": dutyTime5s, "close": dutyTime5c},
                            "토요일": {"start": dutyTime6s, "close": dutyTime6c},
                            "일요일": {"start": dutyTime7s, "close": dutyTime7c},
                        }

                        # 현재 요일 및 시간 정보 (HHMM 정수형)
                        current_time = int(datetime.now().strftime("%H%M"))
                        day_names = [
                            "월요일",
                            "화요일",
                            "수요일",
                            "목요일",
                            "금요일",
                            "토요일",
                            "일요일",
                        ]
                        today_index = datetime.now().weekday()  # Monday=0, ... Sunday=6
                        today_name = day_names[today_index]

                        # 오늘의 운영시간 정보와 영업 상태 결정
                        today_hours = operating_hours.get(today_name)
                        if (
                            today_hours
                            and today_hours["start"]
                            and today_hours["close"]
                        ):
                            try:
                                start_time = int(today_hours["start"])
                                close_time = int(today_hours["close"])
                                if start_time <= current_time < close_time:
                                    today_status = "영업중"
                                else:
                                    today_status = "영업종료"
                            except ValueError:
                                today_status = "정보없음"
                        else:
                            today_status = "정보없음"

                        # 내부 계산을 위해 위도와 경도는 저장하지만, 최종 응답에서는 제거할 예정
                        pharmacy_info = {
                            "name": dutyName,
                            "address": dutyAddr,
                            "tel": dutyTel1,
                            "lat": lat,
                            "lon": lon,
                            "operating_hours": operating_hours,
                            "today_status": today_status,
                        }

                        pharmacies.append(pharmacy_info)
        except ET.ParseError as e:
            print("XML 파싱 에러:", e)
    else:
        print(f"요청 실패. 상태 코드: {response.status_code}")

    return pharmacies


class PharmacyListAPIView(APIView):
    """
    GET 요청 시 서울 내 약국 정보를 기준 위치(서울시청)와의 거리를 계산하여 가까운 순으로 반환합니다.
    각 약국의 진료시간(요일별)과 오늘의 영업 상태(영업중/영업종료)도 함께 출력하며,
    위도와 경도 정보는 최종 응답에서 제외합니다.
    """

    def get(self, request, *args, **kwargs):
        # 기준 위치: 서울시청 (예시)
        ref_lat = 37.5665
        ref_lon = 126.9780

        pharmacies = fetch_pharmacies()

        # 각 약국에 대해 기준 위치와의 거리를 계산 (내부 계산용)
        for pharmacy in pharmacies:
            pharmacy["distance_km"] = haversine(
                ref_lat, ref_lon, pharmacy["lat"], pharmacy["lon"]
            )

        # 거리를 기준으로 정렬
        pharmacies_sorted = sorted(pharmacies, key=lambda x: x["distance_km"])

        # 최종 응답 전에 위도와 경도 정보는 제거합니다.
        for pharmacy in pharmacies_sorted:
            pharmacy.pop("lat", None)
            pharmacy.pop("lon", None)

        return Response(pharmacies_sorted)
