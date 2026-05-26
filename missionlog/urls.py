from django.urls import path, re_path
from .views import spa_index
from .views import mission_views, po_views, load_views, fuel_views

app_name = "missionlog"

urlpatterns = [
    # Mission Lifecycle API Endpoints
    path(
        "api/missions/",
        mission_views.mission_list_or_create,
        name="mission_list_or_create",
    ),
    path("api/missions/active/", mission_views.active_mission, name="active_mission"),
    path(
        "api/missions/<int:pk>/",
        mission_views.mission_detail_or_update,
        name="mission_detail_or_update",
    ),
    path(
        "api/missions/<int:pk>/complete/",
        mission_views.complete_mission,
        name="complete_mission",
    ),
    # Fuel Types API Endpoint
    path("api/fuel-types/", mission_views.fuel_types_list, name="fuel_types_list"),
    path("api/agent-info/", mission_views.agent_info, name="agent_info"),
    # Order Number API Endpoints
    path(
        "api/missions/<int:mission_id>/orders/",
        mission_views.order_create,
        name="order_create",
    ),
    # Purchase Order API Endpoints
    path("api/orders/<int:order_id>/pos/", po_views.po_create, name="po_create"),
    path(
        "api/pos/<int:pk>/",
        po_views.po_detail_update_delete,
        name="po_detail_update_delete",
    ),
    # Load / Deliveries API Endpoints
    path("api/pos/<int:po_id>/loads/", load_views.load_create, name="load_create"),
    path(
        "api/loads/<int:pk>/", load_views.load_update_delete, name="load_update_delete"
    ),
    # Stores List and Autocomplete / Calibration Chart Lookups
    path("api/stores/", load_views.stores_list, name="stores_list"),
    path(
        "api/stores/tank-chart/", load_views.tank_chart_lookup, name="tank_chart_lookup"
    ),
    # Truck Fuel Log API Endpoints
    path(
        "api/missions/<int:mission_id>/fuel-logs/",
        fuel_views.fuel_log_create,
        name="fuel_log_create",
    ),
    path(
        "api/fuel-logs/<int:pk>/",
        fuel_views.fuel_log_update_delete,
        name="fuel_log_update_delete",
    ),
    # The SPA Catch-All
    # This captures /missionlog/, /missionlog/dashboard, etc., and serves the same index.html
    re_path(r"^.*$", spa_index, name="spa_index"),
]
