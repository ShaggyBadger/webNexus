from django.test import TestCase

from atg.models import VeederReading, VeederTicket
from missionlog.models import FuelType
from tankcharts.services import TankFieldChartService
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    TankType,
)


class TankFieldChartServiceTests(TestCase):
    def setUp(self):
        self.fuel_type = FuelType.objects.create(name="Regular", abbreviation="RUL")
        self.store = Store.objects.create(
            store_num=7974,
            store_name="Midland",
            city="Midland",
            state="NC",
        )
        self.tank_type = TankType.objects.create(
            name="12k96",
            capacity=11990,
            max_depth=96,
        )
        self.mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=1,
        )

        for inches in range(1, 97):
            TankChart.objects.create(
                tank_type=self.tank_type,
                is_official=True,
                inches=inches,
                gallons=inches * 120,
                tank_name="12k96",
            )

        self.estimation = TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=48.0,
            length=384.0,
            confidence=0.8,
            mean_error=4.2,
            max_error=8.0,
            sample_count=7,
            algorithm_version="1.0.0",
            is_active=True,
        )

        ticket = VeederTicket.objects.create(store=self.store)
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=self.fuel_type,
            volume=1700,
            ullage=10000,
            height=19.0,
        )
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=self.fuel_type,
            volume=6400,
            ullage=5600,
            height=50.0,
        )

    def test_build_returns_complete_chart(self):
        service = TankFieldChartService()

        chart = service.build(store_num=7974, tank_index=1)

        self.assertEqual(chart.store_num, 7974)
        self.assertEqual(chart.tank_index, 1)
        self.assertEqual(chart.max_depth_inches, 96)
        self.assertTrue(chart.has_official_chart)
        self.assertEqual(len(chart.table_rows), 96)
        self.assertGreaterEqual(chart.coverage_percent, 0.0)
        self.assertGreaterEqual(chart.veeder_observation_count, 2)

    def test_compute_coverage_empty_is_zero(self):
        service = TankFieldChartService()
        coverage_percent = service._compute_coverage(
            veeder_points=[],
            max_depth_inches=96,
        )
        self.assertEqual(coverage_percent, 0.0)
