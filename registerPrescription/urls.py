from django.urls import path
from .views import OCRAPIView, PrescriptionListView, PrescriptionDetailView


urlpatterns = [
    path('ocr/', OCRAPIView.as_view(), name='ocr_api'),
    path('prescriptions/', PrescriptionListView.as_view(), name='prescription-list'),
    path('prescriptions/<int:pk>/', PrescriptionDetailView.as_view(), name='prescription-detail'),
]
