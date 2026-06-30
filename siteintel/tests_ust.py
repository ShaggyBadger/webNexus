from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from tankgauge.models import Store
from siteintel.models import Location, LocationType, USTPermit, USTVerification
from siteintel.logic import ust_service
from rest_framework.test import APIClient
from rest_framework import status
import pytz


class USTBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.loc_type = LocationType.objects.create(name="Gas Station")
        self.location = Location.objects.create(
            name="Test Site",
            location_type=self.loc_type,
            lat=40.7128,
            lon=-74.0060,  # New York
            timezone="America/New_York",
        )
        self.store = Store.objects.create(
            store_num=1234,
            store_name="Test Store",
            location=self.location,
            lat=40.7128,
            lon=-74.0060,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_timezone_resolution(self):
        """Verify that timezone is resolved from GPS coordinates."""
        # Location 1 (NYC) was set in setUp
        self.assertEqual(self.location.timezone, "America/New_York")

        # Location 2 (London)
        loc2 = Location.objects.create(
            name="London Site", location_type=self.loc_type, lat=51.5074, lon=-0.1278
        )
        # The pre_save signal should have populated it
        self.assertEqual(loc2.timezone, "Europe/London")

    def test_status_calculation(self):
        """Test the RED/ORANGE/GREEN logic."""
        today = ust_service.get_store_local_today(self.store)

        # GREEN: Expires in 60 days
        permit = USTPermit.objects.create(
            store=self.store, expiration_date=today + timedelta(days=60), is_active=True
        )
        self.assertEqual(ust_service.calculate_permit_status(permit), "GREEN")

        # ORANGE: Expires in 15 days
        permit.expiration_date = today + timedelta(days=15)
        permit.save()
        self.assertEqual(ust_service.calculate_permit_status(permit), "ORANGE")

        # RED: Expired yesterday
        permit.expiration_date = today - timedelta(days=1)
        permit.save()
        self.assertEqual(ust_service.calculate_permit_status(permit), "RED")

    def test_atomic_update(self):
        """Verify that update_permit is atomic and preserves history."""
        today = timezone.now().date()
        permit_data = {
            "permit_number": "OLD-123",
            "expiration_date": today + timedelta(days=100),
        }
        old_permit = USTPermit.objects.create(
            store=self.store, is_active=True, **permit_data
        )

        new_data = {
            "permit_number": "NEW-456",
            "expiration_date": today + timedelta(days=200),
        }
        ust_service.update_permit(self.store, self.user, new_data, notes="Replaced tag")

        # Check counts
        self.assertEqual(USTPermit.objects.filter(store=self.store).count(), 2)
        self.assertEqual(USTVerification.objects.filter(store=self.store).count(), 1)

        # Verify active state
        self.assertFalse(USTPermit.objects.get(pk=old_permit.pk).is_active)
        self.assertTrue(USTPermit.objects.get(permit_number="NEW-456").is_active)

        # Verify verification log
        v = USTVerification.objects.first()
        self.assertEqual(v.verification_type, "updated")
        self.assertEqual(v.notes, "Replaced tag")

    def test_api_endpoints(self):
        """Verify DRF endpoints respond correctly."""
        today = timezone.now().date()
        permit = USTPermit.objects.create(
            store=self.store, expiration_date=today + timedelta(days=60), is_active=True
        )

        # GET Permit
        response = self.client.get(f"/siteintel/api/stores/{self.store.id}/ust-permit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "GREEN")

        # POST Verification (Confirmed)
        response = self.client.post(
            f"/siteintel/api/stores/{self.store.id}/ust-verifications/",
            {"verification_type": "confirmed", "notes": "Looks good"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(USTVerification.objects.count(), 1)

        # PATCH Permit (Update)
        response = self.client.patch(
            f"/siteintel/api/stores/{self.store.id}/ust-permit/",
            {
                "permit_number": "MOD-789",
                "expiration_date": (today + timedelta(days=90)).isoformat(),
                "verification_notes": "Update via API",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            USTPermit.objects.filter(is_active=True).first().permit_number, "MOD-789"
        )
        self.assertEqual(USTVerification.objects.count(), 2)
