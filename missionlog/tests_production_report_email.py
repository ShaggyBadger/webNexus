import json
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from missionlog.models import Mission, ProductionReportEmailAudit
from missionlog.services.production_report_service import ProductionReportService


class ProductionReportServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="report_user",
            email="report@example.com",
            password="pass12345",
        )
        Profile.objects.update_or_create(
            user=self.user,
            defaults={"timezone": "UTC"},
        )

    def test_weighted_overall_gph_uses_total_hours_not_mean_of_missions(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 1, 14, 8, 0, 0)),
            shift_end=timezone.make_aware(datetime(2026, 1, 14, 10, 0, 0)),
            is_completed=True,
            hours_on_duty=2,
            hours_on_duty_not_driving=2,
            total_gallons=100,
        )
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 1, 21, 8, 0, 0)),
            shift_end=timezone.make_aware(datetime(2026, 1, 21, 16, 0, 0)),
            is_completed=True,
            hours_on_duty=8,
            hours_on_duty_not_driving=8,
            total_gallons=800,
        )

        report = ProductionReportService.build_report(
            user=self.user,
            report_range="month",
            now_utc=timezone.make_aware(datetime(2026, 1, 31, 12, 0, 0)),
        )

        self.assertEqual(report["summary"]["overall_gph"], 90.0)
        self.assertEqual(report["summary"]["included_count"], 2)
        self.assertEqual(report["summary"]["excluded_count"], 0)

    def test_gph_uses_on_duty_not_driving_hours(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 1, 14, 8, 0, 0)),
            shift_end=timezone.make_aware(datetime(2026, 1, 14, 18, 0, 0)),
            is_completed=True,
            hours_on_duty=10,
            hours_on_duty_not_driving=2,
            total_gallons=100,
        )

        report = ProductionReportService.build_report(
            user=self.user,
            report_range="month",
            now_utc=timezone.make_aware(datetime(2026, 1, 31, 12, 0, 0)),
        )

        self.assertEqual(report["summary"]["overall_gph"], 50.0)

    def test_hours_below_floor_are_excluded(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 1, 14, 8, 0, 0)),
            shift_end=timezone.make_aware(datetime(2026, 1, 14, 8, 10, 0)),
            is_completed=True,
            hours_on_duty=0.1,
            hours_on_duty_not_driving=0.1,
            total_gallons=300,
        )

        report = ProductionReportService.build_report(
            user=self.user,
            report_range="month",
            now_utc=timezone.make_aware(datetime(2026, 1, 31, 12, 0, 0)),
        )

        self.assertIsNone(report["summary"]["overall_gph"])
        self.assertEqual(report["summary"]["included_count"], 0)
        self.assertEqual(report["summary"]["excluded_count"], 1)
        self.assertIn(
            "N/A - invalid or insufficient on-duty-not-driving hours",
            report["summary"]["excluded_reason_counts"],
        )


class ProductionReportEmailAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api_user",
            email="api_user@example.com",
            password="pass12345",
        )
        Profile.objects.update_or_create(
            user=self.user,
            defaults={"timezone": "UTC"},
        )
        self.url = reverse("missionlog:production_report_email")

    def _csrf_client(self, user=None):
        client = Client(enforce_csrf_checks=True)
        if user is not None:
            client.force_login(user)
            client.get(reverse("missionlog:spa_index"))
            csrf_token = client.cookies["csrftoken"].value
        else:
            csrf_token = "a" * 32
            client.cookies["csrftoken"] = csrf_token
        return client, csrf_token

    def test_requires_authentication(self):
        client = Client()
        response = client.post(
            self.url,
            data=json.dumps({"range": "month"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_csrf_returns_403(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            self.url,
            data=json.dumps({"range": "month"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    @patch("missionlog.views.report_email_views.ProductionReportDispatcher.enqueue")
    def test_queues_request_and_returns_202(self, mock_enqueue):
        mock_enqueue.return_value = True
        client, csrf_token = self._csrf_client(user=self.user)

        response = client.post(
            self.url,
            data=json.dumps({"range": "month"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIn("Check your email", payload["data"]["message"])
        self.assertEqual(ProductionReportEmailAudit.objects.count(), 1)

    @patch("missionlog.views.report_email_views.ProductionReportDispatcher.enqueue")
    def test_enqueue_failure_returns_503(self, mock_enqueue):
        mock_enqueue.return_value = False
        client, csrf_token = self._csrf_client(user=self.user)

        response = client.post(
            self.url,
            data=json.dumps({"range": "month"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "enqueue_unavailable")

    @patch("missionlog.views.report_email_views.ProductionReportDispatcher.enqueue")
    def test_recipient_fields_are_rejected(self, mock_enqueue):
        mock_enqueue.return_value = True
        client, csrf_token = self._csrf_client(user=self.user)

        response = client.post(
            self.url,
            data=json.dumps({"range": "month", "email": "hacker@example.com"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "recipient_not_allowed")

    @patch("missionlog.views.report_email_views.ProductionReportDispatcher.enqueue")
    def test_invalid_range_returns_400(self, mock_enqueue):
        mock_enqueue.return_value = True
        client, csrf_token = self._csrf_client(user=self.user)

        response = client.post(
            self.url,
            data=json.dumps({"range": "daily"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_range")

    @patch("missionlog.views.report_email_views.ProductionReportDispatcher.enqueue")
    def test_missing_account_email_returns_422(self, mock_enqueue):
        mock_enqueue.return_value = True
        self.user.email = ""
        self.user.save(update_fields=["email"])
        client, csrf_token = self._csrf_client(user=self.user)

        response = client.post(
            self.url,
            data=json.dumps({"range": "month"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "verified_email_required")
