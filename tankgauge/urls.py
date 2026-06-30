from django.urls import path
from .views import (
    closest_store_api,
    delivery_form,
    CalculateTankAPIView,
    EstimationHealthAPIView,
    StoreTanksAPIView,
    TankChartDataAPIView,
)

app_name = "tankgauge"

urlpatterns = [
    # API endpoints
    path("api/closest-store/", closest_store_api, name="closest_store_api"),
    path(
        "api/stores/<int:store_num>/tanks/",
        StoreTanksAPIView.as_view(),
        name="store_tanks_api",
    ),
    path(
        "api/tanks/<int:tank_id>/chart-data/",
        TankChartDataAPIView.as_view(),
        name="tank_chart_data_api",
    ),
    # Page views
    path("delivery/", delivery_form, name="delivery_form"),
    path(
        "api/calculate-tank/", CalculateTankAPIView.as_view(), name="calculate_tank_api"
    ),
    path(
        "api/estimation-health/",
        EstimationHealthAPIView.as_view(),
        name="estimation_health_api",
    ),
]
