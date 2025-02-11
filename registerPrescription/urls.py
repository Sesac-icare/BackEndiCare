# pharmacy/urls.py
from django.urls import path
from .views import OCRAPIView, EnvelopeListView, EnvelopeDetailView

urlpatterns = [
    path('ocr/', OCRAPIView.as_view(), name='ocr_api'),
    path('envelopes/', EnvelopeListView.as_view(), name='envelope_list'),
    path('envelopes/<uuid:envelope_id>/', EnvelopeDetailView.as_view(), name='envelope_detail'),
]
