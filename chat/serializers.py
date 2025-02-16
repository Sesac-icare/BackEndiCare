from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    """질문을 처리하는 Serializer"""

    question = serializers.CharField(required=True, min_length=1, max_length=500)
    session_id = serializers.CharField(required=False, default="default_session")


class ChatResponseSerializer(serializers.Serializer):
    """GPT 응답을 반환하는 Serializer"""

    response_code = serializers.IntegerField()
    message = serializers.CharField()


class NewsSearchRequestSerializer(serializers.Serializer):
    """뉴스 검색을 위한 Serializer"""

    query = serializers.CharField(required=True, min_length=1, max_length=200)


class NewsSearchResponseSerializer(serializers.Serializer):
    """뉴스 검색 결과를 반환하는 Serializer"""

    title = serializers.CharField()
    link = serializers.URLField()
    source = serializers.CharField()
    published_date = serializers.CharField()
