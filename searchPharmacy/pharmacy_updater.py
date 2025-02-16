import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def fetch_total_count():
    """전체 약국 수를 조회하는 함수"""
    url = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyFullDown"
    service_key = os.getenv("PHARMACY_API_KEY")
    
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 1,
        "type": "xml"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            total_count = int(root.find(".//totalCount").text)
            return total_count
    except Exception as e:
        print(f"전체 수 조회 중 오류 발생: {str(e)}")
        return None

def fetch_pharmacies(page_no, num_of_rows=1000):
    """특정 페이지의 약국 정보를 가져오는 함수"""
    url = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyFullDown"
    service_key = os.getenv("PHARMACY_API_KEY")
    
    params = {
        "serviceKey": service_key,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "type": "xml"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall(".//item")
            
            pharmacies = []
            for item in items:
                pharmacy = {
                    "name": item.findtext("dutyName", "정보없음"),
                    "addr": item.findtext("dutyAddr", "정보없음"),
                    "tel": item.findtext("dutyTel1", "정보없음"),
                    "fax": item.findtext("dutyFax", "정보없음"),
                    "lat": float(item.findtext("wgs84Lat", "0")),
                    "lon": float(item.findtext("wgs84Lon", "0")),
                    "map_info": item.findtext("dutyMapimg", ""),
                    "etc": item.findtext("dutyEtc", ""),
                }
                
                # 운영시간 처리
                operating_hours = {}
                days = ["월", "화", "수", "목", "금", "토", "일"]
                for i, day in enumerate(days, 1):
                    start = item.findtext(f"dutyTime{i}s", "")
                    end = item.findtext(f"dutyTime{i}c", "")
                    if start and end:
                        operating_hours[day] = {
                            "start": start,
                            "end": end,
                            "formatted": f"{start[:2]}:{start[2:]} - {end[:2]}:{end[2:]}"
                        }
                    else:
                        operating_hours[day] = {
                            "start": "",
                            "end": "",
                            "formatted": "정보없음"
                        }
                
                pharmacy["operating_hours"] = operating_hours
                pharmacies.append(pharmacy)
                
            return pharmacies
    except Exception as e:
        print(f"데이터 조회 중 오류 발생: {str(e)}")
        return None

def fetch_all_pharmacies():
    """전체 약국 정보를 수집하는 메인 함수"""
    print("전체 약국 수 조회 중...")
    total_count = fetch_total_count()
    
    if not total_count:
        print("전체 약국 수 조회 실패")
        return None
    
    print(f"총 {total_count}개의 약국이 있습니다.")
    
    # 페이지 계산
    num_of_rows = 1000  # 한 번에 가져올 데이터 수
    total_pages = (total_count + num_of_rows - 1) // num_of_rows
    
    all_pharmacies = []
    
    for page in range(1, total_pages + 1):
        print(f"\n{page}/{total_pages} 페이지 처리 중... ({len(all_pharmacies)}/{total_count})")
        
        pharmacies = fetch_pharmacies(page, num_of_rows)
        if pharmacies:
            all_pharmacies.extend(pharmacies)
            print(f"- {len(pharmacies)}개 데이터 추가됨")
        else:
            print(f"- {page} 페이지 데이터 조회 실패")
    
    print(f"\n전체 {len(all_pharmacies)}개의 약국 정보 수집 완료!")
    return all_pharmacies

if __name__ == "__main__":
    pharmacies = fetch_all_pharmacies()
    
    if pharmacies:
        # 수집된 데이터 샘플 출력
        print("\n처음 5개 약국 정보:")
        for pharmacy in pharmacies[:5]:
            print("\n" + "="*50)
            print(f"약국명: {pharmacy['name']}")
            print(f"주소: {pharmacy['addr']}")
            print(f"전화: {pharmacy['tel']}")
            print(f"위치: 위도 {pharmacy['lat']}, 경도 {pharmacy['lon']}")
            print("\n운영시간:")
            for day, hours in pharmacy['operating_hours'].items():
                print(f"  {day}: {hours['formatted']}") 