import json
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
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

    def test_resolve_period_bounds_uses_fixed_day_windows(self):
        tz = ProductionReportService.resolve_user_timezone(self.user)
        now_utc = timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0))

        expected_days = {
            "week": 7,
            "month": 30,
            "quarter": 90,
            "year": 365,
        }

        for report_range, day_count in expected_days.items():
            with self.subTest(report_range=report_range):
                bounds = ProductionReportService.resolve_period_bounds(
                    report_range=report_range,
                    now_utc=now_utc,
                    tz=tz,
                )

                self.assertEqual(
                    bounds.period_end_local.date(), datetime(2026, 8, 4).date()
                )
                self.assertEqual(
                    bounds.period_start_local.date(),
                    bounds.period_end_local.date() - timedelta(days=day_count),
                )
                self.assertEqual(
                    bounds.previous_end_local.date(),
                    bounds.period_start_local.date() - timedelta(days=1),
                )
                self.assertEqual(
                    bounds.previous_start_local.date(),
                    bounds.previous_end_local.date() - timedelta(days=day_count),
                )

    def test_period_label_displays_rolling_start_and_end_dates(self):
        report = ProductionReportService.build_report(
            user=self.user,
            report_range="month",
            now_utc=timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0)),
        )

        self.assertEqual(report["period"]["label"], "Month: Jul 5, 2026 - Aug 4, 2026")

    def test_resolve_period_bounds_uses_user_local_today(self):
        profile = self.user.profile
        profile.timezone = "America/Los_Angeles"
        profile.save(update_fields=["timezone"])

        tz = ProductionReportService.resolve_user_timezone(self.user)
        now_utc = timezone.make_aware(datetime(2026, 8, 5, 1, 30, 0))
        bounds = ProductionReportService.resolve_period_bounds(
            report_range="week",
            now_utc=now_utc,
            tz=tz,
        )

        self.assertEqual(bounds.period_end_local.date(), datetime(2026, 8, 4).date())

    def test_daily_gph_telemetry_aggregates_multiple_missions_per_day(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 8, 2, 10, 0, 0)),
            shift_end=timezone.make_aware(datetime(2026, 8, 2, 12, 0, 0)),
            is_completed=True,
            hours_on_duty_not_driving=2,
            total_gallons=100,
        )
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 8, 2, 17, 0, 0)),
            shift_end=timezone.make_aware(datetime(2026, 8, 2, 18, 0, 0)),
            is_completed=True,
            hours_on_duty_not_driving=1,
            total_gallons=200,
        )

        telemetry = ProductionReportService.build_daily_gph_telemetry(
            user=self.user,
            window_days=30,
            now_utc=timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0)),
        )

        point = next(
            row for row in telemetry["series"] if row["local_date"] == "2026-08-02"
        )
        self.assertEqual(point["gph"], 100.0)
        self.assertEqual(point["included_missions"], 2)

    def test_daily_gph_telemetry_preserves_internal_gaps_and_trims_trailing_no_data(
        self,
    ):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 8, 1, 9, 0, 0)),
            is_completed=True,
            hours_on_duty_not_driving=2,
            total_gallons=120,
        )
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 8, 3, 9, 0, 0)),
            is_completed=True,
            hours_on_duty_not_driving=3,
            total_gallons=210,
        )

        telemetry = ProductionReportService.build_daily_gph_telemetry(
            user=self.user,
            window_days=30,
            now_utc=timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0)),
        )

        self.assertEqual(telemetry["latest_data_date"], "2026-08-03")
        self.assertEqual(telemetry["series"][-1]["local_date"], "2026-08-03")
        gap_point = next(
            row for row in telemetry["series"] if row["local_date"] == "2026-08-02"
        )
        self.assertIsNone(gap_point["gph"])

    def test_daily_gph_telemetry_uses_local_shift_start_bucket(self):
        profile = self.user.profile
        profile.timezone = "America/New_York"
        profile.save(update_fields=["timezone"])

        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 8, 5, 2, 30, 0)),
            is_completed=True,
            hours_on_duty_not_driving=2,
            total_gallons=200,
        )

        telemetry = ProductionReportService.build_daily_gph_telemetry(
            user=self.user,
            window_days=30,
            now_utc=timezone.make_aware(datetime(2026, 8, 5, 12, 0, 0)),
        )

        point = next(row for row in telemetry["series"] if row["gph"] is not None)
        self.assertEqual(point["local_date"], "2026-08-04")

    def test_daily_gph_telemetry_returns_empty_series_when_no_valid_data(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.make_aware(datetime(2026, 8, 4, 9, 0, 0)),
            is_completed=True,
            hours_on_duty_not_driving=0.1,
            total_gallons=100,
        )

        telemetry = ProductionReportService.build_daily_gph_telemetry(
            user=self.user,
            window_days=30,
            now_utc=timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0)),
        )

        self.assertEqual(telemetry["series"], [])


class ProductionReportEmailServiceTests(TestCase):
    def test_email_subject_uses_rolling_period_label(self):
        from missionlog.services.production_report_email_service import (
            ProductionReportEmailService,
        )

        payload = {
            "period": {
                "range": "week",
                "type_label": "Weekly",
                "window_days": 7,
                "start_date": datetime(2026, 7, 28).date(),
                "end_date": datetime(2026, 8, 4).date(),
                "label": "Week: Jul 28, 2026 - Aug 4, 2026",
            },
            "summary": {
                "total_gallons": 1000,
                "total_hours": 10,
                "overall_gph": 100,
                "included_count": 2,
                "excluded_count": 0,
                "excluded_reason_counts": {},
                "best_bucket": None,
                "lowest_bucket": None,
            },
            "comparison_text": "No change from the previous equivalent period",
            "chart_png_bytes": (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
                b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
        }

        result = ProductionReportEmailService.send_report(
            recipient_email="ops@example.com",
            report_payload=payload,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Production Report - Weekly (Jul 28, 2026 to Aug 04, 2026)",
        )
        self.assertIn("Report Type: Weekly", mail.outbox[0].body)
        self.assertIn(
            "Date Range (local): July 28, 2026 - August 4, 2026",
            mail.outbox[0].body,
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
        self.assertIn("check your email", payload["data"]["message"])
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

    @patch("missionlog.views.report_email_views.ProductionReportDispatcher.enqueue")
    def test_dedupes_same_period_but_allows_next_rolled_period(
        self,
        mock_enqueue,
    ):
        mock_enqueue.return_value = True
        client, csrf_token = self._csrf_client(user=self.user)

        with patch("missionlog.views.report_email_views.timezone.now") as mock_now:
            mock_now.return_value = timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0))
            first_response = client.post(
                self.url,
                data=json.dumps({"range": "month"}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )
        self.assertEqual(first_response.status_code, 202)
        self.assertEqual(ProductionReportEmailAudit.objects.count(), 1)

        with patch("missionlog.views.report_email_views.timezone.now") as mock_now:
            mock_now.return_value = timezone.make_aware(datetime(2026, 8, 4, 12, 0, 0))
            second_same_period = client.post(
                self.url,
                data=json.dumps({"range": "month"}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )
        self.assertEqual(second_same_period.status_code, 202)
        self.assertEqual(ProductionReportEmailAudit.objects.count(), 1)

        with patch("missionlog.views.report_email_views.timezone.now") as mock_now:
            mock_now.return_value = timezone.make_aware(datetime(2026, 8, 5, 12, 0, 0))
            next_rolled_period = client.post(
                self.url,
                data=json.dumps({"range": "month"}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )
        self.assertEqual(next_rolled_period.status_code, 202)
        self.assertEqual(ProductionReportEmailAudit.objects.count(), 2)
