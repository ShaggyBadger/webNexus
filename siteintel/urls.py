from django.urls import path
from . import views

app_name = 'siteintel'

urlpatterns = [
    path('', views.SiteIntelDashboardView.as_view(), name='dashboard'),
    path('propose/', views.StoreUpdateCreateView.as_view(), name='proposal_create'),
    path('proposals/', views.StoreUpdateListView.as_view(), name='proposal_list'),
    
    # Site Intelligence Views
    path('site/<int:pk>/', views.LocationDetailView.as_view(), name='location_detail'),
    path('site/<int:location_id>/update-intel/', views.SiteIntelligenceUpdateView.as_view(), name='intel_update'),
    path('site/<int:location_id>/edit-map/', views.MapOverlayUpdateView.as_view(), name='map_edit'),
    path('selector/', views.SiteSelectorView.as_view(), name='selector'),
    path('init-location/<int:store_id>/', views.initialize_location_for_store, name='init_location'),

    # AJAX Intel Endpoints
    path('api/tank-search/', views.tank_type_search_api, name='api_tank_search'),
    path('api/store-lookup/', views.store_lookup_api, name='api_store_lookup'),
    path('api/reverse-geocode/', views.reverse_geocode_api, name='api_reverse_geocode'),
    path('api/proximity-check/', views.proximity_check_api, name='api_proximity_check'),
    path('api/site-lookup/', views.site_lookup_api, name='api_site_lookup'),
    path('api/rack-status/', views.rack_status_api, name='api_rack_status'),
    path('api/rack-checkin/', views.rack_checkin_api, name='api_rack_checkin'),
]
