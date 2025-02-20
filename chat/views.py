import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
import os
from dotenv import load_dotenv
import openai
from typing import List, Dict
from django.db.models import F
from django.db.models.functions import ACos, Cos, Radians, Sin
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from drf_yasg.utils import swagger_auto_schema
import re
from datetime import datetime, time, timedelta
from rest_framework.permissions import IsAuthenticated
import json
from django.db.models import F
from django.db.models.functions import Radians, Sin, Cos, ACos
from datetime import datetime
import math
from gtts import gTTS
from google.cloud import speech
import base64
from dotenv import load_dotenv
import openai
import uuid
import tempfile
from langchain_core.messages import HumanMessage, AIMessage

# 올바른 앱에서 import
from searchHospital.models import Hospital
from searchPharmacy.models import Pharmacy

# 로그 설정
logger = logging.getLogger(__name__)
load_dotenv()

# OpenAI client 초기화
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# 음성을 텍스트로 변환하는 함수
def transcribe_speech(audio_file_path):
    """음성을 텍스트로 변환하는 함수"""
    speech_client = None
    try:
        speech_client = speech.SpeechClient()
        print("Speech client created")

        with open(audio_file_path, "rb") as audio_file:
            content = audio_file.read()
        print(f"Audio file read: {len(content)} bytes")

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="ko-KR",
            enable_automatic_punctuation=True,
            model="default"
        )
        print("Recognition config created")

        response = speech_client.recognize(config=config, audio=audio)
        print("Recognition response:", response)

        if not response.results:
            print("No transcription results")
            return None

        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
            print(f"Confidence: {result.alternatives[0].confidence}")

        return transcript.strip()

    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return None

    finally:
        # Speech 클라이언트 정리
        if speech_client:
            try:
                speech_client.transport.close()
            except Exception as e:
                print(f"Speech client cleanup error: {str(e)}")    
                
                
                
# 시간 관련 유틸리티 함수들
def normalize_time(time_str):
    """시간 문자열을 정규화"""
    try:
        time_str = re.sub(r'[가-힣]', '', time_str)
        time_str = time_str.strip()
        
        if time_str.startswith('24:'):
            return '00:00'
        elif time_str.startswith('30:'):
            return '18:00'
            
        return time_str
    except Exception:
        return '00:00'

def get_hospital_state(hospital, target_time=None):
    """병원의 영업 상태를 확인"""
    if target_time is None:
        target_time = datetime.now()
        
    weekday = target_time.weekday()
    target_time_str = target_time.strftime('%H%M')
    target_time_int = int(target_time_str)
    
    # 현재 시간과 비교
    current_time = datetime.now()
    if target_time <= current_time:
        return "영업종료"  # 현재 또는 과거 시간은 무조건 영업종료

    # 요일별 시간 처리
    if weekday == 6:  # 일요일
        if hospital.sunday_closed:
            return "영업종료"
        hours = hospital.sunday_hours
        lunch_key = 'sunday'
    elif weekday == 5:  # 토요일
        hours = hospital.saturday_hours or (hospital.reception_hours or {}).get('saturday')
        lunch_key = 'saturday'
    else:  # 평일
        day_key = ['mon', 'tue', 'wed', 'thu', 'fri'][weekday]
        hours = hospital.weekday_hours.get(day_key) if hospital.weekday_hours else None
        lunch_key = 'weekday'
    
    if not hours:
        return "영업종료"
        
    try:
        start_time = int(datetime.strptime(normalize_time(hours['start']), '%H:%M').strftime('%H%M'))
        end_time = int(datetime.strptime(normalize_time(hours['end']), '%H:%M').strftime('%H%M'))
        
        if start_time <= target_time_int <= end_time:
            # 점심시간 체크
            if hospital.lunch_time and lunch_key in hospital.lunch_time:
                lunch = hospital.lunch_time[lunch_key]
                if lunch:
                    lunch_start = int(datetime.strptime(normalize_time(lunch['start']), '%H:%M').strftime('%H%M'))
                    lunch_end = int(datetime.strptime(normalize_time(lunch['end']), '%H:%M').strftime('%H%M'))
                    
                    if lunch_start <= target_time_int <= lunch_end:
                        return "점심시간"
            return "영업중"
            
        return "영업종료"
        
    except ValueError:
        return "영업종료"

def parse_target_time(time_str: str) -> datetime:
    """
    시간 문자열을 파싱하여 datetime 객체로 변환
    
    Examples:
        - "내일 오전 10시"
        - "내일 아침"
        - "오후 2시"
        - "새벽"
        - "일찍"
        - "내일 오전"  # 추가
    """
    current_time = datetime.now()
    result_time = current_time
    
    try:
        # 날짜 처리
        if "내일" in time_str:
            result_time = current_time + timedelta(days=1)
        
        # 시간대 처리
        if "새벽" in time_str:
            result_time = result_time.replace(hour=6, minute=0)
        elif "일찍" in time_str or "아침" in time_str:
            result_time = result_time.replace(hour=8, minute=0)
        elif "오전" in time_str:
            # 구체적인 시간이 있는지 확인
            time_match = re.search(r'(\d+)시', time_str)
            if time_match:
                hour = int(time_match.group(1))
                result_time = result_time.replace(hour=hour, minute=0)
            else:
                # 구체적인 시간이 없으면 오전 9시로 설정
                result_time = result_time.replace(hour=9, minute=0)
        elif "오후" in time_str:
            time_match = re.search(r'(\d+)시', time_str)
            if time_match:
                hour = int(time_match.group(1))
                hour = hour + 12 if hour < 12 else hour
                result_time = result_time.replace(hour=hour, minute=0)
            else:
                # 구체적인 시간이 없으면 오후 2시로 설정
                result_time = result_time.replace(hour=14, minute=0)
        else:
            # 시간대 표현이 없으면 현재 시간 사용
            logger.info(f"No specific time period found in: {time_str}, using current time")
        
        logger.info(f"Parsed time string '{time_str}' to {result_time}")
        return result_time
        
    except Exception as e:
        logger.error(f"Time parsing error for '{time_str}': {str(e)}")
        return current_time

def get_hospital_opening_time(hospital, target_date):
    """병원의 영업 시작 시간을 가져옴"""
    weekday = target_date.weekday()
    
    try:
        if weekday == 6:  # 일요일
            if hospital.sunday_closed:
                return None
            hours = hospital.sunday_hours
        elif weekday == 5:  # 토요일
            hours = hospital.saturday_hours
        else:  # 평일
            day_key = ['mon', 'tue', 'wed', 'thu', 'fri'][weekday]
            hours = hospital.weekday_hours.get(day_key) if hospital.weekday_hours else None
            
        if not hours:
            return None
            
        return int(datetime.strptime(normalize_time(hours['start']), '%H:%M').strftime('%H%M'))
    except:
        return None

def get_hospital_closing_time(hospital, target_date):
    """병원의 영업 종료 시간을 가져옴"""
    weekday = target_date.weekday()
    
    try:
        if weekday == 6:  # 일요일
            if hospital.sunday_closed:
                return None
            hours = hospital.sunday_hours
        elif weekday == 5:  # 토요일
            hours = hospital.saturday_hours
        else:  # 평일
            day_key = ['mon', 'tue', 'wed', 'thu', 'fri'][weekday]
            hours = hospital.weekday_hours.get(day_key) if hospital.weekday_hours else None
            
        if not hours:
            return None
            
        return int(datetime.strptime(normalize_time(hours['end']), '%H:%M').strftime('%H%M'))
    except:
        return None

# 병원 검색 도구 개선
@tool
def search_hospital(query: str = "", latitude: float = None, longitude: float = None, target_time: str = None, sort_by: str = None) -> Dict:
    """
    병원 검색 도구
    Args:
        query: 검색어 (예: "이비인후과", "내과")
        latitude: 위도
        longitude: 경도
        target_time: 특정 시간 (예: "내일 오전 10시", "새벽", "일찍")
        sort_by: 정렬 기준 ("earliest_open" - 가장 빨리 여는 순, "latest_close" - 가장 늦게 닫는 순)
    """
    try:
        # 시간 처리
        current_time = datetime.now()
        target_date = current_time
        if target_time:
            target_date = parse_target_time(target_time)
            
        # 기본 쿼리
        hospitals = Hospital.objects.annotate(
            distance=ACos(
                Cos(Radians(latitude)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(longitude)) + 
                Sin(Radians(latitude)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=3)

        if query:
            hospitals = hospitals.filter(hospital_type__icontains=query)

        # 결과 처리
        results = []
        for hospital in hospitals:
            opening_time = get_hospital_opening_time(hospital, target_date)
            closing_time = get_hospital_closing_time(hospital, target_date)
            
            if opening_time is not None:  # 영업 시간 정보가 있는 경우만 포함
                state = get_hospital_state(hospital, target_date)
                hospital_data = {
                    'name': hospital.name,
                    'address': hospital.address,
                    'phone': hospital.phone,
                    'hospital_type': hospital.hospital_type,
                    'distance': f"{hospital.distance:.1f}km",
                    'state': state,
                    'opening_time': opening_time,
                    'closing_time': closing_time,
                    'weekday_hours': hospital.weekday_hours,
                    'saturday_hours': hospital.saturday_hours,
                    'sunday_hours': hospital.sunday_hours,
                    'lunch_time': hospital.lunch_time
                }
                results.append(hospital_data)

        # 정렬 처리
        time_description = "영업 중인"
        if sort_by == "earliest_open":
            results.sort(key=lambda x: x['opening_time'])
            time_description = "가장 빨리 여는"
        elif sort_by == "latest_close":
            results.sort(key=lambda x: x['closing_time'], reverse=True)
            time_description = "가장 늦게 닫는"
        else:
            results = [r for r in results if r['state'] in ["영업중", "점심시간"]]

        # 시간 표시 문자열 생성
        time_str = f"{target_date.strftime('%Y-%m-%d %H:%M')} 기준" if target_time else "현재"
        
        if not results:
            return {
                "type": "no_results",
                "start_message": f"죄송합니다. {time_str} {time_description} {query} 병원을 찾을 수 없습니다.",
                "end_message": "다른 시간대를 확인해보시거나, 직접 전화로 문의해보세요.",
                "data": []
            }

        return {
            "type": "hospital_list",
            "start_message": f"{time_str} {time_description} {query} 병원들입니다:",
            "end_message": "방문 전 전화로 확인하시는 것이 좋습니다.",
            "data": results[:5]
        }

    except Exception as e:
        logger.error(f"Hospital search error: {str(e)}")
        return {
            "type": "error",
            "start_message": "병원 검색 중 오류가 발생했습니다.",
            "end_message": "다시 시도해주세요.",
            "data": []
        }

#####################################################
# 약국
def haversine(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):  
        return float("inf")

    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def format_pharmacy_data(pharmacy, target_time=None):
    """약국 정보를 원하는 형식으로 변환"""
    if target_time is None:
        target_time = datetime.now()
    
    weekday = target_time.weekday()
    target_time_str = target_time.strftime('%H%M')
    target_time_int = int(target_time_str)
    
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
    
    # 현재 시간과 비교
    current_time = datetime.now()
    if target_time <= current_time:
        status = "영업종료"  # 현재 또는 과거 시간은 무조건 영업종료
    else:
        # 영업 상태 확인
        if start_time and end_time:
            try:
                start_int = int(start_time)
                end_int = int(end_time)
                
                if start_int <= target_time_int <= end_int:
                    status = "영업중"
                else:
                    status = "영업종료"
            except ValueError:
                status = "영업종료"
        else:
            status = "영업종료"

    return {
        "약국명": pharmacy.name,
        "영업 상태": status,
        "영업 시간": f"{start_time[:2]}:{start_time[2:]} ~ {end_time[:2]}:{end_time[2:]}" if start_time and end_time else "정보없음",
        "거리": f"{pharmacy.distance:.1f}km",
        "주소": pharmacy.address,
        "전화": pharmacy.tel
    }

def get_pharmacy_opening_time(pharmacy, target_date):
    """약국의 영업 시작 시간을 가져옴"""
    weekday = target_date.weekday()
    time_mapping = {
        0: pharmacy.mon_start,
        1: pharmacy.tue_start,
        2: pharmacy.wed_start,
        3: pharmacy.thu_start,
        4: pharmacy.fri_start,
        5: pharmacy.sat_start,
        6: pharmacy.sun_start,
    }
    start_time = time_mapping[weekday]
    return int(start_time) if start_time else None

def get_pharmacy_closing_time(pharmacy, target_date):
    """약국의 영업 종료 시간을 가져옴"""
    weekday = target_date.weekday()
    time_mapping = {
        0: pharmacy.mon_end,
        1: pharmacy.tue_end,
        2: pharmacy.wed_end,
        3: pharmacy.thu_end,
        4: pharmacy.fri_end,
        5: pharmacy.sat_end,
        6: pharmacy.sun_end,
    }
    end_time = time_mapping[weekday]
    return int(end_time) if end_time else None

@tool
def search_pharmacy(latitude: float = None, longitude: float = None, target_time: str = None, sort_by: str = None) -> Dict:
    """
    근처 약국 검색
    Args:
        latitude: 위도
        longitude: 경도
        target_time: 특정 시간
        sort_by: 정렬 기준 ("earliest_open" - 가장 빨리 여는 순, "latest_close" - 가장 늦게 닫는 순)
    """
    try:
        # 위치 정보 검증
        if None in (latitude, longitude):
            return {
                "type": "error",
                "start_message": "위치 정보가 필요합니다.",
                "end_message": "위치 정보를 설정해주세요.",
                "data": []
            }

        # 시간 처리
        target_date = datetime.now()
        if target_time:
            target_date = parse_target_time(target_time)

        # 약국 검색 쿼리
        nearby_pharmacies = (
            Pharmacy.objects
            .annotate(
                distance=ACos(
                    Cos(Radians(latitude)) * 
                    Cos(Radians(F('latitude'))) * 
                    Cos(Radians(F('longitude')) - Radians(longitude)) + 
                    Sin(Radians(latitude)) * 
                    Sin(Radians(F('latitude')))
                ) * 6371
            )
            .filter(distance__lte=10)
            .order_by('distance')[:10]
        )

        # 결과 처리
        results = []
        for pharmacy in nearby_pharmacies:
            opening_time = get_pharmacy_opening_time(pharmacy, target_date)
            closing_time = get_pharmacy_closing_time(pharmacy, target_date)
            
            if opening_time is not None:  # 영업 시간 정보가 있는 경우만 포함
                formatted_data = format_pharmacy_data(pharmacy, target_date)
                formatted_data['opening_time'] = opening_time
                formatted_data['closing_time'] = closing_time
                results.append(formatted_data)

        # 정렬 처리
        time_description = "영업 중인"
        if sort_by == "earliest_open":
            results.sort(key=lambda x: x['opening_time'])
            time_description = "가장 빨리 여는"
        elif sort_by == "latest_close":
            results.sort(key=lambda x: x['closing_time'], reverse=True)
            time_description = "가장 늦게 닫는"
        else:
            results = [r for r in results if r["영업 상태"] == "영업중"]

        # 시간 표시 문자열 생성
        time_str = f"{target_date.strftime('%Y-%m-%d %H:%M')} 기준" if target_time else "현재"

        if not results:
            return {
                "type": "no_results",
                "start_message": f"죄송합니다. {time_str} {time_description} 약국을 찾을 수 없습니다.",
                "end_message": "다른 시간대를 확인해보시거나, 직접 전화로 문의해보세요.",
                "data": []
            }

        return {
            "type": "pharmacy_list",
            "start_message": f"{time_str} {time_description} 약국들입니다:",
            "end_message": "방문하시기 전에 전화로 확인하시는 것이 좋습니다.",
            "data": results[:5]
        }

    except Exception as e:
        logger.error(f"Pharmacy search error: {str(e)}")
        return {
            "type": "error",
            "start_message": "약국 검색 중 오류가 발생했습니다.",
            "end_message": "다시 시도해주세요.",
            "data": []
        }

# 도구 리스트
tools = [search_hospital, search_pharmacy]

# GPT-4 LangChain 프롬프트 설정
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """당신은 의료 서비스 도우미입니다. 

        이전 대화 내용을 고려하여 응답해주세요. 예를 들어:
        - 사용자가 "내과로 알려줘"라고 하면 이전에 검색된 병원들 중 내과를 찾아주세요.
        - 새로운 검색이 필요한 경우에만 search_hospital이나 search_pharmacy를 호출하세요.
        
        모든 응답은 반드시 다음과 같은 JSON 형식으로 반환해주세요:
        병원/약국 검색 결과:
        {{
            "type": "hospital_list" 또는 "pharmacy_list",
            "start_message": "검색 결과 소개 메시지",
            "end_message": "마무리 메시지",
            "data": [검색된 목록]
        }}
        
        일반 대화:
        {{
            "type": "chat",
            "start_message": "대화 메시지 앞부분",
            "end_message": "대화 메시지 뒷부분이나 추가 안내",
            "data": []
        }}
        
        검색 결과 없음:
        {{
            "type": "no_results",
            "start_message": "결과가 없다는 안내",
            "end_message": "대안 추천",
            "data": []
        }}
        
        예시:
        - 약국 검색: search_pharmacy(latitude=latitude, longitude=longitude)
        - 병원 검색: search_hospital(query="이비인후과", latitude=latitude, longitude=longitude)
        
        위치 정보를 사용자에게 직접 물어보지 말고, 제공된 정보를 사용하세요."""
    ),
    ("placeholder", "{chat_history}"),
    ("human", "사용자 위치: 위도 {latitude}, 경도 {longitude}\n메시지: {input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# LLM 및 에이전트 생성
llm = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=3,
    handle_parsing_errors=True
)

# 세션 기록 저장소
store = {}

def get_session_history(session_ids):
    """세션별 채팅 기록 관리"""
    if session_ids not in store:
        store[session_ids] = ChatMessageHistory()
    return store[session_ids]

# 챗봇 실행기
agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

class UnifiedChatAPIView(APIView):
    """음성/텍스트 통합 대화 API"""
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.message_histories = {}  # 세션별 대화 기록 저장

    def get_or_create_history(self, session_id):
        """세션별 대화 기록 가져오기 또는 생성"""
        if session_id not in self.message_histories:
            self.message_histories[session_id] = ChatMessageHistory()
        return self.message_histories[session_id]

    def format_response(self, response_data):
        try:
            if isinstance(response_data, str):
                try:
                    if '```json' in response_data:
                        json_str = response_data.split('```json')[1].split('```')[0].strip()
                        parsed_data = json.loads(json_str)
                    elif response_data.strip().startswith('{'):
                        parsed_data = json.loads(response_data)
                    else:
                        return {
                            "type": "chat",
                            "start_message": response_data,
                            "end_message": "",
                            "data": []
                        }
                    if "type" in parsed_data:
                        return {
                            "type": parsed_data["type"],
                            "start_message": parsed_data.get("start_message", ""),
                            "end_message": parsed_data.get("end_message", ""),
                            "data": parsed_data.get("data", [])
                        }
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing error: {str(e)}")
                    return {
                        "type": "chat",
                        "start_message": response_data,
                        "end_message": "",
                        "data": []
                    }
            if isinstance(response_data, dict):
                if "type" in response_data:
                    return response_data
            return {
                "type": "chat",
                "start_message": str(response_data),
                "end_message": "",
                "data": []
            }
        except Exception as e:
            logger.error(f"Response formatting error: {str(e)}")
            return {
                "type": "error",
                "start_message": "응답 처리 중 오류가 발생했습니다.",
                "end_message": "다시 시도해주세요.",
                "data": []
            }

    def get_initial_message(self, user_profile):
        """사용자 위치 정보를 포함한 초기 메시지 생성"""
        try:
            return {
                "type": "chat",
                "start_message": "안녕하세요! 저는 아이케어봇이에요. 😊\n아래 버튼을 눌러서 근처 병원이나 약국을 찾아보세요.",
                "end_message": "또는 직접 '근처 소아과 알려줘'와 같이 물어보셔도 됩니다.",
                "data": [{
                    "type": "button",
                    "buttons": [
                        {
                            "text": "약국 찾기",
                            "message": "근처 약국 찾아줘"
                        },
                        {
                            "text": "병원 찾기",
                            "message": "근처 병원 찾아줘"
                        }
                    ]
                }]
            }
        except Exception as e:
            logger.error(f"Error getting initial message: {str(e)}")
            return {
                "type": "chat",
                "start_message": "안녕하세요! 저는 아이케어봇이에요. 😊",
                "end_message": "아이의 건강과 관련된 정보를 도와드릴게요.",
                "data": []
            }

    def post(self, request):
        temp_files = []  # 임시 파일 관리

        try:
            user_profile = request.user.profile
            if not (user_profile.latitude and user_profile.longitude):
                return Response(
                    {"error": "위치 정보가 설정되어 있지 않습니다."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 1. 입력 처리 (음성 또는 텍스트)
            input_text = None

            # 음성 입력 처리
            if 'audio' in request.FILES:
                audio_file = request.FILES['audio']
                temp_audio_path = os.path.join(tempfile.gettempdir(), f'temp_audio_{uuid.uuid4()}.wav')
                temp_files.append(temp_audio_path)

                with open(temp_audio_path, 'wb+') as destination:
                    for chunk in audio_file.chunks():
                        destination.write(chunk)

                # 음성을 텍스트로 변환
                input_text = transcribe_speech(temp_audio_path)
                if not input_text:
                    return Response({
                        "type": "error",
                        "start_message": "음성을 텍스트로 변환하지 못했습니다.",
                        "end_message": "다시 시도해주세요.",
                        "data": []
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                input_text = request.data.get('message')
                if not input_text:
                    return Response(
                        {"error": "메시지가 제공되지 않았습니다."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 2. 챗봇 처리
            session_id = request.data.get("session_id", str(uuid.uuid4()))
            chat_history = self.get_or_create_history(session_id)

            # 버튼 클릭 처리
            if input_text in ["근처 약국 찾아줘", "근처 병원 찾아줘"]:
                # 사용자 메시지 저장
                chat_history.add_message(HumanMessage(content=input_text))
                
                initial_response = {
                    "type": "chat",
                    "start_message": "네, 알겠습니다! 😊",
                    "end_message": "근처를 검색해볼게요.",
                    "data": []
                }

                context = {
                    "input": input_text,
                    "latitude": float(user_profile.latitude),
                    "longitude": float(user_profile.longitude)
                }

                response = agent_with_chat_history.invoke(
                    context,
                    config={"configurable": {"session_id": session_id}},
                )
                response_data = response.get("output", "응답을 생성하지 못했습니다.")
                formatted_response = self.format_response(response_data)
                
                # AI 응답 저장
                chat_history.add_message(AIMessage(content=formatted_response["start_message"]))

                result = {
                    "input_text": input_text,
                    "type": "multi",
                    "responses": [
                        initial_response,
                        formatted_response
                    ],
                    "session_id": session_id,
                    "location": {
                        "latitude": float(user_profile.latitude),
                        "longitude": float(user_profile.longitude)
                    }
                }
                return Response(result, status=status.HTTP_200_OK)

            # 일반 대화 처리
            chat_history.add_message(HumanMessage(content=input_text))
            
            context = {
                "input": input_text,
                "latitude": float(user_profile.latitude),
                "longitude": float(user_profile.longitude),
                "chat_history": chat_history.messages  # 대화 기록 전달
            }

            response = agent_with_chat_history.invoke(
                context,
                config={"configurable": {"session_id": session_id}},
            )
            response_data = response.get("output", "응답을 생성하지 못했습니다.")
            formatted_response = self.format_response(response_data)
            
            # AI 응답 저장
            chat_history.add_message(AIMessage(content=formatted_response["start_message"]))

            result = {
                "input_text": input_text,
                "type": formatted_response["type"],
                "start_message": formatted_response["start_message"],
                "end_message": formatted_response["end_message"],
                "data": formatted_response["data"],
                "session_id": session_id,
                "location": {
                    "latitude": float(user_profile.latitude),
                    "longitude": float(user_profile.longitude)
                }
            }

            # 3. 음성 응답 생성 (need_voice가 true일 경우)
            need_voice = request.data.get('need_voice', False)
            if need_voice:
                temp_tts_path = os.path.join(tempfile.gettempdir(), f'temp_tts_{uuid.uuid4()}.mp3')
                temp_files.append(temp_tts_path)

                try:
                    response_text = f"{formatted_response['start_message']} {formatted_response['end_message']}"
                    tts = gTTS(text=response_text, lang='ko')
                    tts.save(temp_tts_path)

                    with open(temp_tts_path, 'rb') as f:
                        audio_content = base64.b64encode(f.read()).decode('utf-8')

                    result.update({
                        "audio": audio_content,
                        "audio_type": "audio/mp3"
                    })
                except Exception as e:
                    logger.error(f"TTS generation error: {str(e)}")

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"ChatBot error: {str(e)}")
            return Response({
                "type": "error",
                "start_message": "처리 중 오류가 발생했습니다.",
                "end_message": "다시 시도해주세요.",
                "data": [],
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception as e:
                        logger.error(f"Error deleting temporary file: {str(e)}")
