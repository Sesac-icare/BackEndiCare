from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import F
from django.db.models.functions import Radians, Sin, Cos, ACos
from .models import Pharmacy
from .serializers import PharmacySerializer
from users.models import UserProfile
from django.core.management import call_command
import requests
import xml.etree.ElementTree as ET
import math
from datetime import datetime

def haversine(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):  
        return float("inf")

    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def format_pharmacy_data(pharmacy):
    """약국 정보를 원하는 형식으로 변환"""
    weekday = datetime.now().weekday()
    current_time = datetime.now().strftime('%H%M')

    # 요일별 시작/종료 시간
    time_mapping = {
        0: (pharmacy.mon_start, pharmacy.mon_end),
        1: (pharmacy.tue_start, pharmacy.tue_end),
        2: (pharmacy.wed_start, pharmacy.wed_end),
        3: (pharmacy.thu_start, pharmacy.thu_end),
        4: (pharmacy.fri_start, pharmacy.fri_end),
        5: (pharmacy.sat_start, pharmacy.sat_end),
        6: (pharmacy.sun_start, pharmacy.sun_end),
    }

    start_time, end_time = time_mapping[weekday]
    
    # 영업 상태 확인
    if start_time and end_time:  # 영업 시간 정보가 있는 경우만 체크
        if start_time <= current_time <= end_time:
            status = "영업중"
        else:
            status = "영업종료"
    else:  # 영업 시간 정보가 없으면 영업종료
        status = "영업종료"

    # 영업 시간 포맷팅
    operating_hours = "정보없음"
    if start_time and end_time:
        operating_hours = f"{start_time[:2]}:{start_time[2:]} ~ {end_time[:2]}:{end_time[2:]}"

    return {
        "약국명": pharmacy.name,
        "영업 상태": status,
        "영업 시간": operating_hours,
        "거리": f"{round(pharmacy.distance, 1)}km",
        "주소": pharmacy.address,
        "전화": pharmacy.tel
    }

def update_pharmacy_data():
    """약국 데이터 수동 업데이트"""
    call_command('update_pharmacies')

class OpenPharmacyListAPIView(APIView):
    """영업중인 약국 목록을 반환하는 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            user_profile = request.user.profile
            if not (user_profile.latitude and user_profile.longitude):
                return Response(
                    {"error": "사용자의 위치 정보가 없습니다."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            ref_lat = float(user_profile.latitude)
            ref_lon = float(user_profile.longitude)

            nearby_pharmacies = (
                Pharmacy.objects
                .annotate(
                    distance=ACos(
                        Cos(Radians(ref_lat)) * 
                        Cos(Radians(F('latitude'))) * 
                        Cos(Radians(F('longitude')) - Radians(ref_lon)) + 
                        Sin(Radians(ref_lat)) * 
                        Sin(Radians(F('latitude')))
                    ) * 6371
                )
                .filter(distance__lte=10)  # 10km 이내
                .order_by('distance')
            )

            # 영업중인 약국만 필터링
            formatted_pharmacies = []
            for pharmacy in nearby_pharmacies:
                formatted_data = format_pharmacy_data(pharmacy)
                if formatted_data["영업 상태"] == "영업중":
                    formatted_pharmacies.append(formatted_data)

            return Response(formatted_pharmacies)

        except Exception as e:
            return Response(
                {"error": f"약국 정보 조회 중 오류가 발생했습니다: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class NearbyPharmacyListAPIView(APIView):
    """가까운 순서대로 약국 목록을 반환하는 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            user_profile = request.user.profile
            if not (user_profile.latitude and user_profile.longitude):
                return Response(
                    {"error": "사용자의 위치 정보가 없습니다."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            ref_lat = float(user_profile.latitude)
            ref_lon = float(user_profile.longitude)

            nearby_pharmacies = (
                Pharmacy.objects
                .annotate(
                    distance=ACos(
                        Cos(Radians(ref_lat)) * 
                        Cos(Radians(F('latitude'))) * 
                        Cos(Radians(F('longitude')) - Radians(ref_lon)) + 
                        Sin(Radians(ref_lat)) * 
                        Sin(Radians(F('latitude')))
                    ) * 6371
                )
                .filter(distance__lte=10)  # 10km 이내
                .order_by('distance')[:5]  # 가까운 5개만
            )

            formatted_pharmacies = [format_pharmacy_data(p) for p in nearby_pharmacies]
            return Response(formatted_pharmacies)

        except Exception as e:
            return Response(
                {"error": f"약국 정보 조회 중 오류가 발생했습니다: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
