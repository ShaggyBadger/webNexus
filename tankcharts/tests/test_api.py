from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from atg.models import VeederReading, VeederTicket
from missionlog.models import FuelType
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    TankType,
)


class TankChartAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        fuel_type = FuelType.objects.create(name="Regular", abbreviation="RUL")
        store = Store.objects.create(store_num=6001, store_name="Bravo", state="NC")
        tank_type = TankType.objects.create(name="12k96", capacity=12000, max_depth=96)
        mapping = StoreTankMapping.objects.create(
            store=store,
            tank_type=tank_type,
            fuel_type="regular",
            tank_index=1,
        )
        for inches in range(1, 21):
            TankChart.objects.create(
                tank_type=tank_type,
                is_official=True,
                inches=inches,
                gallons=inches * 100,
                tank_name="12k96",
            )
        TankEstimation.objects.create(
            tank_mapping=mapping,
            radius=48.0,
            length=380.0,
            confidence=0.75,
            mean_error=5.0,
            max_error=10.0,
            sample_count=4,
            algorithm_version="1.0.0",
            is_active=True,
        )
        ticket = VeederTicket.objects.create(store=store)
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=fuel_type,
            volume=1200,
            ullage=10800,
            height=12.0,
        )

        self.store_num = 6001

    def test_meta_endpoint_returns_success(self):
        response = self.client.get(f"/tankcharts/meta/{self.store_num}/1/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["data"]["store_num"], self.store_num)
        self.assertNotIn("confidence_level", payload["data"])

    def test_chart_endpoint_redirects_to_dms_download(self):
        response = self.client.get(f"/tankcharts/chart/{self.store_num}/1/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dms/documents/", response["Location"])

    def test_batch_endpoint_requires_admin(self):
        response = self.client.post(
            f"/tankcharts/batch/{self.store_num}/", {"force": True}
        )
        self.assertEqual(response.status_code, 403)

        admin = User.objects.create_user("admin", password="secret", is_staff=True)
        self.client.force_authenticate(user=admin)
        response = self.client.post(
            f"/tankcharts/batch/{self.store_num}/", {"force": True}
        )
        self.assertEqual(response.status_code, 200)
