from django.test import TestCase

from atg.models import VeederTicket
from missionlog.models import FuelType
from tankcharts.services import DMSChartStorageService
from tankgauge.models import Store, StoreTankMapping, TankChart, TankType


class DMSChartStorageServiceTests(TestCase):
    def setUp(self):
        FuelType.objects.create(name="Regular", abbreviation="RUL")
        self.store = Store.objects.create(
            store_num=4630, store_name="Alpha", state="NC"
        )
        self.tank_type = TankType.objects.create(
            name="10k", capacity=10000, max_depth=96
        )
        self.mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=self.tank_type,
            fuel_type="regular",
            tank_index=5,
        )
        for inches in range(1, 11):
            TankChart.objects.create(
                tank_type=self.tank_type,
                is_official=True,
                inches=inches,
                gallons=inches * 100,
                tank_name="10k",
            )

    def test_store_and_find_existing_document(self):
        service = DMSChartStorageService()
        metadata = {
            "store_num": 4630,
            "tank_index": 5,
            "fuel_type": "regular",
            "official_row_count": 10,
            "veeder_count": 0,
            "estimation_id": None,
            "generated_at": "2026-07-21T00:00:00Z",
        }

        document = service.store(
            store_num=4630,
            fuel_type="regular",
            tank_index=5,
            pdf_bytes=b"%PDF-1.4 test",
            metadata=metadata,
        )

        found = service.find_existing(store_num=4630, fuel_type="regular", tank_index=5)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, document.id)

    def test_is_stale_after_new_ticket(self):
        service = DMSChartStorageService()
        metadata = {
            "store_num": 4630,
            "tank_index": 5,
            "fuel_type": "regular",
            "official_row_count": 10,
            "veeder_count": 0,
            "estimation_id": None,
            "generated_at": "2026-07-21T00:00:00Z",
        }

        document = service.store(
            store_num=4630,
            fuel_type="regular",
            tank_index=5,
            pdf_bytes=b"%PDF-1.4 test",
            metadata=metadata,
        )

        VeederTicket.objects.create(store=self.store)

        self.assertTrue(
            service.is_stale(document=document, store_num=4630, tank_index=5)
        )
