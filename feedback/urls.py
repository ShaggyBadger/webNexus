from django.urls import path

from .views import FeedbackInitiateAPIView, FeedbackSubmitAPIView

app_name = "feedback"

urlpatterns = [
    path("api/v1/initiate/", FeedbackInitiateAPIView.as_view(), name="initiate_api"),
    path("api/v1/submit/", FeedbackSubmitAPIView.as_view(), name="submit_api"),
]
