from django.urls import path
from . import views

urlpatterns = [
    path('ocr/', views.OCRAPIView.as_view(), name='ocr_process'),
    path('list/', views.EnvelopeListView.as_view(), name='envelope_list'),
    path('detail/<int:envelope_id>/', views.EnvelopeDetailView.as_view(), name='envelope_detail'),
]
