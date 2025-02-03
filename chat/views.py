import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    NewsSearchRequestSerializer,
    NewsSearchResponseSerializer,
)
from langchain.tools import tool
from typing import List, Dict
from langchain_teddynote.tools import GoogleNews
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent
from langchain.agents import AgentExecutor
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_teddynote.messages import AgentStreamParser

# 로그 설정
logger = logging.getLogger(__name__)
load_dotenv()


# ✅ 뉴스 검색 도구 정의
@tool
def search_news(query: str) -> List[Dict[str, str]]:
    """검색어를 이용하여 Google News에서 뉴스를 가져옵니다."""
    news_tool = GoogleNews()
    return news_tool.search_by_keyword(query, k=5)


# ✅ 도구 리스트
tools = [search_news]

# ✅ GPT-4 LangChain 프롬프트 설정
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Use the `search_news` tool for news search.",
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# ✅ LLM 및 에이전트 생성
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
    max_execution_time=10,
    handle_parsing_errors=True,
)

# ✅ 세션 기록 저장소
store = {}


def get_session_history(session_ids):
    """세션별 채팅 기록 관리"""
    if session_ids not in store:
        store[session_ids] = ChatMessageHistory()
    return store[session_ids]


# ✅ 챗봇 실행기
agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)
agent_stream_parser = AgentStreamParser()

# TODO : OpenAI Whisper 음성지원 기능

# TODO : 사용자 위치 가져오기 
# 🔹 1️⃣ 흐름 정리
# 프론트엔드: navigator.geolocation으로 GPS(위도, 경도) 정보를 가져와 Django로 전송.
# Django 백엔드: 받은 GPS 데이터를 기반으로 근처 병원 정보 검색.
# 병원 데이터 가져오기:
# 구글 플레이스 API (가장 쉬운 방법)
# 공공데이터포털 (보건복지부 병원 데이터)
# 내부 병원 데이터베이스 사용
# 챗봇이 사용자 위치를 분석하여 병원 추천
# OpenAI GPT 또는 LangChain을 활용해 응답 생성.

# 🔹 2️⃣ Django에서 사용자 위치를 가져오는 방법
# ✅ (1) 프론트엔드에서 Geolocation API로 위치 가져오기 → Django로 전송
# JavaScript에서 navigator.geolocation.getCurrentPosition()을 사용하여 GPS 데이터 가져옴
# 가져온 GPS 데이터를 Django API로 전송
# Django에서 해당 위치를 처리하고 응답 반환
# ✅ Django 챗봇이 사용자 위치 기반으로 병원 정보를 제공하는 방법
# 사용자의 GPS 정보를 받아서 챗봇에서 위치를 인식하고, 주변 병원을 추천하는 기능을 추가해야 합니다.



### 🚀 **챗봇 API (GPT + LangChain)**
class ChatBotAPIView(APIView):
    def post(self, request):
        """사용자의 질문을 GPT-4와 LangChain을 이용하여 응답"""
        serializer = ChatRequestSerializer(data=request.data)
        if serializer.is_valid():
            question = serializer.validated_data["question"]
            session_id = serializer.validated_data.get("session_id", "default_session")

            try:
                response = agent_with_chat_history.invoke(
                    {"input": question},
                    config={"configurable": {"session_id": session_id}},
                )
                message = response.get("output", "No response generated.")

                response_data = {"response_code": 200, "message": message}
                return Response(response_data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


### 🚀 **기본 GPT 챗봇 API**
class GPTChatAPIView(APIView):
    def post(self, request):
        """GPT-4o를 사용하여 단순 채팅 응답"""
        serializer = ChatRequestSerializer(data=request.data)
        if serializer.is_valid():
            question = serializer.validated_data["question"]

            try:
                llm = ChatOpenAI(temperature=0.1, model_name="gpt-4o-mini")
                response = llm.invoke(question)
                message = response.content

                response_data = {"response_code": 200, "message": message}
                return Response(response_data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response(
                    {"error": f"오류 발생: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


### 🚀 **뉴스 검색 API**
class NewsSearchAPIView(APIView):
    def post(self, request):
        """Google News를 활용한 뉴스 검색"""
        serializer = NewsSearchRequestSerializer(data=request.data)
        if serializer.is_valid():
            query = serializer.validated_data["query"]

            try:
                news_tool = GoogleNews()
                results = news_tool.search_by_keyword(query, k=5)

                if not results:
                    return Response(
                        {"message": "No news articles found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                response_data = [
                    NewsSearchResponseSerializer(article).data for article in results
                ]
                return Response(response_data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response(
                    {"error": f"오류 발생: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
