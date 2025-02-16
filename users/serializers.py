from django.contrib.auth.models import User  # User 모델
from django.contrib.auth.password_validation import (
    validate_password,
)  # Django의 기본 패스워드 검증 도구

from rest_framework import serializers
from rest_framework.authtoken.models import Token  # Token 모델
from rest_framework.validators import (
    UniqueValidator,
)  # 이메일 중복 방지를 위한 검증 도구

from django.contrib.auth import authenticate
from .models import UserProfile  # UserProfile 모델 추가


# 회원가입 시리얼라이저
class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]  # email만 unique 체크
    )
    password = serializers.CharField(write_only=True, required=True)
    passwordCheck = serializers.CharField(write_only=True, required=True)
    term_agreed = serializers.BooleanField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'passwordCheck', 'term_agreed')

    def validate(self, attrs):
        if attrs['password'] != attrs['passwordCheck']:
            raise serializers.ValidationError({"password": "비밀번호가 일치하지 않습니다."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
        )
        user.set_password(validated_data['password'])
        user.save()

        # UserProfile 생성
        UserProfile.objects.create(
            user=user,
            term_agreed=validated_data.get('term_agreed', False)
        )

        return user


# 로그인 시리얼라이저
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    # write_only 옵션으로 클라이언트-> 서버 방향의 역직렬화만 가능
    # 서버 -> 클라이언트 방향의 직렬화는 불가능

    def validate(self, data):
        # 이메일을 기반으로 사용자 검색
        try:
            user = User.objects.get(email=data["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"error": "User with this email does not exist."}
            )

        # authenticate() 함수는 기본적으로 username을 요구하므로 username으로 전달
        user = authenticate(username=user.username, password=data["password"])

        if user:
            token, created = Token.objects.get_or_create(user=user)
            # ✅ 토큰 + 사용자 정보 반환
            return {
                "token": token.key,
                "user": {"username": user.username, "email": user.email},
            }

        raise serializers.ValidationError({"error": "Invalid email or password"})


# class ProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Profile
#         fields = ("nickname", "position", "subjects", "image")

# -----------------------------------------------------------------

# from rest_framework import serializers
# from django.contrib.auth import get_user_model
# from rest_framework_simplejwt.tokens import RefreshToken

# User = get_user_model()

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'password']
#         extra_kwargs = {'password': {'write_only': True}}

#     def create(self, validated_data):
#         user = User.objects.create_user(**validated_data)
#         return user

# class LoginSerializer(serializers.Serializer):
#     email = serializers.EmailField()
#     password = serializers.CharField(write_only=True)

#     def validate(self, data):
#         user = User.objects.filter(email=data['email']).first()
#         if user and user.check_password(data['password']):
#             refresh = RefreshToken.for_user(user)
#             return {
#                 'refresh': str(refresh),
#                 'access': str(refresh.access_token),
#             }
#         raise serializers.ValidationError("Invalid credentials")
