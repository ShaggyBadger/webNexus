from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import FeedbackClickEvent, FeedbackReport
from .views import FeedbackInitiateAPIView, FeedbackSubmitAPIView


class FeedbackApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="feedback_user",
            password="pass12345",
        )

    def test_initiate_feedback_creates_initiated_report(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("feedback:initiate_api"),
            {
                "url": "/siteintel/location/10/?tab=tanks",
                "viewport_size": "390x844",
                "page_metadata": {"site_id": 10, "tank_index": 1},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        click_event = FeedbackClickEvent.objects.get(
            id=payload["data"]["click_event_id"]
        )
        self.assertEqual(click_event.user_id, self.user.id)
        self.assertEqual(click_event.page_metadata["site_id"], 10)

    def test_initiate_feedback_allows_anonymous_reports(self):
        response = self.client.post(
            reverse("feedback:initiate_api"),
            {
                "url": "/homepage/contact/",
                "viewport_size": "390x844",
                "page_metadata": {"source": "anon"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        click_event = FeedbackClickEvent.objects.get(
            id=response.json()["data"]["click_event_id"]
        )
        self.assertIsNone(click_event.user_id)

    @override_settings(FEEDBACK_MAX_METADATA_BYTES=64)
    def test_initiate_feedback_rejects_oversized_metadata(self):
        response = self.client.post(
            reverse("feedback:initiate_api"),
            {
                "url": "/siteintel/location/10/",
                "page_metadata": {"blob": "x" * 1000},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "validation_error")

    def test_feedback_views_define_throttle_scopes(self):
        self.assertEqual(FeedbackInitiateAPIView.throttle_scope, "feedback_initiate")
        self.assertEqual(FeedbackSubmitAPIView.throttle_scope, "feedback_submit")

    def test_submit_feedback_creates_submitted_report(self):
        click_event = FeedbackClickEvent.objects.create(
            user=self.user,
            url="/tankgauge/",
            page_metadata={"site_id": 88},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("feedback:submit_api"),
            {
                "click_event_id": click_event.id,
                "category": FeedbackReport.CATEGORY_UI_GLITCH,
                "message": "Button does not respond on mobile.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        report = FeedbackReport.objects.get(id=payload["id"])
        click_event.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(report.status, FeedbackReport.STATUS_SUBMITTED)
        self.assertEqual(report.category, FeedbackReport.CATEGORY_UI_GLITCH)
        self.assertEqual(report.message, "Button does not respond on mobile.")
        self.assertEqual(report.click_event_id, click_event.id)
        self.assertIsNotNone(report.submitted_at)
        self.assertTrue(click_event.is_submitted)

    def test_submit_feedback_merges_submitted_context_metadata(self):
        click_event = FeedbackClickEvent.objects.create(
            user=self.user,
            url="/tankgauge/",
            page_metadata={"site_id": 88},
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("feedback:submit_api"),
            {
                "click_event_id": click_event.id,
                "category": FeedbackReport.CATEGORY_GENERAL,
                "message": "context attached",
                "page_metadata": {"active_tab": "tank_profile"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report = FeedbackReport.objects.get(id=response.json()["data"]["id"])
        report.refresh_from_db()
        self.assertEqual(report.page_metadata["site_id"], 88)
        self.assertEqual(
            report.page_metadata["submitted_context"]["active_tab"], "tank_profile"
        )

    def test_submit_feedback_forbidden_for_different_user(self):
        other_user = get_user_model().objects.create_user(
            username="other_user",
            password="pass12345",
        )
        click_event = FeedbackClickEvent.objects.create(
            user=other_user,
            url="/dms/",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("feedback:submit_api"),
            {
                "click_event_id": click_event.id,
                "category": FeedbackReport.CATEGORY_GENERAL,
                "message": "test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertEqual(payload["error"]["code"], "forbidden")

    def test_submit_feedback_fails_when_click_event_missing(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("feedback:submit_api"),
            {
                "click_event_id": 999999,
                "category": FeedbackReport.CATEGORY_GENERAL,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["error"]["code"], "feedback_click_not_found")


class FeedbackAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass12345",
        )
        self.client.force_login(self.admin_user)

    def test_feedback_operations_page_loads(self):
        response = self.client.get(reverse("admin:feedback_feedbackreport_operations"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Feedback Operations")

    def test_feedback_click_events_changelist_loads(self):
        response = self.client.get(
            reverse("admin:feedback_feedbackclickevent_changelist")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
