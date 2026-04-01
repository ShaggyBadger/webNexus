from django.urls import path
from .views import closest_store_api

app_name = "tankgauge"

urlpatterns = [
    # API endpoints
    path("api/closest-store/", closest_store_api, name="closest_store_api"),
    # Page views (to be built)
    path("delivery/", lambda r: None, name="delivery_form"),  # Placeholder
    path("delivery/submit/", lambda r: None, name="delivery_submit"),  # Placeholder
]
