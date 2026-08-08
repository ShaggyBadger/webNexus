from django.test import TestCase

from tankcharts.models import StoreChartGeneration
from tankgauge.models import Store, VirtualTankEstimation


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
