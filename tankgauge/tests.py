import json
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from atg.models import VeederReading, VeederTicket
from missionlog.models import FuelType
from siteintel.models import Location, LocationType
from tankgauge.admin.hardware_admin import TankTypeAdmin
from tankgauge.admin.store_admin import StoreTankMappingAdmin
from tankgauge.logic.curve_generator import generate_inch_gallon_curve
from tankgauge.logic.estimation_service import EstimationService
from tankgauge.logic.tank_lookup import (
    get_mapping_resolution_metrics,
    get_store_and_preset_status,
    get_tank_mapping,
    reset_mapping_resolution_metrics,
)
from tankgauge.models import (
    Store,
    TankChart,
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


class CurveGeneratorTests(TestCase):
    def test_generate_curve_returns_one_point_per_inch(self):
        curve = generate_inch_gallon_curve(
            radius_inches=48.0,
            length_inches=384.0,
            max_depth=96,
        )

        self.assertEqual(len(curve), 96)
        self.assertEqual(curve[0]["inches"], 1)
        self.assertEqual(curve[-1]["inches"], 96)
        self.assertGreater(curve[-1]["gallons"], curve[0]["gallons"])

    def test_generate_curve_rejects_invalid_geometry(self):
        with self.assertRaises(ValueError):
            generate_inch_gallon_curve(
                radius_inches=0.0, length_inches=384.0, max_depth=96
            )


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


class StaleVirtualEstimationTests(TestCase):
    """A mapped estimation must supersede an active virtual for the same tank."""

    def setUp(self):
        self.store = Store.objects.create(
            store_num=36073,
            riso_num=936073,
            store_name="Test Store",
        )
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

    def _create_active_virtual(self, tank_index, fuel_type="diesel"):
        return VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type=fuel_type,
            tank_index=tank_index,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )

    def test_mapped_estimation_deactivates_stale_virtual(self):
        virtual = self._create_active_virtual(tank_index=1)
        service = EstimationService()

        estimation = service.run_estimation_for_tank(self.mapping)

        self.assertIsNotNone(estimation)
        self.assertTrue(TankEstimation.objects.get(id=estimation.id).is_active)
        self.assertFalse(VirtualTankEstimation.objects.get(id=virtual.id).is_active)

    def test_mapped_estimation_leaves_unrelated_virtual_active(self):
        virtual = self._create_active_virtual(tank_index=2)
        service = EstimationService()

        estimation = service.run_estimation_for_tank(self.mapping)

        self.assertIsNotNone(estimation)
        self.assertTrue(VirtualTankEstimation.objects.get(id=virtual.id).is_active)

    def test_mapped_estimation_failure_keeps_virtual_fallback(self):
        # A mapping with no Veeder readings cannot produce an estimation, so the
        # active virtual remains as the fallback geometry source.
        empty_store = Store.objects.create(store_num=99991)
        empty_mapping = StoreTankMapping.objects.create(
            store=empty_store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=3,
        )
        virtual = VirtualTankEstimation.objects.create(
            store=empty_store,
            fuel_type="regular",
            tank_index=3,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )
        service = EstimationService()

        estimation = service.run_estimation_for_tank(empty_mapping)

        self.assertIsNone(estimation)
        self.assertTrue(VirtualTankEstimation.objects.get(id=virtual.id).is_active)

    def test_virtual_estimation_superseded_when_mapped_active(self):
        self._create_active_virtual(tank_index=1)
        service = EstimationService()
        service.run_estimation_for_tank(self.mapping)

        result = service.run_virtual_estimation(
            self.store,
            "diesel",
            1,
            10000,
            [(10.0, 1000.0), (13.0, 1100.0), (16.0, 1200.0)],
            latest_uploaded_at=timezone.now(),
        )

        self.assertIsNone(result)
        self.assertFalse(
            VirtualTankEstimation.objects.filter(
                store=self.store, tank_index=1, is_active=True
            ).exists()
        )


class DeactivateStaleVirtualEstimationsCommandTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(store_num=36073)
        self.tank_type = TankType.objects.create(name="10K", capacity=10000)
        self.mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="diesel",
            tank_index=1,
        )
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )
        self.stale_virtual = VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="diesel",
            tank_index=1,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )
        self.unmapped_virtual = VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="diesel",
            tank_index=7,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )

    def test_dry_run_reports_without_writing(self):
        call_command("deactivate_stale_virtual_estimations")

        self.assertTrue(
            VirtualTankEstimation.objects.get(id=self.stale_virtual.id).is_active
        )
        self.assertTrue(
            VirtualTankEstimation.objects.get(id=self.unmapped_virtual.id).is_active
        )

    def test_apply_deactivates_only_stale(self):
        call_command("deactivate_stale_virtual_estimations", "--apply")

        self.assertFalse(
            VirtualTankEstimation.objects.get(id=self.stale_virtual.id).is_active
        )
        self.assertTrue(
            VirtualTankEstimation.objects.get(id=self.unmapped_virtual.id).is_active
        )

    def test_store_filter_limits_scope(self):
        other_store = Store.objects.create(store_num=99992)
        other_mapping = StoreTankMapping.objects.create(
            store=other_store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=2,
        )
        TankEstimation.objects.create(
            tank_mapping=other_mapping,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )
        other_virtual = VirtualTankEstimation.objects.create(
            store=other_store,
            fuel_type="regular",
            tank_index=2,
            radius=50.0,
            length=200.0,
            confidence=0.5,
            sample_count=5,
            algorithm_version="TEST",
            is_active=True,
        )

        call_command(
            "deactivate_stale_virtual_estimations",
            "--apply",
            "--store",
            str(self.store.store_num),
        )

        self.assertFalse(
            VirtualTankEstimation.objects.get(id=self.stale_virtual.id).is_active
        )
        self.assertTrue(
            VirtualTankEstimation.objects.get(id=other_virtual.id).is_active
        )


class EstimationAndApiTests(APITestCase):
    def setUp(self):
        self.store = Store.objects.create(
            store_num=36073,
            riso_num=936073,
            store_name="Test Store",
        )
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
        TankChart.objects.create(
            tank_type=self.tank_type,
            inches=20,
            gallons=2000,
            tank_name="10K",
            is_official=True,
        )

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
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["status"], "SUCCESS")
        self.assertEqual(response.data["data"]["preferred_mode"], "MATHEMATICAL")
        self.assertIsNotNone(response.data["data"]["profiles"]["MATHEMATICAL"])
        self.assertIsNone(response.data["data"]["profiles"]["OFFICIAL"])
        self.assertEqual(response.data["data"]["display_mode"], "AUTO")
        self.assertIn("active_profile", response.data["data"])
        self.assertNotIn("confidence", response.data["data"])
        self.assertNotIn("confidence", response.data["data"]["active_profile"])

    def test_api_calc_honors_display_mode_override(self):
        url = reverse("tankgauge:calculate_tank_api")
        payload = {
            "store_id": "36073",
            "fuel_type": "diesel",
            "tank_id": str(self.mapping.id),
            "current_inches": 20.0,
            "delivery_gallons": 500,
            "display_mode": "OFFICIAL",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["status"], "SUCCESS")
        self.assertEqual(response.data["data"]["mode"], "MATHEMATICAL")
        self.assertEqual(
            response.data["data"]["active_profile"]["mode"], "MATHEMATICAL"
        )

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
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["status"], "SUCCESS")

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
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["status"], "UNAVAILABLE")

    def test_api_calc_uses_veeder_capacity_for_ninety_hold_when_official_capacity_missing(
        self,
    ):
        null_limits_tank_type = TankType.objects.create(name="15k120")
        mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=null_limits_tank_type,
            fuel_type="diesel",
            tank_index=5,
        )
        TankEstimation.objects.create(
            tank_mapping=mapping,
            radius=59.97,
            length=306.83,
            confidence=0.7,
            mean_error=12.0,
            max_error=24.0,
            sample_count=4,
            algorithm_version="v1",
            is_active=True,
        )

        url = reverse("tankgauge:calculate_tank_api")
        payload = {
            "store_id": str(self.store.store_num),
            "fuel_type": "diesel",
            "tank_id": str(mapping.id),
            "current_inches": 20.0,
            "delivery_gallons": 500,
            "display_mode": "AUTO",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["status"], "SUCCESS")
        self.assertEqual(response.data["data"]["mode"], "MATHEMATICAL")
        self.assertGreater(response.data["data"]["ninety_limit"], 0)
        self.assertGreater(response.data["data"]["avail_90"], 0)
        self.assertGreater(
            response.data["data"]["active_profile"]["capacity"]["capacity_gallons"],
            0,
        )
        self.assertGreater(
            response.data["data"]["active_profile"]["fillable_to_90"],
            0,
        )

    def test_api_calc_uses_estimation_capacity_when_tank_type_capacity_is_null(self):
        tank_type = TankType.objects.create(name="15k120-site-7986")
        mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=tank_type,
            fuel_type="regular",
            tank_index=7,
        )
        TankEstimation.objects.create(
            tank_mapping=mapping,
            radius=59.98,
            length=306.73,
            confidence=0.77,
            mean_error=12.0,
            max_error=24.0,
            sample_count=4,
            algorithm_version="v1",
            is_active=True,
        )

        response = self.client.post(
            reverse("tankgauge:calculate_tank_api"),
            {
                "store_id": str(self.store.store_num),
                "fuel_type": "regular",
                "tank_id": str(mapping.id),
                "current_inches": 100.75,
                "delivery_gallons": 0,
                "display_mode": "AUTO",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertGreater(data["ninety_limit"], 0)
        self.assertGreater(data["avail_90"], 0)

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
        data = response.data["data"]
        self.assertEqual(data["identity"]["source"], "mapped")
        self.assertEqual(data["sample_count"], 3)
        self.assertEqual(data["reading_count"], 3)
        self.assertNotIn("confidence", data)

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
        data = response.data["data"]
        self.assertEqual(data["identity"]["source"], "virtual")
        self.assertEqual(data["sample_count"], 5)
        self.assertEqual(data["reading_count"], 1)
        self.assertNotIn("confidence", data)

    def test_api_validation_returns_structured_error_contract(self):
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
        error = response.data.get("error")
        self.assertIsInstance(error, dict)
        self.assertEqual(error.get("code"), "validation_error")
        self.assertIsInstance(error.get("message"), str)
        self.assertIsInstance(error.get("details"), dict)
        self.assertIn("trace_id", error)


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
                tank_index=1,
                fuel_type=self.fuel_type,
                height=11.0 + (i * 3.0),
                volume=1100 + (i * 120),
                ullage=8900,
            )

    def test_sync_tank_estimates_creates_mapped_estimations(self):
        call_command("sync_tank_estimates", "--store", str(self.store.store_num))
        self.assertTrue(
            TankEstimation.objects.filter(
                tank_mapping=self.mapped,
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

    def test_admin_conflict_resolver_endpoint_dry_run(self):
        self.client.force_login(self.user)

        with patch("tankgauge.admin_views.call_command") as call_command_mock:
            response = self.client.post(reverse("admin_resolve_tank_conflicts"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))

        args, kwargs = call_command_mock.call_args
        self.assertEqual(args, ("resolve_tank_conflicts",))
        self.assertFalse(kwargs["commit"])
        self.assertIn("stdout", kwargs)

    def test_admin_conflict_resolver_endpoint_commit_mode(self):
        self.client.force_login(self.user)

        with patch("tankgauge.admin_views.call_command") as call_command_mock:
            response = self.client.post(
                reverse("admin_resolve_tank_conflicts"),
                data={"commit": "1"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))

        args, kwargs = call_command_mock.call_args
        self.assertEqual(args, ("resolve_tank_conflicts",))
        self.assertTrue(kwargs["commit"])
        self.assertIn("stdout", kwargs)

    def test_admin_sanitize_veeder_readings_endpoint_dry_run(self):
        self.client.force_login(self.user)

        with patch("tankgauge.admin_views.call_command") as call_command_mock:
            response = self.client.post(reverse("admin_sanitize_veeder_readings"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))

        args, kwargs = call_command_mock.call_args
        self.assertEqual(args, ("sanitize_veeder_readings",))
        self.assertFalse(kwargs["commit"])
        self.assertFalse(kwargs["delete_suspicious"])
        self.assertIn("stdout", kwargs)

    def test_admin_sanitize_veeder_readings_endpoint_commit_mode(self):
        self.client.force_login(self.user)

        with patch("tankgauge.admin_views.call_command") as call_command_mock:
            response = self.client.post(
                reverse("admin_sanitize_veeder_readings"),
                data={"commit": "1"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:index"))

        args, kwargs = call_command_mock.call_args
        self.assertEqual(args, ("sanitize_veeder_readings",))
        self.assertTrue(kwargs["commit"])
        self.assertFalse(kwargs["delete_suspicious"])
        self.assertIn("stdout", kwargs)


class StoreChartApiTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            store_num=8111,
            riso_num=98111,
            store_name="API Store",
        )
        self.tank_type = TankType.objects.create(
            name="API Tank", capacity=10000, max_depth=120
        )
        self.mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="diesel",
            tank_index=2,
        )
        self.fuel_type = FuelType.objects.create(name="Diesel")

    def _attach_location(self, vapor_manifold_value):
        location_type, _ = LocationType.objects.get_or_create(name="Store")
        location = Location.objects.create(
            name=f"Location {self.store.store_num}",
            location_type=location_type,
            metadata={"vapor_manifold": vapor_manifold_value},
        )
        self.store.location = location
        self.store.save(update_fields=["location"])

    def test_store_tanks_api_returns_sorted_records(self):
        StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=1,
        )

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        tank_indices = [item["tank_index"] for item in payload["data"]["tanks"]]
        self.assertEqual(tank_indices, [1, 2])
        first_tank = payload["data"]["tanks"][0]
        self.assertIn("available_modes", first_tank)
        self.assertIn("default_mode", first_tank)
        self.assertIn("limits", first_tank)
        self.assertIn("limits_by_mode", first_tank)
        self.assertNotIn("confidence", first_tank["limits"])
        for mode in first_tank["available_modes"]:
            self.assertNotIn("confidence", mode)

    def test_store_tanks_api_hides_official_only_mapping_after_veeder_activation(self):
        ticket = VeederTicket.objects.create(store=self.store)
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=2,
            fuel_type=self.fuel_type,
            volume=7000,
            ullage=3000,
            height=50.0,
        )
        StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=1,
        )

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tanks = response.json()["data"]["tanks"]
        self.assertEqual([tank["tank_index"] for tank in tanks], [2])

    def test_store_tanks_api_not_found_uses_error_contract(self):
        response = self.client.get(
            reverse("tankgauge:store_tanks_api", kwargs={"store_num": 999999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertEqual(payload["error"]["code"], "store_not_found")
        self.assertIn("message", payload["error"])
        self.assertIn("details", payload["error"])
        self.assertIn("trace_id", payload["error"])

    def test_store_tanks_api_accepts_riso_number(self):
        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api",
                kwargs={"store_num": self.store.riso_num},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["data"]["store"]["store_num"], self.store.store_num)
        self.assertEqual(payload["data"]["store"]["riso_num"], self.store.riso_num)

    def test_store_tanks_api_maps_yes_no_metadata_to_boolean(self):
        self._attach_location("No")

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIs(payload["data"]["store"]["vapor_manifold"], False)

        self.store.location.metadata["vapor_manifold"] = "Yes"
        self.store.location.save(update_fields=["metadata"])

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIs(payload["data"]["store"]["vapor_manifold"], True)

    def test_store_tanks_api_returns_unknown_when_metadata_is_blank(self):
        self._attach_location("")

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIsNone(payload["data"]["store"]["vapor_manifold"])

    def test_store_tanks_api_falls_back_to_veeder_limits_when_official_missing(self):
        null_limits_tank_type = TankType.objects.create(name="15k120")
        mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=null_limits_tank_type,
            fuel_type="regular",
            tank_index=3,
        )
        TankEstimation.objects.create(
            tank_mapping=mapping,
            radius=59.97,
            length=306.83,
            confidence=0.7,
            mean_error=12.0,
            max_error=24.0,
            sample_count=4,
            algorithm_version="v1",
            is_active=True,
        )

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tanks = response.json()["data"]["tanks"]
        target = [tank for tank in tanks if tank["id"] == mapping.id][0]
        self.assertEqual(target["capacity"], 15007)
        self.assertEqual(target["max_depth"], 120)
        self.assertEqual(target["limits_source"], "VEEDER")

    @override_settings(TANKGAUGE_DEFAULT_TANK_LIMITS_SOURCE_PRIORITY="VEEDER_FIRST")
    def test_store_tanks_api_can_prefer_veeder_over_official(self):
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=48.0,
            length=240.0,
            confidence=0.7,
            mean_error=10.0,
            max_error=22.0,
            sample_count=5,
            algorithm_version="v1",
            is_active=True,
        )

        response = self.client.get(
            reverse(
                "tankgauge:store_tanks_api", kwargs={"store_num": self.store.store_num}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tanks = response.json()["data"]["tanks"]
        target = [tank for tank in tanks if tank["id"] == self.mapping.id][0]
        self.assertEqual(target["capacity"], 7520)
        self.assertEqual(target["max_depth"], 96)
        self.assertEqual(target["limits_source"], "VEEDER")

    def test_tank_chart_data_api_returns_official_generated_and_scatter_series(self):
        TankChart.objects.create(
            tank_type=self.tank_type,
            inches=10,
            gallons=1000,
            tank_name="API Tank",
            is_official=True,
        )
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=40.0,
            length=180.0,
            confidence=0.8,
            mean_error=12.0,
            max_error=20.0,
            sample_count=3,
            algorithm_version="v1",
            is_active=True,
        )
        ticket = VeederTicket.objects.create(store=self.store)
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=2,
            fuel_type=self.fuel_type,
            height=20.0,
            volume=2200,
            ullage=7800,
        )

        response = self.client.get(
            reverse(
                "tankgauge:tank_chart_data_api", kwargs={"tank_id": self.mapping.id}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        data = payload["data"]
        self.assertEqual(data["tank"]["id"], self.mapping.id)
        self.assertEqual(len(data["series"]["official_chart"]), 0)
        self.assertGreater(len(data["series"]["generated_curve"]), 0)
        self.assertGreater(len(data["series"]["scatter_points"]), 0)
        self.assertEqual(data["tank"]["source_policy"], "VEEDER_ONLY")

    def test_api_calc_success_envelope_shape(self):
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
        self.assertEqual(response.data["status"], "success")
        self.assertIn("data", response.data)

    def test_estimation_health_success_envelope_shape(self):
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
        response = self.client.get(
            reverse("tankgauge:estimation_health_api"),
            {"tank_id": str(self.mapping.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertIn("data", response.data)

    def test_tank_chart_data_api_not_found_uses_error_contract(self):
        response = self.client.get(
            reverse("tankgauge:tank_chart_data_api", kwargs={"tank_id": 999999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertEqual(payload["error"]["code"], "tank_not_found")
        self.assertIn("message", payload["error"])
        self.assertIn("details", payload["error"])
        self.assertIn("trace_id", payload["error"])

    def test_tank_chart_data_scatter_points_use_recent_plus_random_sample(self):
        for idx in range(12):
            ticket = VeederTicket.objects.create(store=self.store)
            ticket.uploaded_at = timezone.now() - timedelta(minutes=idx)
            ticket.save(update_fields=["uploaded_at"])
            VeederReading.objects.create(
                ticket=ticket,
                tank_index=2,
                fuel_type=self.fuel_type,
                height=float(idx + 1),
                volume=2000 + idx,
                ullage=7000,
            )

        with patch(
            "tankgauge.views.api.tank_data.random.sample",
            side_effect=lambda population, k: population[:k],
        ):
            response = self.client.get(
                reverse(
                    "tankgauge:tank_chart_data_api", kwargs={"tank_id": self.mapping.id}
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["data"]
        scatter_points = payload["series"]["scatter_points"]
        self.assertEqual(len(scatter_points), 10)
        self.assertEqual(payload["tank"]["veeder_reading_count"], 12)
        self.assertEqual(
            [point["inches"] for point in scatter_points[:5]], [1, 2, 3, 4, 5]
        )
        self.assertEqual(
            [point["inches"] for point in scatter_points[5:]],
            [6, 7, 8, 9, 10],
        )

    def test_tank_chart_data_scatter_points_skip_random_when_less_than_five(self):
        for idx in range(4):
            ticket = VeederTicket.objects.create(store=self.store)
            ticket.uploaded_at = timezone.now() - timedelta(minutes=idx)
            ticket.save(update_fields=["uploaded_at"])
            VeederReading.objects.create(
                ticket=ticket,
                tank_index=2,
                fuel_type=self.fuel_type,
                height=float(idx + 1),
                volume=3000 + idx,
                ullage=6000,
            )

        with patch("tankgauge.views.api.tank_data.random.sample") as sample_mock:
            response = self.client.get(
                reverse(
                    "tankgauge:tank_chart_data_api", kwargs={"tank_id": self.mapping.id}
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        scatter_points = response.json()["data"]["series"]["scatter_points"]
        self.assertEqual(len(scatter_points), 4)
        self.assertEqual([point["inches"] for point in scatter_points], [1, 2, 3, 4])
        sample_mock.assert_not_called()


class ClosestStoreApiTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            store_num=7777,
            store_name="Closest Store",
            lat=40.0,
            lon=-89.0,
        )

    def _attach_location(self, vapor_manifold_value):
        location_type, _ = LocationType.objects.get_or_create(name="Store")
        location = Location.objects.create(
            name=f"Location {self.store.store_num}",
            location_type=location_type,
            metadata={"vapor_manifold": vapor_manifold_value},
        )
        self.store.location = location
        self.store.save(update_fields=["location"])

    def test_closest_store_api_missing_coordinates_uses_error_contract(self):
        response = self.client.get(reverse("tankgauge:closest_store_api"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertEqual(payload["error"]["code"], "missing_coordinates")
        self.assertIn("message", payload["error"])
        self.assertIn("details", payload["error"])
        self.assertIn("trace_id", payload["error"])

    def test_closest_store_api_includes_vapor_manifold_true(self):
        self._attach_location("Yes")

        response = self.client.get(
            reverse("tankgauge:closest_store_api"),
            {"lat": "40.001", "lon": "-89.001"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        store_result = payload["data"]["results"][0]
        self.assertIs(store_result["vapor_manifold"], True)
        self.assertIs(store_result["veeder_readings"], False)

    def test_closest_store_api_reports_veeder_readings(self):
        fuel_type = FuelType.objects.create(name="Regular")
        ticket = VeederTicket.objects.create(store=self.store)
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=fuel_type,
            volume=5000,
            ullage=5000,
            height=48.0,
        )

        response = self.client.get(
            reverse("tankgauge:closest_store_api"),
            {"lat": "40.001", "lon": "-89.001"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        store_result = response.json()["data"]["results"][0]
        self.assertIs(store_result["veeder_readings"], True)

    def test_closest_store_api_includes_vapor_manifold_false(self):
        self._attach_location("No")

        response = self.client.get(
            reverse("tankgauge:closest_store_api"),
            {"lat": "40.001", "lon": "-89.001"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        store_result = payload["data"]["results"][0]
        self.assertIs(store_result["vapor_manifold"], False)

    def test_closest_store_api_includes_vapor_manifold_unknown(self):
        response = self.client.get(
            reverse("tankgauge:closest_store_api"),
            {"lat": "40.001", "lon": "-89.001"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        store_result = payload["data"]["results"][0]
        self.assertIsNone(store_result["vapor_manifold"])


class StoreTankMappingAdminTests(TestCase):
    def test_store_tank_mapping_admin_searches_by_store_number(self):
        admin_instance = StoreTankMappingAdmin(StoreTankMapping, AdminSite())
        self.assertIn("store__store_num", admin_instance.search_fields)
        self.assertIn("store__store_name", admin_instance.search_fields)
        self.assertIn("tank_index", admin_instance.search_fields)

    def test_store_tank_mapping_admin_uses_tank_type_autocomplete(self):
        admin_instance = StoreTankMappingAdmin(StoreTankMapping, AdminSite())
        self.assertIn("tank_type", admin_instance.autocomplete_fields)


class TankTypeAdminTests(TestCase):
    def test_tank_type_admin_searches_name_and_key_specs(self):
        admin_instance = TankTypeAdmin(TankType, AdminSite())
        self.assertIn("name", admin_instance.search_fields)
        self.assertIn("manufacturer", admin_instance.search_fields)
        self.assertIn("model", admin_instance.search_fields)
        self.assertIn("=capacity", admin_instance.search_fields)
        self.assertIn("=max_depth", admin_instance.search_fields)


class ExportTankDataCommandTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            store_num=100, store_name="Mapped Store", store_type="Travel Center"
        )
        self.tank_type = TankType.objects.create(name="12k96", capacity=12000)
        self.mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=1,
        )
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=48.0,
            length=192.0,
            confidence=0.9,
            sample_count=40,
            algorithm_version="TEST",
            is_active=True,
        )
        VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="regular",
            tank_index=1,
            radius=48.0,
            length=192.0,
            confidence=0.7,
            sample_count=20,
            algorithm_version="TEST",
            is_active=True,
        )
        self.unmapped_store = Store.objects.create(store_num=200, store_name="Bare")

    def test_store_map_includes_store_type_for_all_stores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_tank_data", "--output", tmpdir)
            with open(os.path.join(tmpdir, "store_map.json")) as f:
                store_map = json.load(f)

        self.assertEqual(
            set(store_map), {str(self.store.id), str(self.unmapped_store.id)}
        )
        self.assertEqual(store_map[str(self.store.id)]["store_num"], 100)
        self.assertEqual(store_map[str(self.store.id)]["store_type"], "Travel Center")
        self.assertEqual(store_map[str(self.unmapped_store.id)]["store_num"], 200)
        self.assertIsNone(store_map[str(self.unmapped_store.id)]["store_type"])

    def _run_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_tank_data", "--output", tmpdir)
            with open(os.path.join(tmpdir, "generated_tank_charts.json")) as f:
                generated = json.load(f)
            with open(os.path.join(tmpdir, "tank_assignments.json")) as f:
                assignments = json.load(f)
        return generated, assignments

    def test_generated_charts_emit_one_record_per_physical_tank(self):
        generated, _ = self._run_export()

        keys = [(r["store_id"], r["tank_index"]) for r in generated]
        self.assertEqual(len(keys), len(set(keys)))
        record = next(r for r in generated if r["store_id"] == self.store.id)
        self.assertEqual(record["tank_index"], 1)
        self.assertEqual(record["tank_type_name"], "12k96")
        self.assertEqual(record["confidence"], 0.9)

    def test_generated_charts_fall_back_to_virtual_when_mapped_geometry_fails(self):
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=0.0,
            length=192.0,
            confidence=0.99,
            sample_count=99,
            algorithm_version="TEST",
            is_active=True,
        )

        generated, _ = self._run_export()

        record = next(r for r in generated if r["store_id"] == self.store.id)
        self.assertIsNone(record["tank_type_name"])
        self.assertEqual(record["confidence"], 0.7)

    def test_tank_assignments_cover_every_slot_including_unmapped(self):
        VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="diesel",
            tank_index=2,
            radius=48.0,
            length=192.0,
            confidence=0.5,
            sample_count=10,
            algorithm_version="TEST",
            is_active=True,
        )

        _, assignments = self._run_export()

        store_rows = [r for r in assignments if r["store_num"] == 100]
        self.assertEqual(
            [(r["tank_index"], r["tank_type_name"]) for r in store_rows],
            [(1, "12k96"), (2, None)],
        )
        self.assertTrue(all(r["is_active"] for r in store_rows))
        self.assertEqual(store_rows[1]["fuel_type"], "diesel")

    def test_tank_assignments_skip_virtual_slots_already_mapped(self):
        _, assignments = self._run_export()

        store_rows = [r for r in assignments if r["store_num"] == 100]
        self.assertEqual(len(store_rows), 1)
        self.assertEqual(store_rows[0]["tank_type_name"], "12k96")

    def test_auto_mapper_placeholder_names_export_as_unnamed(self):
        auto_type = TankType.objects.create(name="AUTO_100_T2_REGULAR")
        StoreTankMapping.objects.create(
            store=self.store,
            tank_type=auto_type,
            fuel_type="premium",
            tank_index=2,
        )
        TankEstimation.objects.create(
            tank_mapping=StoreTankMapping.objects.get(
                store=self.store, fuel_type="premium", tank_index=2
            ),
            radius=48.0,
            length=192.0,
            confidence=0.8,
            sample_count=30,
            algorithm_version="TEST",
            is_active=True,
        )

        generated, assignments = self._run_export()

        assignment_row = next(
            r for r in assignments if r["store_num"] == 100 and r["tank_index"] == 2
        )
        self.assertIsNone(assignment_row["tank_type_name"])
        self.assertTrue(assignment_row["is_active"])
        generated_row = next(
            r
            for r in generated
            if r["store_id"] == self.store.id and r["tank_index"] == 2
        )
        self.assertIsNone(generated_row["tank_type_name"])

    def test_tank_assignments_mark_inactive_virtual_only_slots(self):
        VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="diesel",
            tank_index=3,
            radius=48.0,
            length=192.0,
            confidence=0.5,
            sample_count=10,
            algorithm_version="TEST",
            is_active=False,
        )

        _, assignments = self._run_export()

        row = next(
            r for r in assignments if r["store_num"] == 100 and r["tank_index"] == 3
        )
        self.assertFalse(row["is_active"])
        self.assertIsNone(row["tank_type_name"])

    def test_tank_assignments_match_generated_chart_numbering(self):
        VirtualTankEstimation.objects.create(
            store=self.store,
            fuel_type="diesel",
            tank_index=2,
            radius=48.0,
            length=192.0,
            confidence=0.5,
            sample_count=10,
            algorithm_version="TEST",
            is_active=True,
        )

        generated, assignments = self._run_export()

        generated_keys = {(r["store_num"], r["tank_index"]) for r in generated}
        assignment_keys = {
            (r["store_num"], r["tank_index"])
            for r in assignments
            if r["store_num"] == 100
        }
        self.assertEqual(generated_keys, {(100, 1), (100, 2)})
        self.assertTrue(assignment_keys >= generated_keys)
