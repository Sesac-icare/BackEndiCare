from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, Child, PharmacyEnvelope

class UserSerializer(serializers.ModelSerializer):
    # 클라이언트가 password를 보내지만, 응답에는 포함하지 않음
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['password_hash'] = make_password(password)
        return super().create(validated_data)


class ChildSerializer(serializers.ModelSerializer):
    # 부모 사용자를 지정할 때 user_id 필드를 사용
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Child
        fields = ['id', 'child_name', 'user', 'user_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class PharmacyEnvelopeSerializer(serializers.ModelSerializer):
    # 자녀를 지정할 때 child_id 필드를 사용
    child_id = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all(), source='child', write_only=True)
    child = ChildSerializer(read_only=True)

    class Meta:
        model = PharmacyEnvelope
        fields = [
            'id',
            'pharmacy_name',
            'prescription_number',
            'prescription_date',
            'child',
            'child_id',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
