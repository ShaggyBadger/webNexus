from django.urls import path

from .views import CurrentWeatherAPIView

app_name = "weather"

urlpatterns = [
    path("api/current/", CurrentWeatherAPIView.as_view(), name="current"),
]
