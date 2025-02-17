import json
import openpyxl
from geopy.distance import geodesic
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import F, Q
from django.db.models.functions import ACos, Cos, Radians, Sin
from datetime import datetime, time
from math import radians
import re
import math

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.contrib.auth.hashers import make_password

from .models import Hospital
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


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
    except:
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
            current_time = current_time.time()
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
                        
                        if lunch_start <= current_time <= lunch_end:
                            return "점심시간"
                    except ValueError:
                        pass  # 점심시간 파싱 오류는 무시
            
            if start_time <= current_time <= end_time:
                return "영업중"
            return "영업종료"
            
        except ValueError as e:
            print(f"시간 파싱 오류: {e}")
            return "영업종료"  # 시간 형식 오류시 기본값
    
    
    def get(self, request):
        # 사용자 위치 정보 확인
        user_profile = request.user.profile
        if not (user_profile.latitude and user_profile.longitude):
            return Response(
                {"error": "사용자의 위치 정보가 없습니다."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        ).filter(
            distance__lte=radius
        ).order_by('distance')
        
        results = []
        for hospital in hospitals:
            # 통합된 시간 정보 생성
            merged_weekday_hours = self.merge_hours(hospital.weekday_hours, hospital.reception_hours)
            
            results.append({
                'id': hospital.id,
                'name': hospital.name,
                'address': hospital.address,
                'phone': hospital.phone,
                'department': hospital.department,
                'latitude': float(hospital.latitude),
                'longitude': float(hospital.longitude),
                'distance': hospital.distance,
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
        
        return Response({
            'count': len(results),
            'results': results
        })

class OpenHospitalSearchView(HospitalSearchView):
    """현재 영업 중인 병원만 반환하는 API"""
    
    def get(self, request):
        # 사용자 위치 정보 확인
        user_profile = request.user.profile
        if not (user_profile.latitude and user_profile.longitude):
            return Response(
                {"error": "사용자의 위치 정보가 없습니다."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        ).filter(
            distance__lte=radius
        ).order_by('distance')
        
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
                    'distance': hospital.distance,
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
        
        return Response({
            'count': len(results),
            'results': results
        })


class NearbyPharmacyView(APIView):
    """가까운 약국 목록을 반환하는 API"""
    permission_classes = [IsAuthenticated]
    
    def get_pharmacy_state(self, pharmacy, current_time):
        """약국의 현재 영업 상태를 확인"""
        weekday = current_time.weekday()
        
        # 시간 정보가 없는 경우
        if not any([pharmacy.mon_start, pharmacy.tue_start, pharmacy.wed_start, 
                   pharmacy.thu_start, pharmacy.fri_start, pharmacy.sat_start, 
                   pharmacy.sun_start]):
            return "확인요망"
        
        try:
            current_time = current_time.time()
            
            # 일요일
            if weekday == 6:
                if not pharmacy.sun_start or not pharmacy.sun_end:
                    return "영업종료"
                start_time = datetime.strptime(normalize_time(pharmacy.sun_start), '%H:%M').time()
                end_time = datetime.strptime(normalize_time(pharmacy.sun_end), '%H:%M').time()
            # 토요일
            elif weekday == 5:
                if not pharmacy.sat_start or not pharmacy.sat_end:
                    return "영업종료"
                start_time = datetime.strptime(normalize_time(pharmacy.sat_start), '%H:%M').time()
                end_time = datetime.strptime(normalize_time(pharmacy.sat_end), '%H:%M').time()
            # 평일
            else:
                day_map = {
                    0: (pharmacy.mon_start, pharmacy.mon_end),
                    1: (pharmacy.tue_start, pharmacy.tue_end),
                    2: (pharmacy.wed_start, pharmacy.wed_end),
                    3: (pharmacy.thu_start, pharmacy.thu_end),
                    4: (pharmacy.fri_start, pharmacy.fri_end),
                }
                start, end = day_map[weekday]
                if not start or not end:
                    return "영업종료"
                start_time = datetime.strptime(normalize_time(start), '%H:%M').time()
                end_time = datetime.strptime(normalize_time(end), '%H:%M').time()
            
            if start_time <= current_time <= end_time:
                return "영업중"
            return "영업종료"
            
        except ValueError as e:
            print(f"시간 파싱 오류: {e}")
            return "영업종료"
    
    def get(self, request):
        from searchPharmacy.models import Pharmacy
        
        # 사용자 위치 정보 확인
        user_profile = request.user.profile
        if not (user_profile.latitude and user_profile.longitude):
            return Response(
                {"error": "사용자의 위치 정보가 없습니다."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 검색 파라미터
        user_lat = float(user_profile.latitude)
        user_lon = float(user_profile.longitude)
        radius = float(request.GET.get('radius', 3))  # km 단위
        current_time = datetime.now()
        
        # 약국 조회 및 거리 계산
        pharmacies = Pharmacy.objects.annotate(
            distance=ACos(
                Cos(Radians(user_lat)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(user_lon)) + 
                Sin(Radians(user_lat)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(
            distance__lte=radius
        ).order_by('distance')
        
        results = []
        for pharmacy in pharmacies:
            results.append({
                'id': pharmacy.id,
                'name': pharmacy.name,
                'address': pharmacy.address,
                'tel': pharmacy.tel,
                'fax': pharmacy.fax,
                'latitude': float(pharmacy.latitude),
                'longitude': float(pharmacy.longitude),
                'distance': pharmacy.distance,
                'weekday_hours': {
                    'mon': {'start': pharmacy.mon_start, 'end': pharmacy.mon_end},
                    'tue': {'start': pharmacy.tue_start, 'end': pharmacy.tue_end},
                    'wed': {'start': pharmacy.wed_start, 'end': pharmacy.wed_end},
                    'thu': {'start': pharmacy.thu_start, 'end': pharmacy.thu_end},
                    'fri': {'start': pharmacy.fri_start, 'end': pharmacy.fri_end},
                },
                'saturday_hours': {
                    'start': pharmacy.sat_start,
                    'end': pharmacy.sat_end
                },
                'sunday_hours': {
                    'start': pharmacy.sun_start,
                    'end': pharmacy.sun_end
                },
                'state': self.get_pharmacy_state(pharmacy, current_time),
                'map_info': pharmacy.map_info,
                'etc': pharmacy.etc,
                'last_updated': pharmacy.last_updated.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return Response({
            'count': len(results),
            'results': results
        })
