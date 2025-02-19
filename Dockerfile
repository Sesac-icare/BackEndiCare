# Python 3.11.11 이미지 사용
FROM python:3.11.11

# 파이썬 버퍼링 끄기 (로그 바로 출력)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 시스템 업데이트 및 빌드에 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    cargo \
    curl

# Rust 도구체인 설치 (rustup 사용, 최신 stable 버전)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"
RUN rustup update stable

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 패키지 설치
ENV PIP_ROOT_USER_ACTION=ignore
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 프로젝트 파일 전체 복사
COPY . /app/

# Gunicorn으로 Django 앱 실행 (프로젝트 이름을 실제로 수정)
# CMD ["gunicorn", "icare", "--bind", "0.0.0.0:8000"]
CMD ["gunicorn", "icare.wsgi:application", "--bind", "0.0.0.0:8000"]