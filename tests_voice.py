import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import tempfile
from gtts import gTTS
from google.cloud import speech
import base64
from dotenv import load_dotenv
import openai
import uuid
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

from .models import Hospital, Pharmacy

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
        with open(audio_file_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="ko-KR",
            enable_automatic_punctuation=True,
            model="default"
        )

        response = speech_client.recognize(config=config, audio=audio)
        if not response.results:
            return None

        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "

        return transcript.strip()

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return None
    finally:
        if speech_client:
            try:
                speech_client.transport.close()
            except Exception as e:
                logger.error(f"Speech client cleanup error: {str(e)}")

# 병원 검색 도구
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
        hospitals = Hospital.objects.annotate(
            distance=ACos(
                Cos(Radians(latitude)) * 
                Cos(Radians(F('latitude'))) * 
                Cos(Radians(F('longitude')) - Radians(longitude)) + 
                Sin(Radians(latitude)) * 
                Sin(Radians(F('latitude')))
            ) * 6371
        ).filter(distance__lte=3).order_by('distance')[:5]

        results = []
        for hospital in hospitals:
            results.append({
                'name': hospital.name,
                'address': hospital.address,
                'phone': hospital.phone,
                'distance': f"{hospital.distance:.1f}km"
            })
        return results
    except Exception as e:
        logger.error(f"Hospital search error: {str(e)}")
        return [{"error": f"병원 검색 중 오류 발생: {str(e)}"}]

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
# 프롬프트 엔지니어링 추가
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
    """통합 챗봇 API (음성/텍스트 + 도구 사용)"""
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @swagger_auto_schema(
        operation_summary="챗봇 대화",
        operation_description="텍스트 또는 음성으로 대화하고 병원/약국 검색 등 도구 사용 가능",
        tags=['chat']
    )
    def post(self, request):
        temp_files = []

        try:
            # 1. 입력 처리
            input_text = None
            input_type = "text"
            session_id = request.data.get("session_id", "default_session")

            if 'audio' in request.FILES:
                input_type = "voice"
                audio_file = request.FILES['audio']
                
                original_filename = audio_file.name
                file_extension = original_filename.split('.')[-1] if '.' in original_filename else 'wav'
                temp_audio_path = os.path.join(tempfile.gettempdir(), f'temp_audio_{uuid.uuid4()}.{file_extension}')
                temp_files.append(temp_audio_path)

                with open(temp_audio_path, 'wb+') as temp_file:
                    for chunk in audio_file.chunks():
                        temp_file.write(chunk)

                input_text = transcribe_speech(temp_audio_path)
                if not input_text:
                    return Response(
                        {"error": "음성 인식에 실패했습니다."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                input_text = request.data.get('message')
                if not input_text:
                    return Response(
                        {"error": "메시지가 제공되지 않았습니다."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

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

            # 3. 결과 생성
            result = {
                "input_type": input_type,
                "input_text": input_text,
                "response_text": response_text,
                "session_id": session_id
            }

            # 4. 음성 응답 생성
            need_voice = request.data.get('need_voice')
            if need_voice and need_voice.lower() == 'true':
                temp_tts_path = os.path.join(tempfile.gettempdir(), f'temp_tts_{uuid.uuid4()}.mp3')
                temp_files.append(temp_tts_path)

                try:
                    tts = gTTS(text=response_text, lang='ko', slow=False)
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
            return Response(
                {"error": f"처리 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        logger.error(f"Temp file cleanup error: {str(e)}")

