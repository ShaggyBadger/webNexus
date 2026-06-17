from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from missionlog.models import Mission, FuelType, OrderNumber, PurchaseOrder, LoadDelivery
from tankgauge.models.store_models import Store
from missionlog.logic.reports.context import ReportContext
from missionlog.logic.validators.mission import MissionValidator
from missionlog.logic.validators.base import Severity


class ReportingFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com")
        self.fuel_type = FuelType.objects.create(name="Regular", color_name="green", color_hex="#00ff00")
        self.store = Store.objects.create(store_num=7979, store_name="Test Store")
        
        self.mission = Mission.objects.create(
            user=self.user,
            shift_start=timezone.now() - timedelta(hours=10),
            shift_end=timezone.now(),
            start_miles=1000,
            end_miles=1200,
            is_completed=True
        )
        
        self.order = OrderNumber.objects.create(mission=self.mission, order_number="ORD-001")
        self.po = PurchaseOrder.objects.create(order_parent=self.order, po_number=12345)
        self.load = LoadDelivery.objects.create(
            purchase_order=self.po,
            fuel_type=self.fuel_type,
            store=self.store,
            gross_gal=8000,
            net_gal=7950,
            temp=72.5
        )

    def test_report_context_normalization(self):
        """Verify Mission ORM models correctly map to Shift domain objects."""
        context = ReportContext(self.mission)
        shift = context.shift
        
        self.assertEqual(shift.id, self.mission.id)
        self.assertEqual(shift.user_email, "test@example.com")
        self.assertEqual(len(shift.deliveries), 1)
        self.assertEqual(shift.deliveries[0].gross_gal, 8000)
        self.assertEqual(shift.deliveries[0].store_number, "7979")
        self.assertEqual(shift.total_miles, 200)
        self.assertAlmostEqual(shift.duration_hours, 10.0, places=2)

    def test_mission_validator_missing_mileage(self):
        """Verify that missions marked completed but missing end mileage trigger CRITICAL."""
        self.mission.end_miles = None
        self.mission.save()
        
        context = ReportContext(self.mission)
        validator = MissionValidator(context)
        issues = validator.validate()
        
        codes = [issue.code for issue in issues]
        self.assertIn("MISSING_END_MILEAGE", codes)
        self.assertEqual(issues[0].severity, Severity.CRITICAL)

    def test_mission_validator_long_duration(self):
        """Verify that unusually long missions trigger a WARNING."""
        self.mission.shift_start = timezone.now() - timedelta(hours=20)
        self.mission.save()
        
        context = ReportContext(self.mission)
        validator = MissionValidator(context)
        issues = validator.validate()
        
        codes = [issue.code for issue in issues]
        self.assertIn("LONG_SHIFT_DURATION", codes)
        # Find the specific issue
        issue = next(i for i in issues if i.code == "LONG_SHIFT_DURATION")
        self.assertEqual(issue.severity, Severity.WARNING)


class ReportEndpointAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pass12345"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@example.com", password="pass12345"
        )
        self.mission = Mission.objects.create(
            user=self.owner,
            shift_start=timezone.now() - timedelta(hours=2),
            shift_end=timezone.now(),
            is_completed=True,
        )

    def test_report_api_requires_login(self):
        url = reverse("missionlog:report_api", args=[self.mission.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)

    def test_report_api_disallows_cross_user_access(self):
        self.client.force_login(self.other_user)
        url = reverse("missionlog:report_api", args=[self.mission.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_report_api_returns_timeline_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("missionlog:report_api", args=[self.mission.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("timeline", payload)
        self.assertTrue(len(payload["timeline"]) >= 2)
