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
        help_text="이메일(Unique)",
        required=True,
        validators=[
            UniqueValidator(queryset=User.objects.all())
        ],  # 이메일에 대한 중복 검증
    )
    password = serializers.CharField(
        help_text="비밀번호",
        write_only=True,
        required=True,
        validators=[validate_password],
    )

    passwordCheck = serializers.CharField(
        help_text="비밀번호 재입력", write_only=True, required=True
    )  # 비밀번호 확인을 위한 필드

    term_agreed = serializers.BooleanField(required=True)  # 개인정보 동의 필드 추가

    class Meta:
        model = User
        fields = ("username", "password", "passwordCheck", "email", "term_agreed")

    def validate(self, data):
        if data["password"] != data["passwordCheck"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )

        return data

    def validate_term_agreed(self, data):
        if data is not True:
            raise serializers.ValidationError("You must agree to the terms.")
        return data

    def create(
        self, validated_data
    ):  # CREATE 요청에 대해 create 메소드를 오버라이딩, 유저를 생성하고 토큰을 생성하게 함.

        term_agreed = validated_data.pop("term_agreed")  # term_agreed를 따로 저장
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
        )

        user.set_password(validated_data["password"])
        user.save()

        # UserProfile 생성하여 개인정보 동의 저장
        UserProfile.objects.create(user=user, term_agreed=term_agreed)
        Token.objects.create(user=user)
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
