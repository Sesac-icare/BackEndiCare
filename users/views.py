from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import RegisterSerializer, LoginSerializer
from .models import UserProfile
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


# 회원가입
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]  # 누구나 접근 가능

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # UserProfile에서 term_agreed 정보 가져오기
        user_profile = UserProfile.objects.get(user=user)

        return Response(
            {
                "username": user.username,
                "email": user.email,
                "term_agreed": user_profile.term_agreed,
            },
            status=status.HTTP_201_CREATED,
        )


# 로그인
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]  # 누구나 접근 가능

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# 로그아웃
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # 인증된 사용자만 접근 가능

    def post(self, request):
        try:
            request.user.auth_token.delete()  # 현재 유저의 토큰 삭제
            return Response(
                {"message": "Successfully logged out."}, status=status.HTTP_200_OK
            )
        except Token.DoesNotExist:
            return Response(
                {"error": "Invalid token or already logged out."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]  # 로그인한 사용자만 접근 가능

    @swagger_auto_schema(
        operation_description="사용자 정보 조회 API",
        responses={
            200: openapi.Response(
                description="사용자 정보 조회 성공",
                examples={
                    "application/json": {
                        "username": "example_user",
                        "email": "example@email.com",
                    }
                },
            ),
            401: openapi.Response(
                description="인증되지 않은 사용자",
                examples={
                    "application/json": {
                        "detail": "자격 인증데이터(authentication credentials)가 제공되지 않았습니다."
                    }
                },
            ),
        },
    )
    def get(self, request):
        """현재 로그인한 사용자의 정보를 반환합니다."""
        return Response(
            {"username": request.user.username, "email": request.user.email}
        )


# 회원탈퇴
class UserDeleteView(APIView):
    permission_classes = [IsAuthenticated]  # 인증된 사용자만 접근 가능

    @swagger_auto_schema(
        operation_description="회원 탈퇴 API",
        responses={
            200: openapi.Response(
                description="회원 탈퇴 성공",
                examples={
                    "application/json": {"message": "회원 탈퇴가 완료되었습니다."}
                },
            ),
            401: openapi.Response(
                description="인증되지 않은 사용자",
                examples={
                    "application/json": {
                        "detail": "자격 인증데이터(authentication credentials)가 제공되지 않았습니다."
                    }
                },
            ),
        },
    )
    def delete(self, request):
        user = request.user
        try:
            # 사용자 토큰 삭제
            if hasattr(user, "auth_token"):
                user.auth_token.delete()

            # UserProfile 삭제 (CASCADE 설정이 되어있다면 자동으로 삭제됨)
            if hasattr(user, "userprofile"):
                user.userprofile.delete()

            # 사용자 계정 삭제
            user.delete()

            return Response(
                {"message": "회원 탈퇴가 완료되었습니다."}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "회원 탈퇴 처리 중 오류가 발생했습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ----------------------------------------------------------------------------


# from rest_framework import generics, status
# from rest_framework.response import Response
# from django.contrib.auth import get_user_model
# from rest_framework_simplejwt.views import TokenObtainPairView
# from .serializers import UserSerializer, LoginSerializer

# User = get_user_model()

# class RegisterView(generics.CreateAPIView):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer

# class LoginView(generics.GenericAPIView):
#     serializer_class = LoginSerializer

#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         return Response(serializer.validated_data, status=status.HTTP_200_OK)
