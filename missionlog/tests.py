import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from missionlog.models import Mission


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
                    "deliveries": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "active_mission_exists")
        self.assertEqual(payload["error"]["details"]["mission_id"], existing.id)


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
        self.assertContains(response, "[ MISSIONLOG CONSOLE ]")


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
