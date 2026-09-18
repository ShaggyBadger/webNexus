from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase

from genericcharts.forms_sync import TankEstimateSyncForm
from genericcharts.models import TankEstimateSyncRun


class TankEstimateSyncFormTests(SimpleTestCase):
    def test_targeted_scope_requires_store_number(self):
        form = TankEstimateSyncForm(data={"scope": "store"})

        self.assertFalse(form.is_valid())
        self.assertIn("store_number", form.errors)

    def test_mapping_scope_requires_mapping(self):
        form = TankEstimateSyncForm(data={"scope": "mapping"})

        self.assertFalse(form.is_valid())
        self.assertIn("mapping", form.errors)


class TankEstimateSyncCommandTests(TestCase):
    def test_worker_records_successful_command_output(self):
        user = get_user_model().objects.create_user(username="sync-admin")
        run = TankEstimateSyncRun.objects.create(
            store_number=6947,
            mapped_only=True,
            requested_by=user,
        )

        with patch(
            "genericcharts.management.commands.run_tank_estimate_sync.call_command"
        ) as sync_command:
            sync_command.side_effect = (
                lambda *args, stdout, stderr, **kwargs: stdout.write("SYNC COMPLETE")
            )
            call_command("run_tank_estimate_sync", "--run-id", run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, TankEstimateSyncRun.Status.COMPLETED)
        self.assertIn("SYNC COMPLETE", run.output)
        sync_command.assert_called_once_with(
            "sync_tank_estimates",
            stdout=sync_command.call_args.kwargs["stdout"],
            stderr=sync_command.call_args.kwargs["stderr"],
            mapped_only=True,
            virtual_only=False,
            store=6947,
        )

    def test_worker_marks_nonzero_failures_as_partial(self):
        user = get_user_model().objects.create_user(username="partial-admin")
        run = TankEstimateSyncRun.objects.create(
            requested_by=user,
            mapped_only=True,
        )

        with patch(
            "genericcharts.management.commands.run_tank_estimate_sync.call_command"
        ) as sync_command:
            sync_command.side_effect = lambda *args, stdout, stderr, **kwargs: stdout.write(
                "SYNC COMPLETE | mapped_ok=1 mapped_failed=2 virtual_ok=0 virtual_failed=0"
            )
            call_command("run_tank_estimate_sync", "--run-id", run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, TankEstimateSyncRun.Status.PARTIAL_FAILURE)
