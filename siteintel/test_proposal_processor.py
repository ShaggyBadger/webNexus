from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from genericcharts.models import TankEstimateSyncRun
from siteintel.admin.proposal_admin import StoreUpdateAdmin
from siteintel.logic.proposal_processor import apply_proposal
from siteintel.models import LocationType, StoreUpdate, TankUpdate
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankCapacityProfileHistory,
    TankEstimation,
    TankType,
)


class StoreTankMappingSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="proposal-admin", password="test-password"
        )
        self.store = Store.objects.create(
            store_num=72001,
            store_name="Original Store Name",
        )
        self.location_type = LocationType.objects.create(name="Gas Station")
        self.tank_type = TankType.objects.create(name="10k gallon tank", capacity=10000)
        self.replacement_tank_type = TankType.objects.create(
            name="12k gallon tank", capacity=12000
        )

    def _create_proposal(self, *, status="APPROVED", store_name="Updated Store Name"):
        return StoreUpdate.objects.create(
            store=self.store,
            location_type=self.location_type,
            submitted_by=self.user,
            status=status,
            store_num=self.store.store_num,
            store_name=store_name,
            proposed_metadata={},
        )

    def _add_tank_update(
        self,
        proposal,
        *,
        tank_index,
        fuel_type="regular",
        tank_type=None,
    ):
        return TankUpdate.objects.create(
            store_update=proposal,
            tank_index=tank_index,
            fuel_type=fuel_type,
            reported_capacity=10000,
            tank_type=tank_type or self.tank_type,
        )

    def _create_mapping(self, *, tank_index=1, fuel_type="regular", tank_type=None):
        return StoreTankMapping.objects.create(
            store=self.store,
            tank_type=tank_type or self.tank_type,
            fuel_type=fuel_type,
            tank_index=tank_index,
            physical_capacity_gallons="9500.000",
            capacity_verified=True,
            capacity_source="MANUAL_VERIFIED",
            profile_status="READY",
            capacity_notes="Verified field capacity",
            profile_version=4,
        )

    def test_reuses_mapping_and_preserves_history_and_dependent_evidence(self):
        mapping = self._create_mapping()
        original_capacity_updated_at = mapping.capacity_updated_at
        profile_history = TankCapacityProfileHistory.objects.create(
            mapping=mapping,
            profile_version=4,
            previous_capacity_gallons="9000.000",
            new_capacity_gallons="9500.000",
            previous_verified=False,
            new_verified=True,
            previous_source="LEGACY_ASSUMED",
            new_source="MANUAL_VERIFIED",
            reason="Field verification",
            actor_type="USER",
            source_evidence_ids=["evidence-1"],
        )
        estimation = TankEstimation.objects.create(
            tank_mapping=mapping,
            radius=60,
            length=400,
            confidence=0.9,
            mean_error=1,
            max_error=2,
            sample_count=10,
            algorithm_version="test-1",
        )
        sync_run = TankEstimateSyncRun.objects.create(
            mapping=mapping,
            requested_by=self.user,
            scope_type="mapping",
        )
        proposal = self._create_proposal()
        self._add_tank_update(
            proposal,
            tank_index=1,
            tank_type=self.replacement_tank_type,
        )

        apply_proposal(proposal)

        mapping.refresh_from_db()
        self.assertEqual(StoreTankMapping.objects.filter(store=self.store).count(), 1)
        self.assertEqual(mapping.pk, profile_history.mapping_id)
        self.assertEqual(mapping.tank_type_id, self.replacement_tank_type.pk)
        self.assertEqual(mapping.physical_capacity_gallons, 9500)
        self.assertTrue(mapping.capacity_verified)
        self.assertEqual(mapping.profile_version, 4)
        self.assertEqual(mapping.capacity_notes, "Verified field capacity")
        self.assertEqual(mapping.capacity_updated_at, original_capacity_updated_at)
        self.assertTrue(
            TankCapacityProfileHistory.objects.filter(pk=profile_history.pk).exists()
        )
        self.assertTrue(TankEstimation.objects.filter(pk=estimation.pk).exists())
        self.assertTrue(TankEstimateSyncRun.objects.filter(pk=sync_run.pk).exists())

    def test_adds_new_mapping_and_keeps_unmentioned_mapping(self):
        existing_mapping = self._create_mapping(tank_index=1)
        history = TankCapacityProfileHistory.objects.create(
            mapping=existing_mapping,
            profile_version=4,
            previous_source="LEGACY_ASSUMED",
            new_source="MANUAL_VERIFIED",
            reason="Field verification",
        )
        proposal = self._create_proposal()
        self._add_tank_update(proposal, tank_index=2, fuel_type="diesel")

        apply_proposal(proposal)

        existing_mapping.refresh_from_db()
        self.assertTrue(
            StoreTankMapping.objects.filter(pk=existing_mapping.pk).exists()
        )
        self.assertTrue(
            TankCapacityProfileHistory.objects.filter(pk=history.pk).exists()
        )
        self.assertEqual(StoreTankMapping.objects.filter(store=self.store).count(), 2)
        added = StoreTankMapping.objects.get(store=self.store, tank_index=2)
        self.assertEqual(added.fuel_type, "diesel")
        self.assertEqual(added.canonical_fuel_type, "diesel")

    def test_duplicate_proposal_indexes_fail_without_partial_store_changes(self):
        proposal = self._create_proposal()
        self._add_tank_update(proposal, tank_index=1, fuel_type="regular")
        self._add_tank_update(proposal, tank_index=1, fuel_type="diesel")

        with self.assertRaises(ValidationError):
            apply_proposal(proposal)

        self.store.refresh_from_db()
        self.assertEqual(self.store.store_name, "Original Store Name")
        self.assertIsNone(self.store.location_id)
        self.assertFalse(StoreTankMapping.objects.filter(store=self.store).exists())

    def test_existing_fuel_conflict_fails_closed(self):
        self._create_mapping(tank_index=1, fuel_type="diesel")
        proposal = self._create_proposal()
        self._add_tank_update(proposal, tank_index=1, fuel_type="regular")

        with self.assertRaises(ValidationError):
            apply_proposal(proposal)

        self.assertEqual(
            StoreTankMapping.objects.get(store=self.store, tank_index=1).fuel_type,
            "diesel",
        )

    def test_duplicate_existing_physical_indexes_fail_closed(self):
        self._create_mapping(tank_index=1, fuel_type="regular")
        # The database constraint includes fuel, so legacy bad data can still
        # contain a second fuel assignment for the same physical index.
        self._create_mapping(tank_index=1, fuel_type="plus")
        proposal = self._create_proposal()
        self._add_tank_update(proposal, tank_index=1, fuel_type="regular")

        with self.assertRaises(ValidationError):
            apply_proposal(proposal)

        self.assertEqual(StoreTankMapping.objects.filter(store=self.store).count(), 2)

    def test_null_or_non_positive_index_fails_before_canonical_writes(self):
        for invalid_index in (None, 0, -1):
            with self.subTest(tank_index=invalid_index):
                proposal = self._create_proposal()
                self._add_tank_update(proposal, tank_index=invalid_index)

                with self.assertRaises(ValidationError):
                    apply_proposal(proposal)

                self.store.refresh_from_db()
                self.assertEqual(self.store.store_name, "Original Store Name")
                self.assertIsNone(self.store.location_id)
                self.assertFalse(
                    StoreTankMapping.objects.filter(store=self.store).exists()
                )

    def test_new_mapping_without_tank_type_fails(self):
        proposal = self._create_proposal()
        self._add_tank_update(proposal, tank_index=1, tank_type=None)
        TankUpdate.objects.filter(store_update=proposal).update(tank_type=None)

        with self.assertRaises(ValidationError):
            apply_proposal(proposal)

        self.assertFalse(StoreTankMapping.objects.filter(store=self.store).exists())

    def test_matching_mapping_keeps_type_when_proposal_has_none(self):
        mapping = self._create_mapping()
        proposal = self._create_proposal()
        self._add_tank_update(proposal, tank_index=1, tank_type=None)
        TankUpdate.objects.filter(store_update=proposal).update(tank_type=None)

        apply_proposal(proposal)

        mapping.refresh_from_db()
        self.assertEqual(mapping.tank_type_id, self.tank_type.pk)

    def test_no_tank_updates_leave_existing_mappings_unchanged(self):
        mapping = self._create_mapping()
        proposal = self._create_proposal()

        apply_proposal(proposal)

        self.assertTrue(StoreTankMapping.objects.filter(pk=mapping.pk).exists())
        self.assertEqual(StoreTankMapping.objects.filter(store=self.store).count(), 1)


class StoreUpdateAdminRetryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="siteintel-admin",
            email="admin@example.test",
            password="test-password",
        )
        self.store = Store.objects.create(store_num=72002, store_name="Retry Store")
        self.proposal = StoreUpdate.objects.create(
            store=self.store,
            submitted_by=self.user,
            store_num=self.store.store_num,
            store_name="Retry Store",
        )
        self.admin = StoreUpdateAdmin(StoreUpdate, AdminSite())
        self.request = RequestFactory().post("/admin/siteintel/storeupdate/")
        self.request.user = self.user

    @patch("django.contrib.messages.error")
    def test_change_form_failure_restores_pending_approval_state(self, message_error):
        proposal = StoreUpdate.objects.get(pk=self.proposal.pk)
        proposal.status = "APPROVED"
        form = SimpleNamespace(instance=proposal, save_m2m=Mock())
        tank_type = TankType.objects.create(name="Retry tank")

        class SubmittedTankInline:
            def save(self):
                TankUpdate.objects.create(
                    store_update=proposal,
                    tank_index=2,
                    fuel_type="regular",
                    reported_capacity=10000,
                    tank_type=tank_type,
                )

        with patch.object(
            StoreUpdate,
            "apply_update",
            side_effect=ValidationError("Invalid proposed tank mapping"),
        ):
            self.admin.save_model(self.request, proposal, form, change=True)
            self.admin.save_related(
                self.request,
                form,
                [SubmittedTankInline()],
                change=True,
            )

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "PENDING")
        self.assertIsNone(proposal.approved_by_id)
        self.assertIsNone(proposal.approved_at)
        self.assertEqual(proposal.tank_updates.count(), 1)
        self.assertEqual(proposal.tank_updates.get().tank_index, 2)
        message_error.assert_called_once()

    @patch("django.contrib.messages.error")
    def test_new_approved_proposal_returns_to_pending_after_failure(
        self, message_error
    ):
        proposal = StoreUpdate(
            store=self.store,
            submitted_by=self.user,
            status="APPROVED",
            store_num=self.store.store_num,
            store_name=self.store.store_name,
        )
        form = SimpleNamespace(instance=proposal, save_m2m=Mock())

        with patch.object(
            StoreUpdate,
            "apply_update",
            side_effect=ValidationError("Invalid proposed tank mapping"),
        ):
            self.admin.save_model(self.request, proposal, form, change=False)
            self.admin.save_related(self.request, form, [], change=False)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "PENDING")
        self.assertIsNone(proposal.approved_by_id)
        self.assertIsNone(proposal.approved_at)
        message_error.assert_called_once()

    def test_bulk_action_failure_leaves_proposal_pending(self):
        proposal = StoreUpdate.objects.get(pk=self.proposal.pk)

        with patch.object(
            StoreUpdate,
            "apply_update",
            side_effect=ValidationError("Invalid proposed tank mapping"),
        ):
            with patch.object(self.admin, "message_user") as message_user:
                self.admin.approve_and_apply(
                    self.request,
                    StoreUpdate.objects.filter(pk=proposal.pk),
                )

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "PENDING")
        self.assertIsNone(proposal.approved_by_id)
        self.assertIsNone(proposal.approved_at)
        message_user.assert_called_once()

    def test_change_form_sync_uses_tank_updates_saved_with_inline_formsets(self):
        location_type = LocationType.objects.create(name="Gas Station")
        existing_type = TankType.objects.create(name="Existing tank")
        proposal_type = TankType.objects.create(name="Submitted tank")
        mapping = StoreTankMapping.objects.create(
            store=self.store,
            tank_type=existing_type,
            fuel_type="regular",
            tank_index=1,
        )
        proposal = StoreUpdate.objects.create(
            store=self.store,
            location_type=location_type,
            submitted_by=self.user,
            store_num=self.store.store_num,
            store_name=self.store.store_name,
        )
        tank_update = TankUpdate.objects.create(
            store_update=proposal,
            tank_index=2,
            fuel_type="regular",
            reported_capacity=10000,
            tank_type=proposal_type,
        )
        proposal.status = "APPROVED"
        form = SimpleNamespace(instance=proposal, save_m2m=Mock())

        class SubmittedTankInline:
            def save(self):
                TankUpdate.objects.filter(pk=tank_update.pk).update(tank_index=1)

        self.admin.save_model(self.request, proposal, form, change=True)
        self.admin.save_related(
            self.request,
            form,
            [SubmittedTankInline()],
            change=True,
        )

        mapping.refresh_from_db()
        self.assertEqual(StoreTankMapping.objects.filter(store=self.store).count(), 1)
        self.assertEqual(mapping.tank_type_id, proposal_type.pk)
        self.assertEqual(mapping.tank_index, 1)
