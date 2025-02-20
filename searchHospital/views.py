import json
import openpyxl
from geopy.distance import geodesic
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import F, Q
from django.db.models.functions import ACos, Cos, Radians, Sin
from datetime import datetime, time
import math
import re

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.contrib.auth.hashers import make_password

from .models import Hospital
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


def haversine(lat1, lon1, lat2, lon2):
    """두 지점 간의 거리를 계산 (km)"""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    
    R = 6371  # 지구의 반경(km)
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat/2) * math.sin(dLat/2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon/2) * math.sin(dLon/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def normalize_time(time_str):
    """시간 문자열을 정규화"""
    try:
        # 한글 제거
        time_str = re.sub(r'[가-힣]', '', time_str)
        # 공백 제거
        time_str = time_str.strip()
        
        # 30:00과 같은 잘못된 시간 처리
        if time_str.startswith('24:'):
            return '00:00'
        elif time_str.startswith('30:'):
            return '18:00'  # 또는 다른 적절한 기본값
            
        return time_str
    except Exception:
        return '00:00'  # 파싱 실패시 기본값


class HospitalSearchView(APIView):
    permission_classes = [IsAuthenticated]
    
    def merge_hours(self, treatment_hours, reception_hours):
        """진료시간과 접수시간 통합"""
        if not treatment_hours or all(v is None for v in treatment_hours.values()):
            if reception_hours and 'weekday' in reception_hours:
                weekday_reception = reception_hours['weekday']
                if weekday_reception:
                    return {
                        'mon': weekday_reception,
                        'tue': weekday_reception,
                        'wed': weekday_reception,
                        'thu': weekday_reception,
                        'fri': weekday_reception
                    }
        return treatment_hours
    
    def get_hospital_state(self, hospital, current_time):
        """병원의 현재 영업 상태를 확인"""
        # 모든 시간 정보가 없는 경우 체크
        has_any_hours = (
            (hospital.weekday_hours and any(hospital.weekday_hours.values())) or
            hospital.saturday_hours or
            hospital.sunday_hours or
            (hospital.reception_hours and any(hospital.reception_hours.values()))
        )
        
        if not has_any_hours:
            return "확인요망"  # 4글자로 통일된 상태 메시지
        
        weekday = current_time.weekday()
        weekday_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri'}
        
        # 통합된 시간 정보 생성
        merged_weekday_hours = self.merge_hours(hospital.weekday_hours, hospital.reception_hours)
        
        # 일요일
        if weekday == 6:
            if hospital.sunday_closed:
                return "영업종료"
            hours = hospital.sunday_hours
        # 토요일
        elif weekday == 5:
            hours = hospital.saturday_hours or (hospital.reception_hours or {}).get('saturday')
            lunch_key = 'saturday'
        # 평일
        else:
            day_key = weekday_map[weekday]
            hours = merged_weekday_hours.get(day_key) if merged_weekday_hours else None
            lunch_key = 'weekday'
        
        if not hours:
            return "영업종료"
            
        try:
            # 시간 정규화 및 비교
            current_time_only = current_time.time()
            start_time = datetime.strptime(normalize_time(hours['start']), '%H:%M').time()
            end_time = datetime.strptime(normalize_time(hours['end']), '%H:%M').time()
            
            # 점심시간 체크 (평일/토요일 구분)
            if hospital.lunch_time and lunch_key in hospital.lunch_time:
                lunch = hospital.lunch_time[lunch_key]
                if lunch:
                    try:
                        lunch_start = datetime.strptime(normalize_time(lunch['start']), '%H:%M').time()
                        lunch_end = datetime.strptime(normalize_time(lunch['end']), '%H:%M').time()
                        
                        # 점심시간이 1시~2시로 저장된 경우 13:00~14:00으로 변환
                        if lunch_start.hour < 12:
                            lunch_start = time(lunch_start.hour + 12, lunch_start.minute)
                            lunch_end = time(lunch_end.hour + 12, lunch_end.minute)
                        
                        if lunch_start <= current_time_only <= lunch_end:
                            return "점심시간"
                    except ValueError:
                        pass  # 점심시간 파싱 오류는 무시
            
            if start_time <= current_time_only <= end_time:
                return "영업중"
            return "영업종료"
            
        except ValueError as e:
            print(f"시간 파싱 오류: {e}")
            return "영업종료"  # 시간 형식 오류시 기본값
    
    
    def get(self, request):
        # 사용자 위치 정보 확인
        user_profile = request.user.profile
        if not (user_profile.latitude and user_profile.longitude):
            return Response({"error": "사용자의 위치 정보가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 검색 파라미터 (사용자 프로필에서 가져옴)
        user_lat = float(user_profile.latitude)
        user_lon = float(user_profile.longitude)
        radius = float(request.GET.get('radius', 3))  # km 단위
        
        # 현재 시간
        current_time = datetime.now()
        
        # 병원 조회 및 거리 계산
        hospitals = Hospital.objects.annotate(
            distance=ACos(
                Cos(Radians(user_lat)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(user_lon)) + 
                Sin(Radians(user_lat)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=radius).order_by('distance')
        
        results = []
        for hospital in hospitals:
            # 통합된 시간 정보 생성
            merged_weekday_hours = self.merge_hours(hospital.weekday_hours, hospital.reception_hours)
            
            results.append({
                'id': hospital.id,
                'name': hospital.name,
                'address': hospital.address,
                'phone': hospital.phone,
                'department': hospital.department,  # 기본: 모델 필드 그대로 반환 (필요시 문자열 변환 가능)
                'latitude': float(hospital.latitude),
                'longitude': float(hospital.longitude),
                'distance': float(hospital.distance),
                'weekday_hours': merged_weekday_hours,
                'saturday_hours': hospital.saturday_hours or (hospital.reception_hours or {}).get('saturday'),
                'sunday_hours': hospital.sunday_hours,
                'reception_hours': hospital.reception_hours,
                'lunch_time': hospital.lunch_time,
                'sunday_closed': hospital.sunday_closed,
                'holiday_info': hospital.holiday_info,
                'hospital_type': hospital.hospital_type,
                'state': self.get_hospital_state(hospital, current_time),
            })
        
        return Response({'count': len(results), 'results': results})


class OpenHospitalSearchView(HospitalSearchView):
    """현재 영업 중인 병원만 반환하는 API"""
    
    def get(self, request):
        # 사용자 위치 정보 확인
        user_profile = request.user.profile
        if not (user_profile.latitude and user_profile.longitude):
            return Response({"error": "사용자의 위치 정보가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 검색 파라미터
        user_lat = float(user_profile.latitude)
        user_lon = float(user_profile.longitude)
        radius = float(request.GET.get('radius', 3))  # km 단위
        
        # 현재 시간
        current_time = datetime.now()
        
        # 병원 조회 및 거리 계산
        hospitals = Hospital.objects.annotate(
            distance=ACos(
                Cos(Radians(user_lat)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(user_lon)) + 
                Sin(Radians(user_lat)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=radius).order_by('distance')
        
        results = []
        for hospital in hospitals:
            state = self.get_hospital_state(hospital, current_time)
            # 영업중인 병원만 포함
            if state == "영업중":
                merged_weekday_hours = self.merge_hours(hospital.weekday_hours, hospital.reception_hours)
                
                results.append({
                    'id': hospital.id,
                    'name': hospital.name,
                    'address': hospital.address,
                    'phone': hospital.phone,
                    'department': hospital.department,
                    'latitude': float(hospital.latitude),
                    'longitude': float(hospital.longitude),
                    'distance': float(hospital.distance),
                    'weekday_hours': merged_weekday_hours,
                    'saturday_hours': hospital.saturday_hours or (hospital.reception_hours or {}).get('saturday'),
                    'sunday_hours': hospital.sunday_hours,
                    'reception_hours': hospital.reception_hours,
                    'lunch_time': hospital.lunch_time,
                    'sunday_closed': hospital.sunday_closed,
                    'holiday_info': hospital.holiday_info,
                    'hospital_type': hospital.hospital_type,
                    'state': state,
                })
        
        return Response({'count': len(results), 'results': results})


class NearbyHospitalAPIView(APIView):
    """사용자 위치 기반 근처 병원 목록 (상세 정보 포함)"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="근처 병원 목록 조회",
        operation_description="사용자 위치 기반으로 근처 병원 목록을 반환합니다. (상세 정보 포함)",
        tags=['hospital'],
        responses={
            200: openapi.Response(
                description="성공적으로 병원 목록을 반환",
            ),
            400: "사용자의 위치 정보가 없습니다."
        },
        operation_id='nearby_hospital_list'
    )
    def get(self, request):
        # 사용자 위치 정보 확인
        user_profile = request.user.profile
        if not (user_profile.latitude and user_profile.longitude):
            return Response({"error": "사용자의 위치 정보가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 검색 파라미터
        user_lat = float(user_profile.latitude)
        user_lon = float(user_profile.longitude)
        radius = float(request.GET.get('radius', 3))  # km 단위
        current_time = datetime.now()
        
        # 병원 조회 및 거리 계산
        hospitals = Hospital.objects.annotate(
            distance=ACos(
                Cos(Radians(user_lat)) *
                Cos(Radians(F('latitude'))) *
                Cos(Radians(F('longitude')) - Radians(user_lon)) +
                Sin(Radians(user_lat)) *
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=radius).order_by('distance')
        
        results = []
        # HospitalSearchView의 메서드를 재사용하기 위해 인스턴스 생성
        base_view = HospitalSearchView()
        
        for hospital in hospitals:
            # 진료시간/접수시간 통합
            merged_weekday_hours = base_view.merge_hours(hospital.weekday_hours, hospital.reception_hours)
            # 병원의 현재 영업 상태 확인
            state = base_view.get_hospital_state(hospital, current_time)
            
            # 진료과목 처리 수정
            department_str = hospital.department if hasattr(hospital, 'department') else ""
            
            hospital_data = {
                'id': hospital.id,
                'name': hospital.name,
                'address': hospital.address,
                'phone': hospital.phone,
                'department': department_str,
                'latitude': float(hospital.latitude),
                'longitude': float(hospital.longitude),
                'distance': float(hospital.distance),
                'weekday_hours': merged_weekday_hours,
                'saturday_hours': hospital.saturday_hours or (hospital.reception_hours or {}).get('saturday'),
                'sunday_hours': hospital.sunday_hours,
                'reception_hours': hospital.reception_hours,
                'lunch_time': hospital.lunch_time,
                'sunday_closed': hospital.sunday_closed,
                'holiday_info': hospital.holiday_info,
                'hospital_type': hospital.hospital_type if hospital.hospital_type else "일반의원",
                'state': state,
            }
            
            results.append(hospital_data)
        
        return Response({'count': len(results), 'results': results})
