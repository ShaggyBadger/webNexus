import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from tankgauge.models import Store, StoreTankMapping, TankType
from missionlog.models import FuelType
from .models import VeederTicket, VeederReading
from .services import VeederUploadService

from PIL import Image


def get_test_image():
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), "white")
    image.save(file, "jpeg")
    file.seek(0)
    return SimpleUploadedFile("test_ticket.jpg", file.read(), content_type="image/jpeg")


class VeederUploadServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.store = Store.objects.create(store_num=101, store_name="Store 101")
        self.fuel_type = FuelType.objects.create(name="Regular")
        self.image = get_test_image()

    def test_process_ticket_submission_success(self):
        readings_data = [
            {
                "tank_index": 1,
                "fuel_type": self.fuel_type.id,
                "volume": 5000,
                "ullage": 1200,
                "height": 92.5,
                "temp": 68.4,
                "water": 0.5,
                "raw_line_text": "1 Regular 5000 1200 92.5",
                "confidence_score": 0.95,
                "is_user_corrected": False,
            }
        ]
        ticket = VeederUploadService.process_ticket_submission(
            user=self.user,
            store=self.store,
            image=self.image,
            notes="Test note",
            readings_data=readings_data,
        )

        self.assertIsNotNone(ticket.id)
        self.assertEqual(ticket.store, self.store)
        self.assertEqual(ticket.uploaded_by, self.user)
        self.assertEqual(ticket.ocr_status, "PENDING")
        self.assertEqual(ticket.notes, "Test note")

        # Verify nested readings
        readings = ticket.readings.all()
        self.assertEqual(readings.count(), 1)
        reading = readings.first()
        self.assertEqual(reading.tank_index, 1)
        self.assertEqual(reading.fuel_type, self.fuel_type)
        self.assertEqual(reading.volume, 5000)
        self.assertEqual(reading.ullage, 1200)
        self.assertEqual(reading.height, 92.5)
        self.assertEqual(reading.temp, 68.4)
        self.assertEqual(reading.water, 0.5)
        self.assertEqual(reading.confidence_score, 0.95)
        self.assertFalse(reading.is_user_corrected)

    def test_process_ticket_submission_auto_mapper_failure_does_not_rollback(self):
        readings_data = [
            {
                "tank_index": 1,
                "fuel_type": self.fuel_type.id,
                "volume": 5000,
                "ullage": 1200,
                "height": 92.5,
                "temp": 68.4,
                "water": 0.5,
                "raw_line_text": "1 Regular 5000 1200 92.5",
            }
        ]

        with patch(
            "atg.services.upload_service.AutoMapperService.ensure_mapping",
            side_effect=RuntimeError("simulated mapping error"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                ticket = VeederUploadService.process_ticket_submission(
                    user=self.user,
                    store=self.store,
                    image=self.image,
                    notes="Mapper failure should not rollback",
                    readings_data=readings_data,
                )

        self.assertIsNotNone(ticket.id)
        self.assertEqual(ticket.readings.count(), 1)

    def test_process_ticket_submission_creates_auto_mapping_for_unmapped_tank(self):
        readings_data = [
            {
                "tank_index": 2,
                "fuel_type": self.fuel_type.id,
                "volume": 4200,
                "ullage": 5800,
                "height": 40.0,
            },
            {
                "tank_index": 2,
                "fuel_type": self.fuel_type.id,
                "volume": 5000,
                "ullage": 5000,
                "height": 52.0,
            },
            {
                "tank_index": 2,
                "fuel_type": self.fuel_type.id,
                "volume": 6200,
                "ullage": 3800,
                "height": 68.0,
            },
        ]

        fake_estimation = SimpleNamespace(id=999, radius=60.0)
        with patch(
            "atg.services.auto_mapper.EstimationService.run_virtual_estimation",
            return_value=fake_estimation,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                VeederUploadService.process_ticket_submission(
                    user=self.user,
                    store=self.store,
                    image=self.image,
                    notes="Auto-map integration",
                    readings_data=readings_data,
                )

        self.assertTrue(
            StoreTankMapping.objects.filter(
                store=self.store,
                fuel_type="regular",
                tank_index=2,
            ).exists()
        )
        mapping = StoreTankMapping.objects.get(
            store=self.store,
            fuel_type="regular",
            tank_index=2,
        )
        self.assertTrue(mapping.tank_type.name.startswith("AUTO_101_T2_REGULAR"))
        self.assertTrue(
            TankType.objects.filter(name=mapping.tank_type.name).exists(),
        )


class VeederAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.store = Store.objects.create(store_num=101, store_name="Store 101")
        self.fuel_type = FuelType.objects.create(name="Regular")
        self.image = get_test_image()

        self.client.login(username="testuser", password="password123")

    def test_ticket_viewset_create_multipart(self):
        readings_data = [
            {
                "tank_index": 1,
                "fuel_type": self.fuel_type.id,
                "volume": 6000,
                "ullage": 800,
                "height": 95.0,
                "temp": 69.0,
                "water": 0.0,
            }
        ]

        url = reverse("atg:ticket-list")
        data = {
            "store": self.store.id,
            "image": self.image,
            "notes": "API test",
            "readings_json": json.dumps(readings_data),
        }

        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify created ticket
        ticket_id = response.data.get("id")
        self.assertIsNotNone(ticket_id)
        ticket = VeederTicket.objects.get(id=ticket_id)
        self.assertEqual(ticket.notes, "API test")
        self.assertEqual(ticket.readings.count(), 1)
        self.assertEqual(ticket.readings.first().volume, 6000)

    def test_ticket_viewset_create_without_store_and_image(self):
        readings_data = [
            {
                "tank_index": 1,
                "fuel_type": self.fuel_type.id,
                "volume": 6000,
                "ullage": 800,
                "height": 95.0,
            }
        ]

        url = reverse("atg:ticket-list")
        data = {
            "notes": "Without store and image",
            "readings_json": json.dumps(readings_data),
        }

        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        ticket_id = response.data.get("id")
        self.assertIsNotNone(ticket_id)
        ticket = VeederTicket.objects.get(id=ticket_id)
        self.assertIsNone(ticket.store)
        self.assertFalse(bool(ticket.image))

    def test_ticket_list_and_retrieve(self):
        ticket = VeederTicket.objects.create(
            store=self.store, image=self.image, uploaded_by=self.user
        )

        url = reverse("atg:ticket-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        url = reverse("atg:ticket-detail", kwargs={"pk": ticket.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], ticket.id)

    def test_reading_viewset_list_and_patch(self):
        ticket = VeederTicket.objects.create(
            store=self.store, image=self.image, uploaded_by=self.user
        )
        reading = VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=self.fuel_type,
            volume=5000,
            ullage=1200,
            height=92.5,
        )

        url = reverse("atg:reading-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        url = reverse("atg:reading-detail", kwargs={"pk": reading.id})
        response = self.client.patch(url, {"volume": 5500})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        reading.refresh_from_db()
        self.assertEqual(reading.volume, 5500)

    def test_stats_view(self):
        ticket = VeederTicket.objects.create(
            store=self.store, image=self.image, uploaded_by=self.user
        )
        VeederReading.objects.create(
            ticket=ticket,
            tank_index=1,
            fuel_type=self.fuel_type,
            volume=5000,
            ullage=1200,
            height=92.5,
        )

        url = reverse("atg:veeder_stats")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["data"][0]["volume_gal"], 5000)


@override_settings(ATG_REMOTE_OCR_KEY="test-secret-key")
class RemoteOCRAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.store = Store.objects.create(store_num=101, store_name="Store 101")
        self.fuel_type = FuelType.objects.create(name="Regular")
        self.image = get_test_image()

    def test_unauthorized_access(self):
        # Access remote ocr instructions without correct headers
        url = reverse("atg:remote_ocr_instructions")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Access with incorrect headers
        self.client.credentials(HTTP_X_ATG_REMOTE_KEY="wrong-key")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorized_instructions(self):
        self.client.credentials(HTTP_X_ATG_REMOTE_KEY="test-secret-key")
        url = reverse("atg:remote_ocr_instructions")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("mission", response.data)

    def test_fetch_job_flow(self):
        ticket = VeederTicket.objects.create(
            store=self.store,
            image=self.image,
            uploaded_by=self.user,
            ocr_status="PENDING",
        )

        self.client.credentials(HTTP_X_ATG_REMOTE_KEY="test-secret-key")
        url = reverse("atg:remote_ocr_fetch")

        # First fetch should return the pending ticket
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], ticket.id)

        ticket.refresh_from_db()
        self.assertEqual(ticket.ocr_status, "PROCESSING")

        # Second fetch should return idle since no more tickets are PENDING
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "idle")

    def test_resolve_job_flow(self):
        ticket = VeederTicket.objects.create(
            store=self.store,
            image=self.image,
            uploaded_by=self.user,
            ocr_status="PROCESSING",
        )

        self.client.credentials(HTTP_X_ATG_REMOTE_KEY="test-secret-key")
        url = reverse("atg:remote_ocr_resolve")

        payload = {
            "ticket_id": ticket.id,
            "ocr_text": "1 Regular 5000 1200 92.5\nTotal volume 5000",
            "readings": [
                {
                    "tank_index": 1,
                    "fuel_type_id": self.fuel_type.id,
                    "volume": 5000,
                    "ullage": 1200,
                    "height": 92.5,
                    "temp": 68.4,
                    "water": 0.5,
                    "raw_line_text": "1 Regular 5000 1200 92.5",
                }
            ],
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        ticket.refresh_from_db()
        self.assertEqual(ticket.ocr_status, "COMPLETED")
        self.assertEqual(ticket.ocr_text, payload["ocr_text"])

        readings = ticket.readings.all()
        self.assertEqual(readings.count(), 1)
        self.assertEqual(readings.first().volume, 5000)
        self.assertEqual(readings.first().tank_index, 1)
        self.assertTrue(readings.first().is_user_corrected)
