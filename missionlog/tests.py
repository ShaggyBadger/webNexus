import json
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from missionlog.models import (
    FuelType,
    LoadDelivery,
    Mission,
    OrderNumber,
    PurchaseOrder,
    TruckFuelLog,
)


class MissionResumeBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="operator", password="pass12345")
        self.client.force_login(self.user)

    def test_active_mission_returns_latest_incomplete_without_time_cutoff(self):
        old_incomplete = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(days=3),
            is_completed=False,
        )
        latest_incomplete = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(days=1),
            is_completed=False,
        )
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.now(),
            is_completed=True,
        )

        response = self.client.get(reverse("missionlog:active_mission"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["data"]["active"])
        self.assertEqual(payload["data"]["mission"]["id"], latest_incomplete.id)
        self.assertNotEqual(payload["data"]["mission"]["id"], old_incomplete.id)

    def test_active_mission_serializes_not_driving_hours(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(hours=5),
            is_completed=False,
            hours_on_duty_not_driving=1.75,
        )

        response = self.client.get(reverse("missionlog:active_mission"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["data"]["mission"]["id"], mission.id)
        self.assertEqual(payload["data"]["mission"]["hours_on_duty_not_driving"], 1.75)

    def test_active_mission_returns_inactive_when_none_exist(self):
        response = self.client.get(reverse("missionlog:active_mission"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["data"]["active"])

    def test_active_mission_returns_inactive_when_all_completed(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.now(),
            is_completed=True,
        )
        response = self.client.get(reverse("missionlog:active_mission"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["data"]["active"])

    def test_start_mission_blocks_when_old_incomplete_exists(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(days=4),
            is_completed=False,
        )

        response = self.client.post(
            reverse("missionlog:mission_list_or_create"),
            data=json.dumps({"start_miles": 100}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "active_mission_exists")
        self.assertIn("active mission", payload["error"]["message"].lower())

    def test_post_trip_partial_save_returns_existing_old_incomplete(self):
        existing = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(days=5),
            is_completed=False,
        )

        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "advanced",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "active_mission_exists")
        self.assertEqual(payload["error"]["details"]["mission_id"], existing.id)

    def test_delete_active_mission_removes_it_and_resets_active_lookup(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(hours=1),
            is_completed=False,
        )

        response = self.client.delete(
            reverse("missionlog:mission_detail_or_update", kwargs={"pk": mission.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Mission.objects.filter(id=mission.id).exists())

        active_response = self.client.get(reverse("missionlog:active_mission"))
        self.assertEqual(active_response.status_code, 200)
        payload = active_response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["data"]["active"])


class MissionHistoryDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="history_owner", password="pass12345"
        )
        self.other_user = User.objects.create_user(
            username="history_other", password="pass12345"
        )
        self.fuel_type = FuelType.objects.create(name="Regular", abbreviation="REG")

    def _csrf_client(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        client.get(reverse("missionlog:spa_index"))
        csrf_token = client.cookies["csrftoken"].value
        return client, csrf_token

    def _build_completed_mission_graph(self, user):
        mission = Mission.objects.create(
            user=user,
            shift_start=timezone.now() - timedelta(days=1),
            shift_end=timezone.now(),
            is_completed=True,
            total_gallons=Decimal("100.00"),
            hours_on_duty_not_driving=Decimal("2.00"),
        )
        order = OrderNumber.objects.create(
            mission=mission, order_number=f"ORD-{mission.id}"
        )
        purchase_order = PurchaseOrder.objects.create(
            order_parent=order,
            po_number=900000 + mission.id,
        )
        LoadDelivery.objects.create(
            purchase_order=purchase_order,
            fuel_type=self.fuel_type,
            gross_gal=100,
        )
        TruckFuelLog.objects.create(
            mission=mission,
            gallons=Decimal("10.000"),
            price_per_gallon=Decimal("3.250"),
        )
        return mission

    def test_history_delete_requires_authentication(self):
        mission = self._build_completed_mission_graph(self.user)
        response = self.client.delete(
            reverse("missionlog:mission_history_delete", kwargs={"pk": mission.id})
        )
        self.assertEqual(response.status_code, 302)

    def test_history_delete_requires_csrf(self):
        mission = self._build_completed_mission_graph(self.user)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.delete(
            reverse("missionlog:mission_history_delete", kwargs={"pk": mission.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_user_can_delete_own_completed_history_mission_with_cascade(self):
        mission = self._build_completed_mission_graph(self.user)
        client, csrf_token = self._csrf_client(self.user)

        response = client.delete(
            reverse("missionlog:mission_history_delete", kwargs={"pk": mission.id}),
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["data"]["mission_id"], mission.id)
        self.assertFalse(Mission.objects.filter(id=mission.id).exists())
        self.assertEqual(OrderNumber.objects.count(), 0)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(LoadDelivery.objects.count(), 0)
        self.assertEqual(TruckFuelLog.objects.count(), 0)

    def test_user_cannot_delete_another_users_completed_history_mission(self):
        mission = self._build_completed_mission_graph(self.user)
        client, csrf_token = self._csrf_client(self.other_user)

        response = client.delete(
            reverse("missionlog:mission_history_delete", kwargs={"pk": mission.id}),
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Mission.objects.filter(id=mission.id).exists())

    def test_history_delete_rejects_incomplete_mission(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(hours=2),
            is_completed=False,
        )
        client, csrf_token = self._csrf_client(self.user)

        response = client.delete(
            reverse("missionlog:mission_history_delete", kwargs={"pk": mission.id}),
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "history_delete_incomplete_mission")
        self.assertTrue(Mission.objects.filter(id=mission.id).exists())

    def test_replacement_entry_with_past_shift_start_appears_in_history_order(self):
        self.client.force_login(self.user)
        older_shift_start = (timezone.now() - timedelta(days=7)).isoformat()
        newer_shift_start = (timezone.now() - timedelta(days=1)).isoformat()

        older_create_response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": older_shift_start,
                    "entry_type": "basic",
                    "is_completed": True,
                    "total_gallons": "50",
                    "hours_on_duty_not_driving": "1.5",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(older_create_response.status_code, 201)

        newer_create_response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": newer_shift_start,
                    "entry_type": "basic",
                    "is_completed": True,
                    "total_gallons": "60",
                    "hours_on_duty_not_driving": "2.0",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(newer_create_response.status_code, 201)

        history_response = self.client.get(reverse("missionlog:mission_list_or_create"))
        self.assertEqual(history_response.status_code, 200)
        missions = history_response.json()["data"]["missions"]
        self.assertGreaterEqual(len(missions), 2)
        self.assertGreater(missions[0]["shift_start"], missions[1]["shift_start"])


class MissionTimezoneNormalizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tzuser", password="pass12345")
        self.client.force_login(self.user)

    def _set_profile_timezone(self, tz_name):
        Profile.objects.update_or_create(user=self.user, defaults={"timezone": tz_name})

    def test_post_trip_create_naive_shift_start_uses_profile_timezone(self):
        self._set_profile_timezone("America/New_York")

        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": "2026-08-04T01:30",
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "100",
                    "hours_on_duty_not_driving": "2.0",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertEqual(
            mission.shift_start,
            datetime(2026, 8, 4, 5, 30, tzinfo=datetime_timezone.utc),
        )

    def test_legacy_create_aware_shift_start_is_not_localized_twice(self):
        self._set_profile_timezone("America/New_York")

        response = self.client.post(
            reverse("missionlog:mission_list_or_create"),
            data=json.dumps({"shift_start": "2026-08-04T01:30:00-07:00"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertEqual(
            mission.shift_start,
            datetime(2026, 8, 4, 8, 30, tzinfo=datetime_timezone.utc),
        )

    def test_invalid_datetime_input_returns_stable_error(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": "not-a-date",
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "100",
                    "hours_on_duty_not_driving": "2.0",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "invalid_datetime_input")
        self.assertEqual(payload["error"]["details"]["field"], "shift_start")

    def test_post_trip_update_preserves_shift_start_when_omitted(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=datetime(2026, 8, 4, 12, 0, tzinfo=datetime_timezone.utc),
            is_completed=False,
            entry_type="advanced",
        )

        response = self.client.put(
            reverse("missionlog:post_trip_update", kwargs={"pk": mission.id}),
            data=json.dumps({"entry_type": "advanced", "deliveries": []}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(
            mission.shift_start,
            datetime(2026, 8, 4, 12, 0, tzinfo=datetime_timezone.utc),
        )

    def test_complete_mission_normalizes_naive_shift_end_with_user_timezone(self):
        self._set_profile_timezone("America/New_York")
        mission = Mission.objects.create(
            user=self.user,
            shift_start=datetime(2026, 8, 4, 5, 30, tzinfo=datetime_timezone.utc),
            is_completed=False,
        )

        response = self.client.post(
            reverse("missionlog:complete_mission", kwargs={"pk": mission.id}),
            data=json.dumps({"shift_end": "2026-08-04T10:00"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(
            mission.shift_end,
            datetime(2026, 8, 4, 14, 0, tzinfo=datetime_timezone.utc),
        )

    def test_agent_info_includes_resolved_timezone(self):
        self._set_profile_timezone("America/Los_Angeles")

        response = self.client.get(reverse("missionlog:agent_info"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["timezone"], "America/Los_Angeles")
        self.assertEqual(payload["data"]["email"], self.user.email)

    def test_invalid_profile_timezone_falls_back_to_project_timezone(self):
        self._set_profile_timezone("Invalid/Timezone")

        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": "2026-08-04T01:30",
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "100",
                    "hours_on_duty_not_driving": "2.0",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertEqual(
            mission.shift_start,
            datetime(2026, 8, 4, 1, 30, tzinfo=datetime_timezone.utc),
        )


class MissionGphTelemetryEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sparkuser", password="pass12345")
        self.other_user = User.objects.create_user(
            username="sparkother", password="pass12345"
        )
        Profile.objects.update_or_create(
            user=self.user,
            defaults={"timezone": "UTC"},
        )
        self.url = reverse("missionlog:production_gph_telemetry")

    def test_requires_authentication(self):
        response = self.client.get(f"{self.url}?window=30")
        self.assertEqual(response.status_code, 302)

    def test_rejects_unsupported_window(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{self.url}?window=7")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_window")

    def test_returns_only_authenticated_users_series(self):
        Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(days=2),
            is_completed=True,
            hours_on_duty_not_driving=2,
            total_gallons=200,
        )
        Mission.objects.create(
            user=self.other_user,
            shift_start=timezone.now() - timedelta(days=2),
            is_completed=True,
            hours_on_duty_not_driving=2,
            total_gallons=800,
        )

        self.client.force_login(self.user)
        response = self.client.get(f"{self.url}?window=30")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        non_null_points = [row for row in payload["series"] if row["gph"] is not None]
        self.assertEqual(len(non_null_points), 1)
        self.assertEqual(non_null_points[0]["gph"], 100.0)


class MissionLogShellAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shelluser", password="pass12345")

    def test_shell_requires_login(self):
        response = self.client.get(reverse("missionlog:spa_index"))
        self.assertEqual(response.status_code, 302)

    def test_shell_renders_django_template_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("missionlog:spa_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRODUCTION OPS")


class PostTripPayloadHandlingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="payloaduser", password="pass12345"
        )
        self.client.force_login(self.user)

    def test_post_trip_create_keeps_blank_start_end_miles_empty(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "advanced",
                    "start_miles": "",
                    "end_miles": "",
                    "total_miles": "",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertIsNone(mission.start_miles)
        self.assertIsNone(mission.end_miles)

    def test_post_trip_create_persists_three_decimal_truck_fuel_values(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "advanced",
                    "deliveries": [],
                    "truck_fuel": {
                        "gallons": "40.125",
                        "price_per_gallon": "3.219",
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        fuel_log = mission.fuel_logs.get()
        self.assertEqual(fuel_log.gallons, Decimal("40.125"))
        self.assertEqual(fuel_log.price_per_gallon, Decimal("3.219"))

    def test_post_trip_create_calculates_end_miles_from_start_and_total(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "advanced",
                    "start_miles": "1000",
                    "total_miles": "150",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertEqual(mission.start_miles, 1000)
        self.assertEqual(mission.end_miles, 1150)
        self.assertEqual(mission.total_miles, 150)

    def test_post_trip_create_respects_explicit_end_miles_without_total(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "advanced",
                    "start_miles": "1000",
                    "end_miles": "1200",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertEqual(mission.start_miles, 1000)
        self.assertEqual(mission.end_miles, 1200)
        self.assertEqual(mission.total_miles, 200)

    def test_post_trip_update_recalculates_mileage_bounds(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now(),
            start_miles=1000,
            end_miles=1100,
            is_completed=False,
        )

        response = self.client.put(
            reverse("missionlog:post_trip_update", kwargs={"pk": mission.id}),
            data=json.dumps(
                {
                    "start_miles": "1000",
                    "total_miles": "250",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(mission.start_miles, 1000)
        self.assertEqual(mission.end_miles, 1250)
        self.assertEqual(mission.total_miles, 250)


class BasicAdvancedModeTests(TestCase):
    """
    Tests for the Basic / Advanced mode feature on Mission logs.

    Basic mode: exactly 3 required fields (shift_start, total_gallons,
    hours_on_duty_not_driving). Advanced mode: itemised delivery tracking.
    Upgrade is one-way (basic → advanced). Downgrade is prohibited.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="modeuser", password="pass12345")
        self.client.force_login(self.user)

    # ------------------------------------------------------------------
    # Basic mode creation
    # ------------------------------------------------------------------

    def test_basic_mode_creates_mission_with_three_required_fields(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "9500",
                    "hours_on_duty_not_driving": "1.0",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        mission = Mission.objects.get(id=payload["data"]["mission"]["id"])
        self.assertEqual(mission.entry_type, "basic")
        self.assertEqual(mission.total_gallons, Decimal("9500"))

    def test_basic_progress_can_save_before_final_values_are_known(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "basic",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertFalse(mission.is_completed)
        self.assertIsNone(mission.total_gallons)
        self.assertIsNone(mission.hours_on_duty_not_driving)

    def test_basic_progress_converts_hours_and_minutes_to_decimal_hours(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "basic",
                    "hours_on_duty_not_driving_hours": 4,
                    "hours_on_duty_not_driving_minutes": 21,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertEqual(mission.hours_on_duty_not_driving, Decimal("4.35"))

    def test_basic_completion_converts_hours_and_minutes(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "9500",
                    "hours_on_duty_not_driving_hours": 4,
                    "hours_on_duty_not_driving_minutes": 21,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        mission = Mission.objects.get(id=response.json()["data"]["mission"]["id"])
        self.assertTrue(mission.is_completed)
        self.assertEqual(mission.hours_on_duty_not_driving, Decimal("4.35"))

    def test_basic_completion_rejects_minutes_outside_range(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "9500",
                    "hours_on_duty_not_driving_hours": 4,
                    "hours_on_duty_not_driving_minutes": 60,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "INVALID_BASIC_SUBMISSION")
        self.assertIn(
            "hours_on_duty_not_driving_minutes",
            payload["error"]["details"]["field_errors"],
        )

    def test_basic_mode_missing_total_gallons_returns_400(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": True,
                    "entry_type": "basic",
                    "hours_on_duty_not_driving": "1.0",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "INVALID_BASIC_SUBMISSION")

    def test_basic_mode_negative_total_gallons_returns_400(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "-100",
                    "hours_on_duty_not_driving": "1.0",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "INVALID_BASIC_SUBMISSION")

    def test_basic_mode_missing_hours_not_driving_returns_400(self):
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": True,
                    "entry_type": "basic",
                    "total_gallons": "9500",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "INVALID_BASIC_SUBMISSION")

    # ------------------------------------------------------------------
    # Advanced mode
    # ------------------------------------------------------------------

    def test_advanced_mode_creation_succeeds_without_total_gallons(self):
        """Advanced mode does not require total_gallons; it is computed from deliveries."""
        response = self.client.post(
            reverse("missionlog:post_trip_create"),
            data=json.dumps(
                {
                    "shift_start": timezone.now().isoformat(),
                    "is_completed": False,
                    "entry_type": "advanced",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        mission = Mission.objects.get(id=payload["data"]["mission"]["id"])
        self.assertEqual(mission.entry_type, "advanced")

    # ------------------------------------------------------------------
    # One-way upgrade: basic → advanced
    # ------------------------------------------------------------------

    def test_upgrade_basic_to_advanced_succeeds(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now(),
            is_completed=False,
            entry_type="basic",
            total_gallons=Decimal("9500"),
            hours_on_duty_not_driving=1.0,
        )

        response = self.client.put(
            reverse("missionlog:post_trip_update", kwargs={"pk": mission.id}),
            data=json.dumps(
                {
                    "entry_type": "advanced",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(mission.entry_type, "advanced")

    # ------------------------------------------------------------------
    # Downgrade block: advanced/legacy → basic
    # ------------------------------------------------------------------

    def test_downgrade_advanced_to_basic_is_blocked(self):
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now(),
            is_completed=False,
            entry_type="advanced",
        )

        response = self.client.put(
            reverse("missionlog:post_trip_update", kwargs={"pk": mission.id}),
            data=json.dumps(
                {
                    "entry_type": "basic",
                    "total_gallons": "9000",
                    "hours_on_duty_not_driving": "1.0",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "ILLEGAL_DOWNGRADE")

    def test_downgrade_legacy_null_to_basic_is_blocked(self):
        """Missions with entry_type=None (legacy) must not be downgradable to basic."""
        mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now(),
            is_completed=False,
            entry_type=None,
        )

        response = self.client.put(
            reverse("missionlog:post_trip_update", kwargs={"pk": mission.id}),
            data=json.dumps(
                {
                    "entry_type": "basic",
                    "total_gallons": "9000",
                    "hours_on_duty_not_driving": "1.0",
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "ILLEGAL_DOWNGRADE")
