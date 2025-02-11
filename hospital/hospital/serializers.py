from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, Child, PharmacyEnvelope

class UserSerializer(serializers.ModelSerializer):
    # 클라이언트가 비밀번호를 전달할 수 있도록 하지만, 응답에는 노출되지 않음
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        # 전달받은 비밀번호를 해싱하여 password_hash에 저장
        password = validated_data.pop('password')
        validated_data['password_hash'] = make_password(password)
        return super().create(validated_data)


class ChildSerializer(serializers.ModelSerializer):
    # 자녀를 생성할 때 user_id를 전달받을 수 있도록 함.
    # 조회 시에는 UserSerializer로 중첩된 사용자 정보를 표시할 수도 있음.
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )

    class Meta:
        model = Child
        fields = ['id', 'child_name', 'user', 'user_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class PharmacyEnvelopeSerializer(serializers.ModelSerializer):
    # 자녀 정보를 포함하여 조회할 수 있도록 함.
    child = ChildSerializer(read_only=True)
    child_id = serializers.PrimaryKeyRelatedField(
        queryset=Child.objects.all(), source='child', write_only=True
    )

    class Meta:
        model = PharmacyEnvelope
        fields = [
            'id',
            'child',
            'child_id',
            'pharmacy_name',
            'prescription_number',
            'prescription_date',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
