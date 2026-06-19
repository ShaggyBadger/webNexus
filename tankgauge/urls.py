from django.urls import path
from .views import (
    closest_store_api,
    delivery_form,
    delivery_submit,
    CalculateTankAPIView,
    EstimationHealthAPIView,
)

app_name = "tankgauge"

urlpatterns = [
    # API endpoints
    path("api/closest-store/", closest_store_api, name="closest_store_api"),
    # Page views
    path("delivery/", delivery_form, name="delivery_form"),
    path("delivery/submit/", delivery_submit, name="delivery_submit"),
    path(
        "api/calculate-tank/", CalculateTankAPIView.as_view(), name="calculate_tank_api"
    ),
    path(
        "api/estimation-health/",
        EstimationHealthAPIView.as_view(),
        name="estimation_health_api",
    ),
]
