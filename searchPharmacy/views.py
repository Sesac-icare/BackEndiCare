from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import User, Child, PharmacyEnvelope
from .serializers import UserSerializer, ChildSerializer, PharmacyEnvelopeSerializer

# ─── 사용자 관련 API ──────────────────────────────

@api_view(['POST'])
def create_user(request):
    """
    사용자 생성 API (POST)
    요청 예시 (JSON):
    {
        "email": "test@example.com",
        "password": "your_password"
    }
    """
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {"status": "success", "data": {"user_id": user.id, "email": user.email}},
            status=status.HTTP_201_CREATED
        )
    return Response({"status": "error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def list_users(request):
    """전체 사용자 목록 조회 API (GET)"""
    users = User.objects.all()
    serializer = UserSerializer(users, many=True)
    return Response({"status": "success", "data": serializer.data})


# ─── 자녀 관련 API ──────────────────────────────

@api_view(['POST'])
def create_child(request):
    """
    자녀 생성 API (POST)
    요청 예시 (JSON):
    {
        "user_id": 1,
        "child_name": "홍길동"
    }
    """
    serializer = ChildSerializer(data=request.data)
    if serializer.is_valid():
        child = serializer.save()
        return Response(
            {"status": "success", "data": {"child_id": child.id, "child_name": child.child_name, "user_id": child.user.id}},
            status=status.HTTP_201_CREATED
        )
    return Response({"status": "error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def list_children(request):
    """
    자녀 목록 조회 API (GET)
    쿼리 파라미터: user_id (선택 사항)
    """
    user_id = request.query_params.get('user_id')
    if user_id:
        children = Child.objects.filter(user_id=user_id)
    else:
        children = Child.objects.all()
    serializer = ChildSerializer(children, many=True)
    return Response({"status": "success", "data": serializer.data})


# ─── 약국 봉투(PharmacyEnvelope) 관련 API ──────────────────────────────

@api_view(['POST'])
def create_pharmacy_envelope(request):
    """
    약국 봉투 생성 API (POST)
    요청 예시 (JSON):
    {
        "child_id": 1,
        "pharmacy_name": "우리약국",
        "prescription_number": "RX123456",
        "prescription_date": "2025-02-10"  // YYYY-MM-DD 형식
    }
    """
    serializer = PharmacyEnvelopeSerializer(data=request.data)
    if serializer.is_valid():
        envelope = serializer.save()
        return Response(
            {
                "status": "success",
                "data": {
                    "envelope_id": envelope.id,
                    "pharmacy_name": envelope.pharmacy_name,
                    "prescription_number": envelope.prescription_number,
                    "prescription_date": envelope.prescription_date
                }
            },
            status=status.HTTP_201_CREATED
        )
    return Response({"status": "error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def list_pharmacy_envelopes(request):
    """
    약국 봉투 목록 조회 API (GET)
    쿼리 파라미터: child_id (선택 사항)
    """
    child_id = request.query_params.get('child_id')
    if child_id:
        envelopes = PharmacyEnvelope.objects.filter(child_id=child_id)
    else:
        envelopes = PharmacyEnvelope.objects.all()
    serializer = PharmacyEnvelopeSerializer(envelopes, many=True)
    return Response({"status": "success", "data": serializer.data})
