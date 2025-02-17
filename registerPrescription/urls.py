from django.urls import path
from .views import (
    ClovaOCRAPIView,
    PrescriptionListView,
    PrescriptionListByDateView,
    PrescriptionDeleteView,
    PrescriptionDetailView,
)

urlpatterns = [
    path("ocr/", ClovaOCRAPIView.as_view(), name="clova-ocr"),
    path("list/", PrescriptionListView.as_view(), name="prescription-list"),
    path(
        "by-date/",
        PrescriptionListByDateView.as_view(),
        name="prescription-list-by-date",
    ),
    path(
        "<int:prescription_id>/",
        PrescriptionDeleteView.as_view(),
        name="prescription-delete",
    ),
    path(
        "detail/<int:prescription_id>/",
        PrescriptionDetailView.as_view(),
        name="prescription-detail",
    ),
]
