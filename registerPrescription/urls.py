from django.urls import path
from .views import ClovaOCRAPIView

urlpatterns = [
    path('ocr/', ClovaOCRAPIView.as_view(), name='clova-ocr'),
]

