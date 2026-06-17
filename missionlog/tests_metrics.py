from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from missionlog.models import Mission, FuelType, OrderNumber, PurchaseOrder, LoadDelivery, TruckFuelLog
from tankgauge.models.store_models import Store
from missionlog.logic.reports.context import ReportContext
from missionlog.logic.metrics.timeline import generate_event_stream
from missionlog.logic.metrics.fuel import calculate_fuel_metrics
from missionlog.logic.metrics.mileage import calculate_mileage_metrics
from missionlog.logic.metrics.efficiency import calculate_efficiency_metrics
from missionlog.logic.metrics.earnings import calculate_earnings

class ReportingMetricsTests(TestCase):
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
        
        # Add truck fuel
        TruckFuelLog.objects.create(mission=self.mission, gallons=Decimal("30.00"), price_per_gallon=Decimal("4.00"))
        
        self.order = OrderNumber.objects.create(mission=self.mission, order_number="ORD-001")
        self.po = PurchaseOrder.objects.create(order_parent=self.order, po_number=12345)
        LoadDelivery.objects.create(
            purchase_order=self.po,
            fuel_type=self.fuel_type,
            store=self.store,
            gross_gal=8000,
            net_gal=7950
        )

    def test_timeline_sequencing(self):
        context = ReportContext(self.mission)
        events = generate_event_stream(context.shift)
        
        self.assertTrue(len(events) >= 3) # Start, Fuel, End
        self.assertEqual(events[0].event_type.value, "SHIFT_START")
        
        # Verify SHIFT_END is present in the stream
        event_types = [e.event_type.value for e in events]
        self.assertIn("SHIFT_END", event_types)

    def test_fuel_calculations(self):
        context = ReportContext(self.mission)
        metrics = calculate_fuel_metrics(context.shift.deliveries)
        
        self.assertEqual(metrics["total_gross_gallons"]["value"], 8000)
        self.assertEqual(metrics["thermal_variance"]["value"], -50)
        self.assertEqual(metrics["thermal_variance"]["math"], "7950 - 8000")

    def test_efficiency_mpg(self):
        context = ReportContext(self.mission)
        metrics = calculate_efficiency_metrics(context.shift)
        
        # 200 miles / 30 gallons = 6.666...
        self.assertEqual(metrics["mpg"]["value"], 6.67)

    def test_fuel_product_mix_contract(self):
        context = ReportContext(self.mission)
        metrics = calculate_fuel_metrics(context.shift.deliveries)

        self.assertIn("Regular", metrics["product_mix"])
        self.assertEqual(metrics["product_mix"]["Regular"]["value"], 8000)
        self.assertEqual(metrics["product_mix"]["Regular"]["type"], "exact")

    def test_earnings_uses_explicit_rate(self):
        context = ReportContext(self.mission)
        metrics = calculate_earnings(context.shift, hourly_rate=Decimal("42.50"))

        self.assertEqual(metrics["estimated_earnings"]["value"], 425.0)
