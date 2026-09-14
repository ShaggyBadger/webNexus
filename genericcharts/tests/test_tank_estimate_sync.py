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
