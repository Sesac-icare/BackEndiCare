from django.urls import path
from .views import ClovaOCRAPIView, PrescriptionListView

urlpatterns = [
    path('ocr/', ClovaOCRAPIView.as_view(), name='clova-ocr'),
    path('list/', PrescriptionListView.as_view(), name='prescription-list'),
]

