from django.urls import path
from .views import ChatBotAPIView, GPTChatAPIView, NewsSearchAPIView

urlpatterns = [
    path("chatbot/", ChatBotAPIView.as_view(), name="chatbot"),
    path("gpt-chat/", GPTChatAPIView.as_view(), name="gpt-chat"),
    path("news-search/", NewsSearchAPIView.as_view(), name="news-search"),
]
