import os
import sys

# Django 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'icare.settings')
django.setup()

import re
from datetime import datetime, timedelta
from typing import Dict, List, Union
from holidayskr import is_holiday
import pandas as pd
import json
import time
from django.db import transaction
from searchHospital.models import Hospital
from openai import OpenAI

def process_treatment_hours(row):
    """진료시간 처리"""
    weekday_result = {}
    saturday_result = None
    sunday_result = None
    
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    weekday_keys = ['mon', 'tue', 'wed', 'thu', 'fri']  # 영문 키 사용
    
    for eng_day, key in zip(days[:5], weekday_keys):  # 평일만 처리
        start = str(row.get(f'trmt{eng_day}Start', ''))
        end = str(row.get(f'trmt{eng_day}End', ''))
        
        if len(start) == 4 and len(end) == 4:
            time_info = {
                'start': f"{start[:2]}:{start[2:]}",
                'end': f"{end[:2]}:{end[2:]}"
            }
            weekday_result[key] = time_info
        else:
            weekday_result[key] = None
    
    # 토요일 처리
    sat_start = str(row.get('trmtSatStart', ''))
    sat_end = str(row.get('trmtSatEnd', ''))
    if len(sat_start) == 4 and len(sat_end) == 4:
        saturday_result = {
            'start': f"{sat_start[:2]}:{sat_start[2:]}",
            'end': f"{sat_end[:2]}:{sat_end[2:]}"
        }
    
    # 일요일 처리
    sun_start = str(row.get('trmtSunStart', ''))
    sun_end = str(row.get('trmtSunEnd', ''))
    if len(sun_start) == 4 and len(sun_end) == 4:
        sunday_result = {
            'start': f"{sun_start[:2]}:{sun_start[2:]}",
            'end': f"{sun_end[:2]}:{sun_end[2:]}"
        }
    
    return weekday_result, saturday_result, sunday_result

def process_reception_hours(row):
    """접수시간 처리"""
    result = {
        'weekday': None,
        'saturday': None
    }
    
    # 평일 접수시간
    rcv_week = str(row.get('rcvWeek', ''))
    if rcv_week and '정보없음' not in rcv_week:
        time_match = re.findall(
            r'(\d{1,2})시?(\d{1,2})?분?~(\d{1,2})시?(\d{1,2})?분?',
            rcv_week.replace(' ', '')
        )
        if time_match:
            start_h, start_m, end_h, end_m = time_match[0]
            result['weekday'] = {
                'start': f"{int(start_h):02d}:{int(start_m or 0):02d}",
                'end': f"{int(end_h):02d}:{int(end_m or 0):02d}"
            }
    
    # 토요일 접수시간
    rcv_sat = str(row.get('rcvSat', ''))
    if rcv_sat and '정보없음' not in rcv_sat:
        time_match = re.findall(
            r'(\d{1,2})시?(\d{1,2})?분?~(\d{1,2})시?(\d{1,2})?분?',
            rcv_sat.replace(' ', '')
        )
        if time_match:
            start_h, start_m, end_h, end_m = time_match[0]
            result['saturday'] = {
                'start': f"{int(start_h):02d}:{int(start_m or 0):02d}",
                'end': f"{int(end_h):02d}:{int(end_m or 0):02d}"
            }
    
    return result

def process_lunch_time(row):
    """점심시간 처리"""
    result = {
        'weekday': None,
        'saturday': None
    }
    
    # 평일 점심시간
    lunch_week = str(row.get('lunchWeek', ''))
    if lunch_week and '정보없음' not in lunch_week:
        time_match = re.findall(
            r'(\d{1,2})시?(\d{1,2})?분?~(\d{1,2})시?(\d{1,2})?분?',
            lunch_week.replace(' ', '')
        )
        if time_match:
            start_h, start_m, end_h, end_m = time_match[0]
            result['weekday'] = {
                'start': f"{int(start_h):02d}:{int(start_m or 0):02d}",
                'end': f"{int(end_h):02d}:{int(end_m or 0):02d}"
            }
    
    # 토요일 점심시간
    lunch_sat = str(row.get('lunchSat', ''))
    if lunch_sat and '정보없음' not in lunch_sat:
        time_match = re.findall(
            r'(\d{1,2})시?(\d{1,2})?분?~(\d{1,2})시?(\d{1,2})?분?',
            lunch_sat.replace(' ', '')
        )
        if time_match:
            start_h, start_m, end_h, end_m = time_match[0]
            result['saturday'] = {
                'start': f"{int(start_h):02d}:{int(start_m or 0):02d}",
                'end': f"{int(end_h):02d}:{int(end_m or 0):02d}"
            }
    
    return result

def process_holiday_info(row):
    """휴무일 정보 처리"""
    result = {
        'sunday_closed': False,
        'holiday_info': {
            'fully_closed': False,  # 완전 휴무
            'partially_closed': False,  # 부분 휴무
            'closed_hours': None,  # 휴무 시간
            'special_holidays': []  # 특별 휴무일 (명절 등)
        }
    }
    
    # 일요일 휴무 처리
    sunday_info = str(row.get('noTrmtSun', ''))
    result['sunday_closed'] = '휴진' in sunday_info or '휴무' in sunday_info
    
    # 공휴일 휴무 처리
    holiday_info = str(row.get('noTrmtHoli', ''))
    
    if holiday_info:
        # 완전 휴무 체크
        if any(keyword in holiday_info for keyword in ['전부휴진', '전체휴무', '종일휴진']):
            result['holiday_info']['fully_closed'] = True
        
        # 부분 휴무 체크 (시간 포함)
        time_match = re.search(r'(\d{1,2})시\s*(이?후|부터)?\s*휴[진무]', holiday_info)
        if time_match:
            result['holiday_info']['partially_closed'] = True
            result['holiday_info']['closed_hours'] = f"{int(time_match.group(1)):02d}:00"
        
        # 특별 휴무일 체크
        special_days = []
        if '명절' in holiday_info:
            special_days.append('명절')
        if '어린이날' in holiday_info:
            special_days.append('어린이날')
        if '크리스마스' in holiday_info:
            special_days.append('크리스마스')
        if '신정' in holiday_info or '신년' in holiday_info:
            special_days.append('신정')
        
        result['holiday_info']['special_holidays'] = special_days
    
    return result

def normalize_hospital_type(hospital_type):
    """병원 유형 정규화"""
    # 공백 제거 및 소문자 변환
    hospital_type = hospital_type.strip().lower()
    
    # '-' 뒤의 과목만 추출
    if ' - ' in hospital_type:
        hospital_type = hospital_type.split(' - ')[1].strip()
    
    # 매핑 테이블
    type_mapping = {
        '종합병원': '종합병원',
        '내과의원': '내과',
        '내과': '내과',
        '소아청소년과의원': '소아청소년과',
        '소아과의원': '소아청소년과',
        '소아청소년과': '소아청소년과',
        '가정의학과의원': '가정의학과',
        '가정의학과': '가정의학과',
        '이비인후과의원': '이비인후과',
        '이비인후과': '이비인후과',
        '정형외과의원': '정형외과',
        '정형외과': '정형외과',
        '피부과의원': '피부과',
        '피부과': '피부과',
        '안과의원': '안과',
        '안과': '안과',
        '치과의원': '치과',
        '치과': '치과',
        '한의원': '한방병원',
        '한방병원': '한방병원',
        '산부인과의원': '산부인과',
        '산부인과': '산부인과',
        '정신건강의학과의원': '정신건강의학과',
        '정신건강의학과': '정신건강의학과',
        '성형외과의원': '성형외과',
        '성형외과': '성형외과',
        '신경외과의원': '신경외과',
        '신경외과': '신경외과',
    }
    
    # 매핑된 값이 있으면 반환, 없으면 '일반의원' 반환
    return type_mapping.get(hospital_type, '일반의원')

def classify_hospitals_batch(hospitals_data, batch_size=50):
    """병원 데이터를 배치로 처리하여 유형 분류"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    results = {}
    total_batches = (len(hospitals_data) + batch_size - 1) // batch_size
    
    print(f"\n총 {len(hospitals_data)}개 병원 분류 시작 (배치 크기: {batch_size})")
    print("="*50)
    
    # 배치 단위로 처리
    for i in range(0, len(hospitals_data), batch_size):
        current_batch = i // batch_size + 1
        batch = hospitals_data[i:i+batch_size]
        
        print(f"\n배치 {current_batch}/{total_batches} 처리 중...")
        print(f"처리 범위: {i+1}~{min(i+batch_size, len(hospitals_data))} / {len(hospitals_data)}")
        
        # 현재 배치의 병원 목록 출력
        print("\n현재 배치 병원 목록:")
        for idx, (name, _) in enumerate(batch, 1):
            print(f"{idx}. {name}")
        
        prompt = "다음 병원들의 유형을 분류해주세요:\n\n"
        
        for idx, (name, departments) in enumerate(batch, 1):
            prompt += f"병원 {idx}:\n이름: {name}\n진료과목: {departments}\n\n"
        
        prompt += """
각 병원에 대해 다음 중 하나의 유형을 선택하여 답변해주세요:
1. 종합병원
2. 내과
3. 소아청소년과
4. 가정의학과
5. 이비인후과
6. 정형외과
7. 피부과
8. 안과
9. 치과
10. 한방병원
11. 산부인과
12. 정신건강의학과
13. 일반의원
14. 성형외과
15. 신경외과

답변 형식:
병원 1: 과목명만 작성
병원 2: 과목명만 작성
...

예시:
병원 1: 내과
병원 2: 종합병원
병원 3: 소아청소년과

주의사항:
- 병원명은 제외하고 과목명만 답변
- 반드시 위 목록에서 하나만 선택
- 설명이나 부가 정보 없이 과목명만 작성

선택 기준:
- 여러 진료과목이 있고 의사 수가 많으면 '종합병원'
- 여러 진료과목이 있고 {name} 병원이 주력 과목이면 해당 과목
- 한의사나 한방 관련 과목이 있으면 '한방병원'
- 특정 과목이 주력이면 해당 과목
- 판단이 어려우면 '일반의원'
"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-16k",  # 더 긴 컨텍스트를 처리할 수 있는 모델
                messages=[
                    {"role": "system", "content": "병원 유형을 분류하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # 응답 파싱 및 결과 출력
            print("\n분류 결과:")
            response_lines = response.choices[0].message.content.strip().split('\n')
            for line in response_lines:
                if ':' in line:
                    idx_str, hospital_type = line.split(':')
                    idx = int(idx_str.replace('병원 ', '').strip()) - 1
                    if idx < len(batch):
                        hospital_name = batch[idx][0]
                        normalized_type = normalize_hospital_type(hospital_type.strip())
                        results[hospital_name] = normalized_type
                        print(f"{hospital_name}: {normalized_type}")
            
            print(f"\n진행률: {min(i+batch_size, len(hospitals_data))}/{len(hospitals_data)} ({(min(i+batch_size, len(hospitals_data))/len(hospitals_data)*100):.1f}%)")
            print("="*50)
            
        except Exception as e:
            print(f"\n배치 처리 중 오류 발생: {str(e)}")
            print("기본값 '일반의원'으로 처리합니다.")
            for name, _ in batch:
                results[name] = "일반의원"
                print(f"{name}: 일반의원")
    
    print("\n전체 병원 분류 완료!")
    return results

def process_hospitals_file(input_file: str, output_file: str):
    """병원 데이터를 전처리하고 엑셀과 DB에 저장"""
    print(f"데이터 파일 읽는 중: {input_file}")
    
    # JSON을 DataFrame으로 읽기
    df = pd.read_json(input_file)
    details_df = pd.json_normalize(df['details'].fillna({}))
    print(f"전체 {len(df)}개 병원 데이터 전처리 시작...")
    
    # 기본 정보 처리
    processed_df = pd.DataFrame({
        'ykiho': df['ykiho'],
        'name': df['name'],
        'address': df['address'],
        'phone': df['phone'],
        'latitude': df.apply(lambda x: float(x['latitude']), axis=1),
        'longitude': df.apply(lambda x: float(x['longitude']), axis=1),
        'departments': df['departments'].apply(
            lambda x: ', '.join([f"{d['name']}({d['doctor_count']}명)" for d in x]) if isinstance(x, list) else ''
        )
    })
    
    # 병원 데이터 배치 처리를 위한 준비
    hospitals_data = [(row['name'], row['departments']) for _, row in processed_df.iterrows()]
    hospital_types = classify_hospitals_batch(hospitals_data)
    
    # DB에 저장
    print("\nDB 저장 시작...")
    created_count = 0
    updated_count = 0
    
    try:
        with transaction.atomic():
            for _, row in processed_df.iterrows():
                try:
                    # 진료시간 처리
                    weekday_hours, saturday_hours, sunday_hours = process_treatment_hours(details_df.loc[_])
                    
                    # 휴무일 정보 처리
                    holiday_data = process_holiday_info(details_df.loc[_])
                    
                    # 미리 분류된 병원 유형 사용
                    hospital_type = hospital_types.get(row['name'], "일반의원")
                    
                    hospital, created = Hospital.objects.update_or_create(
                        ykiho=row['ykiho'],
                        defaults={
                            'name': row['name'],
                            'address': row['address'],
                            'phone': row['phone'],
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude']),
                            'department': row['departments'],
                            'hospital_type': hospital_type,
                            'weekday_hours': weekday_hours,
                            'saturday_hours': saturday_hours,
                            'sunday_hours': sunday_hours,
                            'reception_hours': process_reception_hours(details_df.loc[_]),
                            'lunch_time': process_lunch_time(details_df.loc[_]),
                            'sunday_closed': holiday_data['sunday_closed'],
                            'holiday_info': holiday_data['holiday_info'],
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    print(f"병원 데이터 저장 중 오류 ({row['name']}): {str(e)}")
                    continue

        print(f"DB 저장 완료! (생성: {created_count}개, 업데이트: {updated_count}개)")
        
    except Exception as e:
        print(f"DB 저장 중 오류 발생: {str(e)}")
        raise
    
    print("\n처리된 데이터 샘플 (상위 10개):")
    print("="*100)
    print(processed_df.head(10))
    print("="*100)
    print("\n처리 완료!")

if __name__ == "__main__":
    start_time = time.time()
    
    try:
        process_hospitals_file('seoul_gyeonggi_hospitals.json', 'processed_hospitals.xlsx')
    except Exception as e:
        print(f"오류 발생: {str(e)}")
    finally:
        end_time = time.time()
        print(f"총 처리 시간: {end_time - start_time:.2f}초") 