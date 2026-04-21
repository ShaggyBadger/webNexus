from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.tactical_login, name='login'),
    path('logout/', views.tactical_logout, name='logout'),
    path('signup/', views.tactical_signup, name='signup'),
    path('profile/', views.tactical_profile, name='profile'),
    path('profile/edit/', views.tactical_profile_edit, name='profile_edit'),
    path('password_change/', views.tactical_password_change, name='password_change'),
]
