from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from genericcharts.forms import GenericChartReviewForm
from genericcharts.models import GenericChartGeneration
from tankgauge.models import Store, StoreType


class GenericChartReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="chart-admin",
            password="not-a-real-secret",
        )
        Store.objects.create(store_num=91001, state="NC")
        Store.objects.create(store_num=91003, state="north carolina")
        Store.objects.create(store_num=91002, state="Virginia")
        self.exxon = StoreType.objects.create(name="Exxon")
        self.mobil = StoreType.objects.create(name="Mobil")

    def test_review_form_normalizes_allowlist_and_selection_scope(self):
        form = GenericChartReviewForm(
            data={
                "state": "NC",
                "store_numbers": "12, 4, 12",
                "store_type_ids": [str(self.exxon.id)],
                "volume_gap_percent": "3",
                "near_duplicate_tolerance_percent": "1",
                "outlier_multiplier": "2",
                "document_description": "Custom package description.",
            }
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.selection_spec().package_scope_key,
            f"north-carolina-stores-4-12-types-{self.exxon.id}",
        )

    def test_state_choices_put_full_first_and_load_database_states(self):
        form = GenericChartReviewForm()

        self.assertEqual(form.fields["state"].choices[0], ("FULL", "FULL - All states"))
        self.assertEqual(
            list(form.fields["state"].choices)[1:],
            [("NC", "North Carolina"), ("VA", "Virginia")],
        )

    def test_store_type_choices_default_to_all_types(self):
        form = GenericChartReviewForm()

        self.assertEqual(
            form.store_type_options,
            ((str(self.exxon.id), "Exxon"), (str(self.mobil.id), "Mobil")),
        )
        self.assertEqual(
            form.selected_store_type_ids,
            {str(self.exxon.id), str(self.mobil.id)},
        )

    def test_review_page_requires_staff_and_renders_for_staff(self):
        url = reverse("admin:genericcharts_genericchartgeneration_review")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        non_staff = get_user_model().objects.create_user(
            username="regular-user",
            password="not-a-real-secret",
        )
        self.client.force_login(non_staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CoreStarterPack Package Review")
        self.assertContains(response, 'name="state"')
        self.assertContains(response, 'name="volume_gap_percent"')
        self.assertContains(response, 'id="store-types-available"')
        self.assertContains(response, "Exxon")
        self.assertContains(response, "Mobil")
        self.assertContains(response, "Lower values create more separate charts")
        self.assertContains(response, "higher values merge more similar curves")
        self.assertContains(response, 'name="outlier_multiplier"')
        self.assertContains(
            response, "changes review flags, not the generated chart curve"
        )

    def test_staff_without_model_view_permission_cannot_review(self):
        staff_user = get_user_model().objects.create_user(
            username="limited-staff",
            password="not-a-real-secret",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(
            reverse("admin:genericcharts_genericchartgeneration_review")
        )

        self.assertEqual(response.status_code, 403)

    @patch("genericcharts.admin.launch_generation")
    def test_admin_can_start_generation_from_valid_configuration(self, launch):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("admin:genericcharts_genericchartgeneration_generate"),
            {
                "state": "NC",
                "store_numbers": "101, 202",
                "store_type_ids": [str(self.exxon.id), str(self.mobil.id)],
                "volume_gap_percent": "3",
                "near_duplicate_tolerance_percent": "1",
                "outlier_multiplier": "2",
                "document_description": "Custom package description.",
            },
        )

        self.assertEqual(response.status_code, 302)
        launch.assert_called_once()
        generation = GenericChartGeneration.objects.get()
        self.assertEqual(
            generation.options["document_description"],
            "Custom package description.",
        )
        self.assertEqual(
            generation.options["store_type_ids"], [self.exxon.id, self.mobil.id]
        )
