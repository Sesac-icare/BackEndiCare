from django.urls import path, include

urlpatterns = [
    # ... 다른 URL 패턴들
    path('hospitals/', include('searchHospital.urls')),
] 