from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from dms.models import Category, Document
from genericcharts.models import GenericChartGeneration
from genericcharts.services.dms_service import GenericChartDMSService
from dms.services.chart_artifact_safety import chart_document_safety_reason
from tankgauge.models import StoreType


@override_settings(MEDIA_ROOT="/tmp/webnexus-genericcharts-tests")
class GenericChartDMSServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="admin")
        self.service = GenericChartDMSService()

    def _generation(self):
        return GenericChartGeneration.objects.create(
            state="NC",
            package_scope_key="north-carolina",
            generator_version="1.2.1",
            requested_by=self.user,
        )

    def test_publish_supersedes_only_the_same_scope(self):
        first = self._generation()
        first_document = self.service.publish(
            generation=first,
            pdf_bytes=b"%PDF first",
            summary={},
        )
        second = self._generation()
        second_document = self.service.publish(
            generation=second,
            pdf_bytes=b"%PDF second",
            summary={},
        )

        first_document.refresh_from_db()
        second_document.refresh_from_db()
        self.assertEqual(first_document.status, "SUPERSEDED")
        self.assertFalse(first_document.is_public)
        self.assertEqual(second_document.status, "ACTIVE")
        self.assertTrue(second_document.is_public)
        self.assertIn("CoreStarterPack", second_document.description)
        self.assertNotIn('"coverage"', second_document.description)
        self.assertEqual(
            Document.objects.filter(category__slug="fng", status="ACTIVE").count(),
            1,
        )
        self.assertTrue(Category.objects.filter(slug="fng").exists())

    def test_publish_uses_editable_description(self):
        generation = self._generation()

        document = self.service.publish(
            generation=generation,
            pdf_bytes=b"%PDF description",
            summary={"stores": 1},
            description="A concise operator-facing description.",
        )

        self.assertEqual(document.description, "A concise operator-facing description.")

    def test_different_store_type_scopes_remain_active(self):
        exxon = StoreType.objects.create(name="Exxon")
        first = self._generation()
        first.options = {"store_type_ids": [exxon.id]}
        first.package_scope_key = "north-carolina-types-1"
        first.save(update_fields=["options", "package_scope_key"])
        first_document = self.service.publish(
            generation=first,
            pdf_bytes=b"%PDF exxon",
            summary={},
        )

        second = self._generation()
        second.package_scope_key = "north-carolina-types-2"
        second.save(update_fields=["package_scope_key"])
        second_document = self.service.publish(
            generation=second,
            pdf_bytes=b"%PDF other",
            summary={},
        )

        first_document.refresh_from_db()
        self.assertEqual(first_document.status, "ACTIVE")
        self.assertEqual(second_document.status, "ACTIVE")
        self.assertIn("Exxon", first_document.title)
        self.assertTrue(first_document.tags.filter(slug="store-type-exxon").exists())
        self.assertFalse(second_document.tags.filter(slug="store-type-exxon").exists())

    def test_publish_retains_source_validity_for_delivery_safety(self):
        generation = self._generation()
        generation.summary = {
            "source_validity": [
                {"estimate_status": "UNSAFE", "profile_status": "READY"}
            ]
        }
        generation.save(update_fields=["summary"])

        document = self.service.publish(
            generation=generation,
            pdf_bytes=b"%PDF unsafe source",
            summary=generation.summary,
        )

        generation.document = document
        generation.status = GenericChartGeneration.Status.COMPLETED
        generation.save(update_fields=["document", "status"])
        self.assertEqual(
            generation.summary["source_validity"][0]["estimate_status"], "UNSAFE"
        )
        self.assertEqual(
            chart_document_safety_reason(document), "generic_estimate_unsafe"
        )
