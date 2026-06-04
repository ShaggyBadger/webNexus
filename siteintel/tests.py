from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch
from siteintel.logic.rack_ops import get_rack_status
from datetime import datetime, timezone


class RackOpsUnitTests(SimpleTestCase):
    def test_get_rack_status_calendar_day(self):
        # Scenario:
        # Check-in: Jan 1, 2026, 23:00 UTC
        # Current:  Jan 2, 2026, 01:00 UTC
        # Difference: 2 hours, but different calendar days.

        jan1 = datetime(2026, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        jan2 = datetime(2026, 1, 2, 1, 0, 0, tzinfo=timezone.utc)

        user = MagicMock()
        rack = MagicMock()
        rack.lockout_days = 7

        last_checkin = MagicMock()
        last_checkin.timestamp = jan1

        # Patch RackCheckIn.objects.filter().order_by().first()
        with patch("siteintel.models.RackCheckIn.objects.filter") as mock_filter:
            mock_filter.return_value.order_by.return_value.first.return_value = (
                last_checkin
            )

            with patch("siteintel.logic.rack_ops.datetime") as mock_datetime:
                mock_datetime.now.return_value = jan2
                # Ensure datetime() constructor still works for the status color logic if needed
                mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                    *args, **kwargs
                )

                status = get_rack_status(user, rack)

                # CURRENT BEHAVIOR (24h-based):
                # jan2 - jan1 = 2 hours. delta.days = 0.
                # days_remaining = 7 - 0 = 7.

                # DESIRED BEHAVIOR (Calendar-based):
                # jan2.date() - jan1.date() = 1 day.
                # days_remaining = 7 - 1 = 6.

                # For now, I'll assert 7 to confirm it fails when I change it to 6.
                # Or better, I'll just change it to 6 and expect failure now.
                self.assertEqual(
                    status["days_remaining"],
                    6,
                    f"Expected 6 days remaining for calendar-day logic, got {status['days_remaining']}",
                )

    def test_record_checkin_proximity(self):
        """
        Verify that is_verified is set correctly based on proximity.
        Threshold is 500 meters (~0.31 miles).
        """
        from siteintel.logic.rack_ops import record_checkin

        user = MagicMock(username="testuser")
        rack = MagicMock()
        rack.location.name = "Test Rack"
        # 45.0, -93.0
        rack.location.lat = 45.0
        rack.location.lon = -93.0

        with patch("siteintel.models.RackCheckIn.objects.create") as mock_create:
            # Case 1: Within range (roughly 100 meters away)
            record_checkin(user, rack, lat=45.0001, lon=-93.0)
            args, kwargs = mock_create.call_args
            self.assertTrue(kwargs["is_verified"], "Check-in should be verified within 500m")

            # Case 2: Out of range (roughly 2 miles away)
            record_checkin(user, rack, lat=45.03, lon=-93.0)
            args, kwargs = mock_create.call_args
            self.assertFalse(kwargs["is_verified"], "Check-in should NOT be verified outside 500m")
