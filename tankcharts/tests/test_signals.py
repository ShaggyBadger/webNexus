from unittest.mock import patch

from django.test import TestCase

from tankcharts.models import StoreChartGeneration
from tankgauge.models import Store, StoreTankMapping, TankType, VirtualTankEstimation


class TankChartSignalTests(TestCase):
    def test_virtual_estimation_waits_for_mapping_before_regeneration(self):
        store = Store.objects.create(store_num=42369, store_name="Winnsboro SEI")

        with self.captureOnCommitCallbacks(execute=True):
            VirtualTankEstimation.objects.create(
                store=store,
                fuel_type="regular",
                tank_index=1,
                radius=60.0,
                length=400.0,
                confidence=0.9,
                mean_error=1.0,
                max_error=2.0,
                sample_count=1,
                algorithm_version="test",
                is_active=True,
            )

        self.assertFalse(StoreChartGeneration.objects.filter(store=store).exists())

    def test_chart_relevant_mapping_update_schedules_store_chart_refresh(self):
        store = Store.objects.create(store_num=42370, store_name="Mapping Update")
        original_type = TankType.objects.create(name="Original tank")
        replacement_type = TankType.objects.create(name="Replacement tank")
        mapping = StoreTankMapping.objects.create(
            store=store,
            tank_type=original_type,
            fuel_type="regular",
            tank_index=1,
        )

        with patch("tankcharts.signals.regenerate_store_chart_for_store_id") as refresh:
            with self.captureOnCommitCallbacks(execute=True):
                mapping.tank_type = replacement_type
                mapping.save(update_fields=["tank_type"])

        refresh.assert_called_once_with(
            store_id=store.pk,
            reason_code="tank_mapping_updated",
        )

    def test_non_chart_mapping_update_does_not_schedule_refresh(self):
        store = Store.objects.create(store_num=42371, store_name="Notes Only")
        tank_type = TankType.objects.create(name="Notes tank")
        mapping = StoreTankMapping.objects.create(
            store=store,
            tank_type=tank_type,
            fuel_type="regular",
            tank_index=1,
        )

        with patch("tankcharts.signals.regenerate_store_chart_for_store_id") as refresh:
            with self.captureOnCommitCallbacks(execute=True):
                mapping.capacity_notes = "Reviewed by field staff"
                mapping.save(update_fields=["capacity_notes"])

        refresh.assert_not_called()
