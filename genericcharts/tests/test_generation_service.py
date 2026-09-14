from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from genericcharts.models import GenericChartGeneration
from genericcharts.pipeline.dataclasses import SelectionSpec
from genericcharts.services.generation_service import create_generation, run_generation


class GenericChartGenerationServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="admin")

    def test_create_generation_persists_scope_and_options(self):
        generation = create_generation(
            requested_by=self.user,
            selection=SelectionSpec(state="NC", store_numbers=(12, 4)),
            options={"store_numbers": [4, 12], "volume_gap_percent": 3.0},
        )

        self.assertEqual(generation.package_scope_key, "north-carolina-stores-4-12")
        self.assertEqual(generation.status, GenericChartGeneration.Status.PENDING)
        self.assertEqual(generation.options["store_numbers"], [4, 12])

    @patch("genericcharts.services.generation_service.build_package_data")
    def test_failed_generation_preserves_job_failure_without_document(
        self, build_package
    ):
        generation = create_generation(
            requested_by=self.user,
            selection=SelectionSpec(),
            options={
                "store_numbers": [],
                "volume_gap_percent": 3.0,
                "near_duplicate_tolerance_percent": 1.0,
                "outlier_multiplier": 2.0,
            },
        )
        build_package.side_effect = ValueError("controlled failure")

        result = run_generation(generation.id)

        result.refresh_from_db()
        self.assertEqual(result.status, GenericChartGeneration.Status.FAILED)
        self.assertEqual(result.failure_reason, "controlled failure")
        self.assertIsNone(result.document)

    def test_running_job_blocks_a_second_worker(self):
        running = create_generation(
            requested_by=self.user,
            selection=SelectionSpec(),
            options={"store_numbers": []},
        )
        running.status = GenericChartGeneration.Status.RUNNING
        running.save(update_fields=["status"])
        pending = create_generation(
            requested_by=self.user,
            selection=SelectionSpec(state="NC"),
            options={"store_numbers": []},
        )

        result = run_generation(pending.id)

        self.assertEqual(result.id, pending.id)
        pending.refresh_from_db()
        self.assertEqual(pending.status, GenericChartGeneration.Status.PENDING)

    def test_stale_running_job_is_failed_before_new_job_claim(self):
        stale = create_generation(
            requested_by=self.user,
            selection=SelectionSpec(),
            options={"store_numbers": []},
        )
        stale.status = GenericChartGeneration.Status.RUNNING
        stale.started_at = timezone.now() - timedelta(minutes=31)
        stale.save(update_fields=["status", "started_at"])
        pending = create_generation(
            requested_by=self.user,
            selection=SelectionSpec(state="NC"),
            options={"store_numbers": []},
        )

        result = run_generation(pending.id)

        self.assertEqual(result.status, GenericChartGeneration.Status.FAILED)
        stale.refresh_from_db()
        self.assertEqual(stale.status, GenericChartGeneration.Status.FAILED)
