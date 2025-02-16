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

class UnifiedChatAPIView(APIView):
    """음성/텍스트 통합 대화 API"""
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request):
        temp_files = []  # 임시 파일 관리

        try:
            # 1. 입력 처리 (음성 또는 텍스트)
            input_text = None
            input_type = "text"

            # 음성 입력 처리
            if 'audio' in request.FILES:
                input_type = "voice"
                audio_file = request.FILES['audio']
                temp_audio_path = os.path.join(tempfile.gettempdir(), f'temp_audio_{uuid.uuid4()}.wav')
                temp_files.append(temp_audio_path)

                with open(temp_audio_path, 'wb') as temp_file:
                    for chunk in audio_file.chunks():
                        temp_file.write(chunk)

                input_text = transcribe_speech(temp_audio_path)
                if not input_text:
                    return Response(
                        {"error": "음성 인식에 실패했습니다."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # 텍스트 입력 처리
            else:
                input_text = request.data.get('message')
                if not input_text:
                    return Response(
                        {"error": "메시지가 제공되지 않았습니다."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 2. GPT 응답 생성
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant specialized in children's health care. Please provide clear and simple explanations suitable for parents."
                },
                {"role": "user", "content": input_text}
            ]

            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=150
            )
            response_text = completion.choices[0].message.content.strip()

            # 3. 음성 응답 생성 (need_voice가 true일 경우)
            result = {
                "input_type": input_type,
                "input_text": input_text,
                "response_text": response_text
            }

            need_voice = request.data.get('need_voice', False)
            if need_voice:
                temp_tts_path = os.path.join(tempfile.gettempdir(), f'temp_tts_{uuid.uuid4()}.mp3')
                temp_files.append(temp_tts_path)

                tts = gTTS(text=response_text, lang='ko')
                tts.save(temp_tts_path)

                with open(temp_tts_path, 'rb') as f:
                    audio_content = base64.b64encode(f.read()).decode('utf-8')

                result.update({
                    "audio": audio_content,
                    "audio_type": "audio/mp3"
                })

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error in UnifiedChatAPIView: {str(e)}")
            return Response(
                {"error": f"처리 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        print(f"임시 파일 삭제 오류: {str(e)}")
            
            
