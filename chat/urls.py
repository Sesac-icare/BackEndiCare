from django.urls import path
from .views import  UnifiedChatAPIView

urlpatterns = [
    path("unified/", UnifiedChatAPIView.as_view(), name="unified-chat"),
]

