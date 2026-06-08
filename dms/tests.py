import os
import shutil
import tempfile
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from dms.models import Category, Collection, Document, TemporaryUpload, Tag
from dms.services.upload_service import DocumentUploadService
from dms.services.download_service import DocumentDownloadService
from dms.services.search_service import DocumentSearchService
from dms.management.commands.purge_deleted_documents import Command as PurgeCommand
from siteintel.models import Location, LocationType


# Set up a temporary media directory for testing file storage
TEMP_MEDIA_DIR = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_DIR)
class DMSTestCase(APITestCase):
    """
    Test suite for Document Management System (DMS) models, services, views and cleanup.
    """

    def setUp(self):
        # Create user accounts
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpassword"
        )
        self.staff_user = User.objects.create_user(
            username="staff", email="staff@test.com", password="staffpassword", is_staff=True
        )
        self.standard_user = User.objects.create_user(
            username="user", email="user@test.com", password="userpassword"
        )

        # Create Category
        self.category_safety = Category.objects.create(
            name="Safety Guidelines", slug="safety-guidelines", active=True, sort_order=1
        )
        self.category_inactive = Category.objects.create(
            name="Old Forms", slug="old-forms", active=False, sort_order=10
        )

        # Create Collection
        self.collection_public = Collection.objects.create(
            name="Public Safety Pack", description="Public facing guidelines", is_public=True
        )
        self.collection_private = Collection.objects.create(
            name="Confidential Operations", description="Internal operations", is_public=False
        )

        # Content file content
        self.file_content = b"%PDF-1.4 sample pdf file content"
        self.test_file = SimpleUploadedFile("test_guide.pdf", self.file_content, content_type="application/pdf")

    def tearDown(self):
        # Clean up temporary media directory
        if os.path.exists(TEMP_MEDIA_DIR):
            shutil.rmtree(TEMP_MEDIA_DIR)

    def test_category_slug_and_sort(self):
        self.assertEqual(str(self.category_safety), "Safety Guidelines")
        self.assertTrue(self.category_safety.active)
        self.assertFalse(self.category_inactive.active)

    def test_upload_service_two_phase_flow(self):
        # 1. Phase A: Raw Ingestion
        raw_result = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        self.assertIn("temp_id", raw_result)
        self.assertEqual(raw_result["original_name"], "test_guide.pdf")
        self.assertEqual(raw_result["mime_type"], "application/pdf")
        self.assertFalse(raw_result["is_duplicate"])

        temp_upload = TemporaryUpload.objects.get(id=raw_result["temp_id"])
        self.assertEqual(temp_upload.uploaded_by, self.staff_user)

        # 2. Phase B: Finalize Upload
        doc = DocumentUploadService.finalize_upload(
            temp_id=temp_upload.id,
            user=self.staff_user,
            title="Fire Safety Drill Guide",
            description="Emergency procedures handbook",
            category_id=self.category_safety.id,
            collection_ids=[self.collection_public.id],
        )

        self.assertEqual(doc.title, "Fire Safety Drill Guide")
        self.assertEqual(doc.category, self.category_safety)
        self.assertIn(self.collection_public, doc.collections.all())
        self.assertEqual(doc.uploaded_by, self.staff_user)
        self.assertEqual(doc.mime_type, "application/pdf")
        self.assertEqual(doc.status, "ACTIVE")

        # TemporaryUpload database entry and temporary file should be gone
        self.assertFalse(TemporaryUpload.objects.filter(id=temp_upload.id).exists())

    def test_download_service(self):
        # First ingest and finalize document
        raw_result = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc = DocumentUploadService.finalize_upload(
            temp_id=raw_result["temp_id"],
            user=self.staff_user,
            title="Drill Guide",
            category_id=self.category_safety.id,
        )

        # Perform download
        file_obj, filename, mime_type = DocumentDownloadService.prepare_download(doc.id)
        
        self.assertEqual(filename, "test_guide.pdf")
        self.assertEqual(mime_type, "application/pdf")
        
        # Verify download count incremented
        doc.refresh_from_db()
        self.assertEqual(doc.download_count, 1)

    def test_search_and_filter_service(self):
        # Ingest and finalize two documents
        raw_1 = DocumentUploadService.handle_raw_upload(
            SimpleUploadedFile("safety.pdf", self.file_content, content_type="application/pdf"),
            self.staff_user,
        )
        doc_safety = DocumentUploadService.finalize_upload(
            temp_id=raw_1["temp_id"],
            user=self.staff_user,
            title="Emergency Safety Protocol",
            description="General office safety guidelines",
            category_id=self.category_safety.id,
        )

        raw_2 = DocumentUploadService.handle_raw_upload(
            SimpleUploadedFile("compliance.pdf", self.file_content, content_type="application/pdf"),
            self.staff_user,
        )
        doc_compliance = DocumentUploadService.finalize_upload(
            temp_id=raw_2["temp_id"],
            user=self.staff_user,
            title="Quarterly Compliance Audit",
            description="Compliance criteria for regional yards",
        )

        # Link doc_compliance to a Location in "NC"
        loc_type = LocationType.objects.create(name="Yard")
        nc_location = Location.objects.create(name="Raleigh Yard", location_type=loc_type, state="NC")
        
        doc_compliance.content_type = ContentType.objects.get_for_model(Location)
        doc_compliance.object_id = str(nc_location.id)
        doc_compliance.save()

        # Test simple search text query
        results = DocumentSearchService.search_documents(search_query="Audit")
        self.assertIn(doc_compliance, results)
        self.assertNotIn(doc_safety, results)

        # Test Category filtering
        results = DocumentSearchService.search_documents(category_id=self.category_safety.id)
        self.assertIn(doc_safety, results)
        self.assertNotIn(doc_compliance, results)

        # Test State filtering
        results = DocumentSearchService.search_documents(state="NC")
        self.assertIn(doc_compliance, results)
        self.assertNotIn(doc_safety, results)

    def test_api_upload_and_download_views(self):
        # 1. Log in as Staff User
        self.client.force_login(self.staff_user)

        # 2. Phase A Request
        response = self.client.post(reverse("dms:api_raw_upload"), {"file": self.test_file})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "success")
        
        temp_id = response.data["data"]["temp_id"]

        # 3. Phase B Request
        payload = {
            "temp_id": temp_id,
            "title": "Staff Training Manual",
            "description": "Initial onboarding overview",
            "category": self.category_safety.id,
            "collections": [self.collection_public.id],
        }
        response = self.client.post(
            reverse("dms:api_finalize_upload"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doc_id = response.data["data"]["id"]

        # 4. Download document
        self.client.force_login(self.standard_user)
        download_url = reverse("dms:document_download", args=[doc_id])
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="test_guide.pdf"')

    def test_api_metadata_update_permissions(self):
        # Ingest and finalize doc
        raw_res = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc = DocumentUploadService.finalize_upload(
            temp_id=raw_res["temp_id"], user=self.staff_user, title="Original Title"
        )

        detail_url = reverse("dms:api_document_detail", args=[doc.id])

        # Standard user PATCH -> Expect 403 Forbidden
        self.client.force_login(self.standard_user)
        response = self.client.patch(detail_url, {"title": "Hacked Title"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Staff user PATCH -> Expect 200 OK
        self.client.force_login(self.staff_user)
        response = self.client.patch(detail_url, {"title": "Updated Title"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.title, "Updated Title")
        # Version should increment on update
        self.assertEqual(doc.version, 2)

    def test_soft_delete_flow(self):
        # Ingest and finalize doc
        raw_res = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc = DocumentUploadService.finalize_upload(
            temp_id=raw_res["temp_id"], user=self.staff_user, title="To Be Soft Deleted"
        )

        # Staff DELETE -> Soft delete (archives document and moves file to trash)
        self.client.force_login(self.staff_user)
        detail_url = reverse("dms:api_document_detail", args=[doc.id])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        doc.refresh_from_db()
        self.assertEqual(doc.status, "ARCHIVED")
        self.assertTrue(doc.file_path.startswith("trash/"))
        self.assertFalse(doc.file_path.startswith("documents/"))

    def test_finalize_upload_with_tags_and_visibility(self):
        self.client.force_login(self.staff_user)
        
        # Phase A
        response = self.client.post(reverse("dms:api_raw_upload"), {"file": self.test_file})
        temp_id = response.data["data"]["temp_id"]

        # Phase B with tags (strings and IDs) and public visibility
        tag1 = Tag.objects.create(name="Propane", slug="propane")
        payload = {
            "temp_id": temp_id,
            "title": "Public Propane Guide",
            "is_public": True,
            "tags": [tag1.id, "Winter", "Safety"]
        }
        response = self.client.post(reverse("dms:api_finalize_upload"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        doc = Document.objects.get(id=response.data["data"]["id"])
        self.assertTrue(doc.is_public)
        self.assertEqual(doc.tags.count(), 3)
        self.assertTrue(doc.tags.filter(name="Propane").exists())
        self.assertTrue(doc.tags.filter(name="Winter").exists())
        self.assertTrue(doc.tags.filter(name="Safety").exists())

    def test_public_visibility_enforcement(self):
        # Create one public and one private document
        raw_1 = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc_public = DocumentUploadService.finalize_upload(
            temp_id=raw_1["temp_id"], user=self.staff_user, title="Public Doc", is_public=True
        )

        raw_2 = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc_private = DocumentUploadService.finalize_upload(
            temp_id=raw_2["temp_id"], user=self.staff_user, title="Private Doc", is_public=False
        )

        # 1. Standard user list view -> should only see public doc
        self.client.force_login(self.standard_user)
        response = self.client.get(reverse("dms:api_documents"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [d["id"] for d in response.data["data"]]
        self.assertIn(doc_public.id, ids)
        self.assertNotIn(doc_private.id, ids)

        # 2. Standard user detail view of private doc -> should 404
        response = self.client.get(reverse("dms:api_document_detail", args=[doc_private.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Staff user list view -> should see both
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dms:api_documents"))
        ids = [d["id"] for d in response.data["data"]]
        self.assertIn(doc_public.id, ids)
        self.assertIn(doc_private.id, ids)

    def test_tag_search(self):
        tag_winter = Tag.objects.create(name="Winter", slug="winter")
        
        raw_1 = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc_winter = DocumentUploadService.finalize_upload(
            temp_id=raw_1["temp_id"], user=self.staff_user, title="Winter Guide", tag_ids=[tag_winter.id]
        )

        raw_2 = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc_other = DocumentUploadService.finalize_upload(
            temp_id=raw_2["temp_id"], user=self.staff_user, title="Other Guide"
        )

        # Search by tag_slug
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dms:api_documents"), {"tag_slug": "winter"})
        ids = [d["id"] for d in response.data["data"]]
        self.assertIn(doc_winter.id, ids)
        self.assertNotIn(doc_other.id, ids)

        # Search by generic query including tag name
        response = self.client.get(reverse("dms:api_documents"), {"q": "Winter"})
        ids = [d["id"] for d in response.data["data"]]
        self.assertIn(doc_winter.id, ids)

    def test_patch_tags_and_visibility(self):
        raw = DocumentUploadService.handle_raw_upload(self.test_file, self.staff_user)
        doc = DocumentUploadService.finalize_upload(
            temp_id=raw["temp_id"], user=self.staff_user, title="Initial Title", is_public=False
        )

        self.client.force_login(self.staff_user)
        payload = {
            "title": "Updated Title",
            "is_public": True,
            "tags": ["NewTag", "AnotherTag"]
        }
        response = self.client.patch(reverse("dms:api_document_detail", args=[doc.id]), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        doc.refresh_from_db()
        self.assertEqual(doc.title, "Updated Title")
        self.assertTrue(doc.is_public)
        self.assertEqual(doc.tags.count(), 2)
        self.assertTrue(doc.tags.filter(name="NewTag").exists())
