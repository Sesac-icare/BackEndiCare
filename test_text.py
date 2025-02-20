import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
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
from datetime import datetime, time

from .models import Hospital, Pharmacy

# 로그 설정
logger = logging.getLogger(__name__)
load_dotenv()

# OpenAI client 초기화
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

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

def get_hospital_state(hospital, current_time):
    """병원의 현재 영업 상태를 확인"""
    has_any_hours = (
        (hospital.weekday_hours and any(hospital.weekday_hours.values())) or
        hospital.saturday_hours or
        hospital.sunday_hours or
        (hospital.reception_hours and any(hospital.reception_hours.values()))
    )
    
    if not has_any_hours:
        return "확인요망"
    
    weekday = current_time.weekday()
    weekday_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri'}
    
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
        day_key = weekday_map[weekday]
        hours = hospital.weekday_hours.get(day_key) if hospital.weekday_hours else None
        lunch_key = 'weekday'
    
    if not hours:
        return "영업종료"
        
    try:
        current_time_only = current_time.time()
        start_time = datetime.strptime(normalize_time(hours['start']), '%H:%M').time()
        end_time = datetime.strptime(normalize_time(hours['end']), '%H:%M').time()
        
        # 점심시간 체크
        if hospital.lunch_time and lunch_key in hospital.lunch_time:
            lunch = hospital.lunch_time[lunch_key]
            if lunch:
                try:
                    lunch_start = datetime.strptime(normalize_time(lunch['start']), '%H:%M').time()
                    lunch_end = datetime.strptime(normalize_time(lunch['end']), '%H:%M').time()
                    
                    if lunch_start.hour < 12:
                        lunch_start = time(lunch_start.hour + 12, lunch_start.minute)
                        lunch_end = time(lunch_end.hour + 12, lunch_end.minute)
                    
                    if lunch_start <= current_time_only <= lunch_end:
                        return "점심시간"
                except ValueError:
                    pass
        
        if start_time <= current_time_only <= end_time:
            return "영업중"
        return "영업종료"
        
    except ValueError:
        return "영업종료"

# 병원 검색 도구 개선
@tool
def search_hospital(query: str, latitude: float, longitude: float) -> List[Dict]:
    """
    영업 중인 병원 중 사용자의 증상에 맞춰 가까운 병원 추천
    사용자의 증상을 충분히 설명하지 않을 경우, 추가 질문을 통해 정보 수집    
    Args:
        query: 검색어 (예: "소아과", "내과")
        latitude: 위도
        longitude: 경도
    Returns:
        근처 병원 목록
    """
    try:
        current_time = datetime.now()
        
        hospitals = Hospital.objects.annotate(
            distance=ACos(
                Cos(Radians(latitude)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(longitude)) + 
                Sin(Radians(latitude)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=3).order_by('distance')

        results = []
        for hospital in hospitals:
            # 영업 상태 확인
            state = get_hospital_state(hospital, current_time)
            
            # 진료과목 처리
            department_str = hospital.department if hasattr(hospital, 'department') else ""
            
            hospital_data = {
                'name': hospital.name,
                'address': hospital.address,
                'phone': hospital.phone,
                'department': department_str,
                'distance': f"{hospital.distance:.1f}km",
                'state': state,
                'hospital_type': hospital.hospital_type if hospital.hospital_type else "일반의원",
                'weekday_hours': hospital.weekday_hours,
                'saturday_hours': hospital.saturday_hours,
                'sunday_hours': hospital.sunday_hours,
                'lunch_time': hospital.lunch_time
            }
            
            # 영업중인 병원 우선 추가
            if state == "영업중":
                results.insert(0, hospital_data)
            else:
                results.append(hospital_data)

        return results[:5]  # 상위 5개만 반환
        
    except Exception as e:
        logger.error(f"Hospital search error: {str(e)}")
        return [{"error": f"병원 검색 중 오류가 발생했습니다: {str(e)}"}]

# 약국 검색 도구
@tool
def search_pharmacy(latitude: float, longitude: float) -> List[Dict]:
    """
    사용자 위치 기준으로 영업 중인 약국 중 3 곳을 검색.
    Args:
        latitude: 위도
        longitude: 경도
    Returns:
        근처 약국 목록
    """
    try:
        pharmacies = Pharmacy.objects.annotate(
            distance=ACos(
                Cos(Radians(latitude)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(longitude)) + 
                Sin(Radians(latitude)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=3).order_by('distance')[:5]

        results = []
        for pharmacy in pharmacies:
            results.append({
                'name': pharmacy.name,
                'address': pharmacy.address,
                'phone': pharmacy.tel,
                'distance': f"{pharmacy.distance:.1f}km",
                'state': "영업중" if pharmacy.is_open() else "영업종료"
            })
        return results
    except Exception as e:
        logger.error(f"Pharmacy search error: {str(e)}")
        return [{"error": f"약국 검색 중 오류 발생: {str(e)}"}]

# 도구 리스트
tools = [search_hospital, search_pharmacy]

# GPT-4 LangChain 프롬프트 설정
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """당신은 의료 서비스 도우미입니다. 
        병원과 약국 검색을 도와주고, 의료 관련 질문에 답변해주세요.
        search_hospital과 search_pharmacy 도구를 사용하여 근처 병원과 약국을 찾을 수 있습니다."""
    ),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# LLM 및 에이전트 생성
llm = ChatOpenAI(model="gpt-4", temperature=0)
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

class ChatBotAPIView(APIView):
    """텍스트 기반 챗봇 API"""
    parser_classes = (JSONParser,)

    @swagger_auto_schema(
        operation_summary="챗봇 대화",
        operation_description="텍스트로 대화하고 병원/약국 검색 등 도구 사용 가능",
        tags=['chat']
    )
    def post(self, request):
        try:
            # 1. 입력 처리
            input_text = request.data.get('message')
            if not input_text:
                return Response(
                    {"error": "메시지가 제공되지 않았습니다."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            session_id = request.data.get("session_id", "default_session")

            # 2. LangChain Agent로 응답 생성
            try:
                response = agent_with_chat_history.invoke(
                    {"input": input_text},
                    config={"configurable": {"session_id": session_id}},
                )
                response_text = response.get("output", "응답을 생성하지 못했습니다.")
            except Exception as e:
                logger.error(f"Agent execution error: {str(e)}")
                return Response(
                    {"error": f"응답 생성 중 오류가 발생했습니다: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 3. 결과 반환
            result = {
                "input_text": input_text,
                "response_text": response_text,
                "session_id": session_id
            }

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"ChatBot error: {str(e)}")
            return Response(
                {"error": f"처리 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

