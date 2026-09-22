import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from tankgauge.views.api.error_contract import drf_error_response, drf_success_response

from .serializers import WeatherRequestSerializer
from .services.weather_service import get_weather

logger = logging.getLogger("weather")


class CurrentWeatherAPIView(APIView):
    """Return cached or freshly fetched weather for supplied coordinates."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "weather_current"

    def post(self, request):
        serializer = WeatherRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return drf_error_response(
                request=request,
                code="invalid_coordinates",
                message="Valid latitude and longitude are required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )
        data, response_status = get_weather(**serializer.validated_data)
        if response_status != status.HTTP_200_OK:
            code = data.get("error_code", "weather_unavailable")
            response_code = (
                "weather_budget_exhausted"
                if code == "weather_budget_exhausted"
                else "weather_unavailable"
            )
            return drf_error_response(
                request=request,
                code=response_code,
                message="Weather is currently unavailable.",
                status_code=response_status,
            )
        return drf_success_response(data=data)
