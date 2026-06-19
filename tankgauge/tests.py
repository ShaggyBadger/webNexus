from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from atg.models import VeederReading, VeederTicket
from missionlog.models import FuelType
from tankgauge.logic.estimation_service import EstimationService
from tankgauge.logic.tank_lookup import (
    get_mapping_resolution_metrics,
    get_store_and_preset_status,
    get_tank_mapping,
    reset_mapping_resolution_metrics,
)
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankEstimation,
    TankType,
    VirtualTankEstimation,
)


class TankLookupTests(TestCase):
    def setUp(self):
        reset_mapping_resolution_metrics()
        self.store_std = Store.objects.create(
            store_num=6949,
            store_name="7-11 Standard Test",
            city="Test City",
            state="TS",
        )
        self.store_other = Store.objects.create(
            store_num=1234,
            store_name="Other Store",
            city="Other City",
            state="OC",
        )
        self.tank_type_reg = TankType.objects.create(
            name="10K Gallon Regular", capacity=10000, max_depth=120
        )
        self.tank_type_dsl = TankType.objects.create(
            name="5K Gallon Diesel", capacity=5000, max_depth=90
        )
        StoreTankMapping.objects.create(
            store=self.store_std,
            tank_type=self.tank_type_reg,
            fuel_type="regular",
        )
        StoreTankMapping.objects.create(
            store=self.store_other,
            tank_type=self.tank_type_dsl,
            fuel_type="diesel",
            tank_index=1,
        )

    def test_get_store_and_preset_status_std(self):
        store, is_preset = get_store_and_preset_status("7-11_STD")
        self.assertEqual(store.store_num, 6949)
        self.assertTrue(is_preset)

    def test_get_store_and_preset_status_normal(self):
        store, is_preset = get_store_and_preset_status("1234")
        self.assertEqual(store.store_num, 1234)
        self.assertFalse(is_preset)

    def test_get_store_and_preset_status_not_found(self):
        store, is_preset = get_store_and_preset_status("9999")
        self.assertIsNone(store)
        self.assertFalse(is_preset)

    def test_get_tank_mapping_success(self):
        store = Store.objects.get(store_num=1234)
        mapping = get_tank_mapping(store, "diesel")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.tank_type.name, "5K Gallon Diesel")

    def test_get_tank_mapping_case_insensitive(self):
        store = Store.objects.get(store_num=1234)
        mapping = get_tank_mapping(store, "DIESEL")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.tank_type.name, "5K Gallon Diesel")

    def test_get_tank_mapping_not_found(self):
        store = Store.objects.get(store_num=1234)
        mapping = get_tank_mapping(store, "regular")
        self.assertIsNone(mapping)

    def test_get_tank_mapping_metrics_strict_and_fallback(self):
        store = Store.objects.get(store_num=1234)

        strict_mapping = get_tank_mapping(store, "diesel", tank_index=1)
        self.assertIsNotNone(strict_mapping)

        fallback_mapping = get_tank_mapping(store, "diesel")
        self.assertIsNotNone(fallback_mapping)

        metrics = get_mapping_resolution_metrics()
        self.assertEqual(metrics["strict_match"], 1)
        self.assertEqual(metrics["fallback_no_index_provided"], 1)


@override_settings(TANKGAUGE_ENABLE_GENERATED_CHART_FALLBACK=False)
class GeneratedChartFallbackDisabledTests(TestCase):
    def test_generated_chart_source_ignored_when_flag_disabled(self):
        from tankgauge.logic.calculations import _get_volume_from_chart

        store = Store.objects.create(store_num=9999, store_name="NoChartStore")
        tank_type = TankType.objects.create(name="NoChartType")
        value = _get_volume_from_chart(
            tank_type=tank_type,
            depth=10.0,
            store=store,
            tank_index=1,
            prefer_generated=True,
        )
        self.assertEqual(value, 0.0)


class ConfidenceGateTests(TestCase):
    def setUp(self):
        self.service = EstimationService()

    def test_gate_rejects_only_empty_observations(self):
        obs = []
        self.assertFalse(self.service._passes_confidence_gates(obs))

    def test_gate_accepts_single_reading(self):
        obs = [(10.0, 1000.0)]
        self.assertTrue(self.service._passes_confidence_gates(obs))


class EstimationAndApiTests(APITestCase):
    def setUp(self):
        self.store = Store.objects.create(store_num=36073, store_name="Test Store")
        self.tank_type = TankType.objects.create(
            name="10K", capacity=10000, max_depth=120
        )
        self.mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="diesel",
            tank_index=1,
        )
        self.fuel_type = FuelType.objects.create(name="Diesel")

        ticket = VeederTicket.objects.create(store=self.store)
        for i in range(3):
            VeederReading.objects.create(
                ticket=ticket,
                tank_index=1,
                fuel_type=self.fuel_type,
                height=10.0 + (i * 3.0),
                volume=1000 + (i * 100),
                ullage=9000,
            )

    def test_virtual_persistence_reuses_when_unchanged(self):
        observations = [(10.0, 1000.0), (13.0, 1100.0), (16.0, 1200.0)]
        service = EstimationService()

        ts = timezone.now()
        est_1 = service.run_virtual_estimation(
            self.store,
            "diesel",
            2,
            10000,
            observations,
            latest_uploaded_at=ts,
        )
        est_2 = service.run_virtual_estimation(
            self.store,
            "DIESEL",
            2,
            10000,
            observations,
            latest_uploaded_at=ts,
        )

        self.assertIsNotNone(est_1)
        self.assertEqual(est_1.id, est_2.id)

    def test_virtual_persistence_recomputes_when_signature_changes(self):
        service = EstimationService()
        now = timezone.now()
        base_obs = [(10.0, 1000.0), (13.0, 1100.0), (16.0, 1200.0)]

        est_1 = service.run_virtual_estimation(
            self.store,
            "diesel",
            2,
            10000,
            base_obs,
            latest_uploaded_at=now,
        )
        est_2 = service.run_virtual_estimation(
            self.store,
            "diesel",
            2,
            10000,
            base_obs + [(20.0, 1600.0)],
            latest_uploaded_at=now + timedelta(minutes=1),
        )

        self.assertNotEqual(est_1.id, est_2.id)
        self.assertFalse(
            VirtualTankEstimation.objects.get(id=est_1.id).is_active,
        )
        self.assertTrue(
            VirtualTankEstimation.objects.get(id=est_2.id).is_active,
        )

    def test_api_calc_success(self):
        user = User.objects.create_user(username="testuser", password="password")
        self.client.login(username=user.username, password="password")

        url = reverse("tankgauge:calculate_tank_api")
        payload = {
            "store_id": "36073",
            "fuel_type": "diesel",
            "tank_id": str(self.mapping.id),
            "current_inches": 20.0,
            "delivery_gallons": 500,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUCCESS")

    def test_api_calc_success_without_auth(self):
        url = reverse("tankgauge:calculate_tank_api")
        payload = {
            "store_id": "36073",
            "fuel_type": "diesel",
            "tank_id": str(self.mapping.id),
            "current_inches": 20.0,
            "delivery_gallons": 500,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUCCESS")

    def test_api_calc_unavailable_does_not_crash(self):
        user = User.objects.create_user(username="testuser2", password="password")
        self.client.login(username=user.username, password="password")

        empty_tank_type = TankType.objects.create(
            name="No Chart", capacity=12000, max_depth=144
        )
        empty_mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=empty_tank_type,
            fuel_type="regular",
            tank_index=3,
        )

        url = reverse("tankgauge:calculate_tank_api")
        payload = {
            "store_id": "36073",
            "fuel_type": "regular",
            "tank_id": str(empty_mapping.id),
            "current_inches": 20.0,
            "delivery_gallons": 500,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "UNAVAILABLE")

    def test_estimation_health_api_for_mapped_tank(self):
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=40.0,
            length=180.0,
            confidence=0.77,
            mean_error=42.5,
            max_error=88.0,
            sample_count=3,
            algorithm_version="v1",
            is_active=True,
        )

        url = reverse("tankgauge:estimation_health_api")
        response = self.client.get(url, {"tank_id": str(self.mapping.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["identity"]["source"], "mapped")
        self.assertEqual(response.data["sample_count"], 3)
        self.assertEqual(response.data["reading_count"], 3)

    def test_estimation_health_api_for_virtual_identity(self):
        VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="diesel",
            tank_index=7,
            radius=40.0,
            length=180.0,
            confidence=0.66,
            mean_error=55.0,
            max_error=110.0,
            sample_count=5,
            algorithm_version="v1",
            is_active=True,
        )

        virtual_ticket = VeederTicket.objects.create(store=self.store)
        VeederReading.objects.create(
            ticket=virtual_ticket,
            tank_index=7,
            fuel_type=self.fuel_type,
            height=22.0,
            volume=2100,
            ullage=7900,
        )

        url = reverse("tankgauge:estimation_health_api")
        response = self.client.get(
            url,
            {
                "store_id": str(self.store.store_num),
                "fuel_type": "diesel",
                "tank_index": 7,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["identity"]["source"], "virtual")
        self.assertEqual(response.data["sample_count"], 5)
        self.assertEqual(response.data["reading_count"], 1)

    def test_api_validation_returns_string_error(self):
        user = User.objects.create_user(username="testuser3", password="password")
        self.client.login(username=user.username, password="password")

        url = reverse("tankgauge:calculate_tank_api")
        payload = {
            "store_id": "36073",
            "fuel_type": "diesel",
            "tank_id": str(self.mapping.id),
            "current_inches": -1,
            "delivery_gallons": 500,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data.get("error"), str)


class SyncCommandTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(store_num=5001, store_name="Sync Store")
        self.fuel_type = FuelType.objects.create(name="Diesel")
        self.tank_type = TankType.objects.create(
            name="SyncTank", capacity=10000, max_depth=120
        )

        self.mapped = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="diesel",
            tank_index=1,
        )

        ticket = VeederTicket.objects.create(store=self.store)
        for i in range(3):
            VeederReading.objects.create(
                ticket=ticket,
                tank_index=1,
                fuel_type=self.fuel_type,
                height=12.0 + (i * 3.0),
                volume=1200 + (i * 120),
                ullage=8800,
            )
            VeederReading.objects.create(
                ticket=ticket,
                tank_index=2,
                fuel_type=self.fuel_type,
                height=11.0 + (i * 3.0),
                volume=1100 + (i * 120),
                ullage=8900,
            )

    def test_sync_tank_estimates_creates_virtual_estimations(self):
        call_command("sync_tank_estimates", "--store", str(self.store.store_num))
        self.assertTrue(
            VirtualTankEstimation.objects.filter(
                store=self.store,
                fuel_type="diesel",
                tank_index=2,
                is_active=True,
            ).exists()
        )


class AdminSyncButtonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="password",
        )

    def test_admin_sync_endpoint_triggers_command(self):
        self.client.force_login(self.user)

        with patch("tankgauge.admin_views.call_command") as call_command_mock:
            response = self.client.post(reverse("admin_sync_tank_estimates"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))
        call_command_mock.assert_called_once_with("sync_tank_estimates")
