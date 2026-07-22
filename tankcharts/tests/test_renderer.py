from django.test import TestCase

from atg.models import VeederReading, VeederTicket
from missionlog.models import FuelType
from tankcharts.rendering import PDFRenderer
from tankcharts.services import TankFieldChartService
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    TankType,
)


class PDFRendererTests(TestCase):
    def test_renderer_returns_pdf_bytes(self):
        fuel_type = FuelType.objects.create(name="Regular", abbreviation="RUL")
        store = Store.objects.create(store_num=7912, store_name="Quick", state="NC")
        tank_type = TankType.objects.create(name="12k96", capacity=12000, max_depth=96)
        mapping = StoreTankMapping.objects.create(
            store=store,
            tank_type=tank_type,
            fuel_type="regular",
            tank_index=1,
        )
        for inches in range(1, 31):
            TankChart.objects.create(
                tank_type=tank_type,
                is_official=True,
                inches=inches,
                gallons=inches * 150,
                tank_name="12k96",
            )
        TankEstimation.objects.create(
            tank_mapping=mapping,
            radius=48.0,
            length=383.0,
            confidence=0.8,
            mean_error=3.1,
            max_error=7.1,
            sample_count=5,
            algorithm_version="1.0.0",
            is_active=True,
        )
        ticket = VeederTicket.objects.create(store=store)
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=fuel_type,
            volume=3200,
            ullage=8800,
            height=25.0,
        )

        chart = TankFieldChartService().build(store_num=7912, tank_index=1)
        pdf_bytes = PDFRenderer().render(chart)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertGreaterEqual(pdf_bytes.count(b"/Type /Page"), 2)
