from django.urls import path

from tankcharts.views import (
    StoreChartPDFAPIView,
    TankChartBatchGenerateAPIView,
    TankChartMetaAPIView,
    TankChartPDFAPIView,
)

app_name = "tankcharts"

urlpatterns = [
    path(
        "chart/<int:store_num>/<int:tank_index>/",
        TankChartPDFAPIView.as_view(),
        name="chart_pdf",
    ),
    path(
        "batch/<int:store_num>/",
        TankChartBatchGenerateAPIView.as_view(),
        name="batch_generate",
    ),
    path(
        "store/<int:store_num>/",
        StoreChartPDFAPIView.as_view(),
        name="store_chart_pdf",
    ),
    path(
        "meta/<int:store_num>/<int:tank_index>/",
        TankChartMetaAPIView.as_view(),
        name="chart_meta",
    ),
]
