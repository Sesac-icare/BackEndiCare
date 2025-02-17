from django.core.management.base import BaseCommand
import requests
import xml.etree.ElementTree as ET
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from django.db import transaction
from searchHospital.models import Hospital
from searchHospital.data_processor import (
    process_treatment_hours,
    process_reception_hours,
    process_lunch_time,
    process_holiday_info,
    classify_hospitals_batch
)
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class Command(BaseCommand):
    help = '공공데이터 포털 API에서 병원 데이터를 수집하고 DB에 저장'

    # API 설정을 클래스 속성으로 이동
    BASIS_URL = "http://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
    DETAIL_URL = "http://apis.data.go.kr/B551182/MadmDtlInfoService2.7/getDtlInfo2.7"
    DGSBJT_URL = "http://apis.data.go.kr/B551182/MadmDtlInfoService2.7/getDgsbjtInfo2.7"
    API_KEY = os.getenv('HOSPITAL_API_KEY')

    def add_arguments(self, parser):
        parser.add_argument(
            '--regions',
            nargs='+',
            default=['서울'],
            help='수집할 지역 목록 (예: 서울 경기)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=400,
            help='한 번에 처리할 병원 수 (기본값: 400)'
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=20,
            help='동시 처리할 작업자 수 (기본값: 20)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='기존 데이터를 모두 삭제하고 새로 로드'
        )

    def fetch_hospitals_by_region(self, region: str) -> List[Dict]:
        """지역별 병원 기본 정보 수집"""
        hospitals = []
        page = 1
        
        while True:
            params = {
                "ServiceKey": self.API_KEY,
                "pageNo": str(page),
                "numOfRows": "1000",
                "sidoCd": "110000" if region == "서울" else "310000"  # 서울:110000, 경기:310000
            }
            
            try:
                response = requests.get(self.BASIS_URL, params=params)
                root = ET.fromstring(response.content)
                
                items = root.findall(".//item")
                if not items:  # 더 이상 데이터가 없으면 종료
                    break
                    
                for item in root.findall(".//item"):
                    hospital = {
                        "ykiho": item.findtext("ykiho", ""),
                        "name": item.findtext("yadmNm", ""),
                        "address": item.findtext("addr", ""),
                        "phone": item.findtext("telno", ""),
                        "latitude": float(item.findtext("YPos", "0")),
                        "longitude": float(item.findtext("XPos", "0")),
                    }
                    if hospital["ykiho"]:  # ykiho가 있는 경우만 추가
                        hospitals.append(hospital)
                
                self.stdout.write(f"{region} 지역 {page}페이지 처리 완료 (병원 수: {len(hospitals)})")
                page += 1
                time.sleep(0.5)  # API 호출 제한 고려
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error fetching {region} page {page}: {str(e)}"))
                break
        
        return hospitals

    def fetch_hospital_details(self, ykiho: str) -> Dict:
        """병원 상세 정보 수집"""
        params = {"ServiceKey": self.API_KEY, "ykiho": ykiho}
        
        try:
            response = requests.get(self.DETAIL_URL, params=params)
            root = ET.fromstring(response.content)
            item = root.find(".//item")
            
            if item is not None:
                return {
                    # 진료시간 (월~일)
                    "trmtMonStart": item.findtext("trmtMonStart", ""),
                    "trmtMonEnd": item.findtext("trmtMonEnd", ""),
                    "trmtTueStart": item.findtext("trmtTueStart", ""),
                    "trmtTueEnd": item.findtext("trmtTueEnd", ""),
                    "trmtWedStart": item.findtext("trmtWedStart", ""),
                    "trmtWedEnd": item.findtext("trmtWedEnd", ""),
                    "trmtThuStart": item.findtext("trmtThuStart", ""),
                    "trmtThuEnd": item.findtext("trmtThuEnd", ""),
                    "trmtFriStart": item.findtext("trmtFriStart", ""),
                    "trmtFriEnd": item.findtext("trmtFriEnd", ""),
                    "trmtSatStart": item.findtext("trmtSatStart", ""),
                    "trmtSatEnd": item.findtext("trmtSatEnd", ""),
                    "trmtSunStart": item.findtext("trmtSunStart", ""),
                    "trmtSunEnd": item.findtext("trmtSunEnd", ""),
                    
                    # 점심시간
                    "lunchWeek": item.findtext("lunchWeek", ""),
                    "lunchSat": item.findtext("lunchSat", ""),
                    
                    # 접수시간
                    "rcvWeek": item.findtext("rcvWeek", ""),
                    "rcvSat": item.findtext("rcvSat", ""),
                    
                    # 휴무일 정보
                    "noTrmtSun": item.findtext("noTrmtSun", ""),
                    "noTrmtHoli": item.findtext("noTrmtHoli", ""),
                }
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching details for {ykiho}: {str(e)}"))
        
        return {}

    def fetch_hospital_departments(self, ykiho: str) -> List[Dict]:
        """병원 진료과목 정보 수집"""
        params = {"ServiceKey": self.API_KEY, "ykiho": ykiho}
        departments = []
        
        try:
            response = requests.get(self.DGSBJT_URL, params=params)
            root = ET.fromstring(response.content)
            
            for item in root.findall(".//item"):
                dept = {
                    "code": item.findtext("dgsbjtCd", ""),
                    "name": item.findtext("dgsbjtCdNm", ""),
                    "doctor_count": int(item.findtext("dgsbjtPrSdrCnt", "0"))
                }
                departments.append(dept)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching departments for {ykiho}: {str(e)}"))
        
        return departments

    def process_hospital_batch(self, hospitals: List[Dict], executor: ThreadPoolExecutor) -> List[Dict]:
        """병원 배치 처리 (상세 정보와 진료과목 정보 추가)"""
        
        def fetch_all_info(hospital: Dict) -> Dict:
            """한 병원의 모든 정보를 한번에 수집"""
            try:
                details = self.fetch_hospital_details(hospital["ykiho"])
                departments = self.fetch_hospital_departments(hospital["ykiho"])
                return {
                    **hospital,
                    "details": details,
                    "departments": departments
                }
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {hospital['name']}: {str(e)}"))
                return hospital

        # 모든 병원 정보를 동시에 요청
        futures = [executor.submit(fetch_all_info, hospital) for hospital in hospitals]
        return [future.result() for future in as_completed(futures)]

    def save_to_db(self, hospitals_data: List[Dict]):
        """수집한 병원 데이터를 DB에 저장"""
        created_count = 0
        updated_count = 0
        
        try:
            with transaction.atomic():
                # 병원 유형 분류
                hospitals_for_gpt = [(h['name'], 
                    ', '.join([f"{d['name']}({d['doctor_count']}명)" 
                        for d in h['departments']]))
                    for h in hospitals_data]
                
                hospital_types = classify_hospitals_batch(hospitals_for_gpt)
                
                for hospital in hospitals_data:
                    try:
                        # 진료시간 처리
                        weekday_hours, saturday_hours, sunday_hours = process_treatment_hours(hospital['details'])
                        
                        # 휴무일 정보 처리
                        holiday_data = process_holiday_info(hospital['details'])
                        
                        # 병원 유형
                        hospital_type = hospital_types.get(hospital['name'], "일반의원")
                        
                        # DB 업데이트 또는 생성
                        db_hospital, created = Hospital.objects.update_or_create(
                            ykiho=hospital['ykiho'],
                            defaults={
                                'name': hospital['name'],
                                'address': hospital['address'],
                                'phone': hospital['phone'],
                                'latitude': float(hospital['latitude']),
                                'longitude': float(hospital['longitude']),
                                'department': ', '.join([f"{d['name']}({d['doctor_count']}명)" 
                                    for d in hospital['departments']]),
                                'hospital_type': hospital_type,
                                'weekday_hours': weekday_hours,
                                'saturday_hours': saturday_hours,
                                'sunday_hours': sunday_hours,
                                'reception_hours': process_reception_hours(hospital['details']),
                                'lunch_time': process_lunch_time(hospital['details']),
                                'sunday_closed': holiday_data['sunday_closed'],
                                'holiday_info': holiday_data['holiday_info'],
                            }
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                            
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"병원 데이터 저장 중 오류 ({hospital['name']}): {str(e)}")
                        )
                        continue
                        
            return created_count, updated_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"DB 저장 중 오류 발생: {str(e)}"))
            raise

    def handle(self, *args, **options):
        start_time = time.time()
        
        try:
            if options['force']:
                self.stdout.write('기존 데이터 삭제 중...')
                Hospital.objects.all().delete()
            
            all_hospitals = []
            
            # 데이터 수집
            with ThreadPoolExecutor(max_workers=options['workers']) as executor:
                for region in options['regions']:
                    self.stdout.write(f"\n{region} 지역 병원 수집 시작...")
                    hospitals = self.fetch_hospitals_by_region(region)
                    self.stdout.write(f"{region} 지역 총 {len(hospitals)}개 병원 기본 정보 수집 완료")
                    
                    for i in range(0, len(hospitals), options['batch_size']):
                        batch = hospitals[i:i+options['batch_size']]
                        self.stdout.write(f"\n배치 처리 중... ({i+1}-{i+len(batch)}/{len(hospitals)})")
                        processed_batch = self.process_hospital_batch(batch, executor)
                        all_hospitals.extend(processed_batch)
                        
                        progress = ((i+len(batch))/len(hospitals))*100
                        self.stdout.write(f"진행률: {progress:.1f}%")
            
            # DB 저장
            self.stdout.write("\nDB 저장 시작...")
            created, updated = self.save_to_db(all_hospitals)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n처리 완료!\n"
                    f"총 병원 수: {len(all_hospitals)}\n"
                    f"새로 생성: {created}개\n"
                    f"업데이트: {updated}개"
                )
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"오류 발생: {str(e)}"))
            
        finally:
            end_time = time.time()
            self.stdout.write(
                self.style.SUCCESS(f"총 처리 시간: {end_time - start_time:.2f}초")
            ) 