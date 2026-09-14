from django.contrib.auth import get_user_model
from django.test import TestCase

from genericcharts.models import GenericChartGeneration


class GenericChartGenerationTests(TestCase):
    """Verify the generation-history foundation before pipeline work begins."""

    def test_generation_defaults_to_pending(self):
        user = get_user_model().objects.create_user(
            username="chart-admin",
            password="not-a-real-secret",
        )

        generation = GenericChartGeneration.objects.create(
            state="FULL",
            generator_version="1.2.1",
            requested_by=user,
        )

        self.assertEqual(generation.status, GenericChartGeneration.Status.PENDING)
        self.assertEqual(generation.options, {})
        self.assertEqual(generation.package_scope_key, "full")
        self.assertEqual(generation.summary, {})
        self.assertEqual(str(generation), "CoreStarterPack [FULL] v1.2.1 (pending)")
