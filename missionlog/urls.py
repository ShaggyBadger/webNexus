from django.urls import path, re_path
from . import views

app_name = "missionlog"

urlpatterns = [
    # API Endpoints
    path("api/missions/", views.mission_api, name="mission_api"),
    
    # The SPA Catch-All
    # This captures /missionlog/, /missionlog/dashboard, etc., and serves the same index.html
    re_path(r"^.*$", views.spa_index, name="spa_index"),
]
