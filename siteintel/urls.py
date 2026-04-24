from django.urls import path
from . import views

app_name = 'siteintel'

urlpatterns = [
    path('', views.SiteIntelDashboardView.as_view(), name='dashboard'),
    path('propose/', views.StoreUpdateCreateView.as_view(), name='proposal_create'),
    path('proposals/', views.StoreUpdateListView.as_view(), name='proposal_list'),
    
    # AJAX Intel Endpoints
    path('api/tank-search/', views.tank_type_search_api, name='api_tank_search'),
    path('api/store-lookup/', views.store_lookup_api, name='api_store_lookup'),
    path('api/reverse-geocode/', views.reverse_geocode_api, name='api_reverse_geocode'),
    path('api/proximity-check/', views.proximity_check_api, name='api_proximity_check'),
]
