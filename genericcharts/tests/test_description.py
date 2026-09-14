from types import SimpleNamespace

from django.test import SimpleTestCase

from genericcharts.pipeline.dataclasses import SelectionSpec
from genericcharts.services.description import default_document_description


class DocumentDescriptionTests(SimpleTestCase):
    def _package(self):
        return SimpleNamespace(
            stores=(1, 2),
            generated_tanks=(1, 2, 3),
            catalog={"1k": object(), "2k": object()},
            coverage_report={
                "stores_covered": 2,
                "review_required": [{"store_id": 1}],
            },
        )

    def test_full_description(self):
        description = default_document_description(
            selection=SelectionSpec(), package=self._package()
        )

        self.assertIn("all states CoreStarterPack", description)

    def test_state_description(self):
        description = default_document_description(
            selection=SelectionSpec(state="NC"), package=self._package()
        )

        self.assertIn("NC CoreStarterPack", description)

    def test_allowlist_description(self):
        description = default_document_description(
            selection=SelectionSpec(state="NC", store_numbers=(202, 101)),
            package=self._package(),
        )

        self.assertIn("NC stores 101, 202 CoreStarterPack", description)
