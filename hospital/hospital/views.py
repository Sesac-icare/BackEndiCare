import json
import openpyxl
from geopy.distance import geodesic

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.contrib.auth.hashers import make_password

from .models import User, Child, PharmacyEnvelope

# ===== 기존 병원 API =====

# 엑셀 파일 경로 (병원 정보가 저장된 파일)
EXCEL_FILE_PATH = "hospital.xlsx"

@csrf_exempt
def nearby_hospitals(request):
    """
    사용자의 현재 위치를 기반으로 가까운 병원을 반환하는 API.
    GET 파라미터: lat, lon
    """
    try:
        # 위도, 경도 받기
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")

        if not lat or not lon:
            return JsonResponse({"status": "error", "message": "위도와 경도를 입력하세요."}, status=400)

        user_location = (float(lat), float(lon))

        # 엑셀 파일 로드
        workbook = openpyxl.load_workbook(EXCEL_FILE_PATH)
        sheet = workbook.active
        hospitals = []

        # 현재 시간 가져오기 (HH:MM 형식)
        current_time = localtime().strftime("%H:%M")

        # 엑셀 데이터 읽기 (첫 번째 행은 헤더라고 가정)
        for row in sheet.iter_rows(min_row=2, values_only=True):
            try:
                name = row[0]              # 병원명
                business_hours = row[1]    # 영업시간 (예: "09:00 - 18:00")
                latitude = float(row[2])     # 위도
                longitude = float(row[3])    # 경도
                address = row[4]           # 주소
                phone = row[5]             # 전화번호

                # 영업 시간 파싱 및 현재 영업 여부 체크
                open_time, close_time = business_hours.split(" - ")
                is_open = "영업중" if open_time <= current_time <= close_time else "영업 종료"

                # 사용자 위치와 병원 사이의 거리 계산 (km 단위)
                distance = geodesic(user_location, (latitude, longitude)).km

                # 병원 정보 저장
                hospitals.append({
                    "병원명": name,
                    "영업여부": is_open,
                    "영업시간": business_hours,
                    "거리": f"{distance:.1f}km",
                    "주소": address,
                    "전화번호": phone
                })

            except Exception as row_error:
                print(f"❌ 행 데이터 오류 발생: {row} → {row_error}")

        # 거리가 가까운 순으로 정렬 후 최대 5개 반환
        hospitals = sorted(hospitals, key=lambda x: float(x["거리"].replace("km", "")))[:5]

        return JsonResponse({"status": "success", "data": hospitals}, status=200)

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ===== 사용자(User) 관련 API =====

@csrf_exempt
def create_user(request):
    """
    사용자 생성 API (POST)
    요청 JSON 예시:
    {
        "email": "test@example.com",
        "password": "your_password"
    }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return JsonResponse({"status": "error", "message": "Email과 password를 입력하세요."}, status=400)

            # 패스워드 해싱 (보안을 위해)
            password_hash = make_password(password)
            user = User.objects.create(email=email, password_hash=password_hash)

            return JsonResponse({
                "status": "success",
                "data": {"user_id": user.id, "email": user.email}
            }, status=201)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    else:
        return JsonResponse({"status": "error", "message": "POST 메서드만 허용됩니다."}, status=405)


# ===== 자녀(Child) 관련 API =====

@csrf_exempt
def create_child(request):
    """
    자녀 생성 API (POST)
    요청 JSON 예시:
    {
        "user_id": 1,
        "child_name": "홍길동"
    }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_id = data.get("user_id")
            child_name = data.get("child_name")

            if not user_id or not child_name:
                return JsonResponse({"status": "error", "message": "user_id와 child_name을 입력하세요."}, status=400)

            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return JsonResponse({"status": "error", "message": "해당 사용자가 존재하지 않습니다."}, status=404)

            child = Child.objects.create(user=user, child_name=child_name)
            return JsonResponse({
                "status": "success",
                "data": {"child_id": child.id, "child_name": child.child_name, "user_id": user.id}
            }, status=201)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    else:
        return JsonResponse({"status": "error", "message": "POST 메서드만 허용됩니다."}, status=405)


@csrf_exempt
def list_children(request):
    """
    자녀 목록 조회 API (GET)  
    쿼리 파라미터: user_id (선택 사항)
    """
    if request.method == "GET":
        try:
            user_id = request.GET.get("user_id")
            if user_id:
                children = Child.objects.filter(user_id=user_id)
            else:
                children = Child.objects.all()

            children_list = [
                {"child_id": child.id, "child_name": child.child_name, "user_id": child.user.id}
                for child in children
            ]
            return JsonResponse({"status": "success", "data": children_list}, status=200)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    else:
        return JsonResponse({"status": "error", "message": "GET 메서드만 허용됩니다."}, status=405)


# ===== 약국 봉투(PharmacyEnvelope) 관련 API =====

@csrf_exempt
def create_pharmacy_envelope(request):
    """
    약국 봉투 생성 API (POST)
    요청 JSON 예시:
    {
        "child_id": 1,
        "pharmacy_name": "OO약국",
        "prescription_number": "RX123456",
        "prescription_date": "2025-03-01"  // YYYY-MM-DD 형식
    }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            child_id = data.get("child_id")
            pharmacy_name = data.get("pharmacy_name")
            prescription_number = data.get("prescription_number")
            prescription_date = data.get("prescription_date")

            if not all([child_id, pharmacy_name, prescription_number, prescription_date]):
                return JsonResponse({"status": "error", "message": "모든 필드를 입력하세요."}, status=400)

            try:
                child = Child.objects.get(pk=child_id)
            except Child.DoesNotExist:
                return JsonResponse({"status": "error", "message": "해당 자녀가 존재하지 않습니다."}, status=404)

            envelope = PharmacyEnvelope.objects.create(
                child=child,
                pharmacy_name=pharmacy_name,
                prescription_number=prescription_number,
                prescription_date=prescription_date
            )
            return JsonResponse({
                "status": "success",
                "data": {"envelope_id": envelope.id}
            }, status=201)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    else:
        return JsonResponse({"status": "error", "message": "POST 메서드만 허용됩니다."}, status=405)


@csrf_exempt
def list_pharmacy_envelopes(request):
    """
    약국 봉투 목록 조회 API (GET)  
    쿼리 파라미터: child_id (선택 사항)
    """
    if request.method == "GET":
        try:
            child_id = request.GET.get("child_id")
            if child_id:
                envelopes = PharmacyEnvelope.objects.filter(child_id=child_id)
            else:
                envelopes = PharmacyEnvelope.objects.all()

            envelopes_list = [
                {
                    "envelope_id": env.id,
                    "child_id": env.child.id,
                    "pharmacy_name": env.pharmacy_name,
                    "prescription_number": env.prescription_number,
                    "prescription_date": env.prescription_date.strftime("%Y-%m-%d")
                }
                for env in envelopes
            ]
            return JsonResponse({"status": "success", "data": envelopes_list}, status=200)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    else:
        return JsonResponse({"status": "error", "message": "GET 메서드만 허용됩니다."}, status=405)
