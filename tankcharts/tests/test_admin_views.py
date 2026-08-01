import sys
from pathlib import Path
from tempfile import gettempdir
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tankcharts.admin_views import MANAGE_SCRIPT, _generation_command


class TriggerGenerateAllTankChartsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="secret", is_staff=True)
        self.client.force_login(self.admin)
        self.url = reverse("admin:tankcharts_storechartgeneration_generate_all")

    def test_generation_offloaded_to_background_subprocess(self):
        with mock.patch("tankcharts.admin_views.subprocess.Popen") as popen:
            with mock.patch(
                "tankcharts.admin_views.BATCH_LOG_FILE",
                Path(gettempdir()) / "test_generate_all_tank_charts.log",
            ):
                response = self.client.post(self.url, {"force": "1"})

        self.assertEqual(response.status_code, 302)
        popen.assert_called_once()
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1], str(MANAGE_SCRIPT))
        self.assertIn("generate_all_tank_charts", cmd)
        self.assertIn("--force", cmd)

    def test_generation_does_not_call_command_in_request(self):
        with mock.patch("tankcharts.admin_views.call_command") as call_command_mock:
            with mock.patch("tankcharts.admin_views.subprocess.Popen"):
                response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 302)
        call_command_mock.assert_not_called()

    def test_dry_run_runs_synchronously(self):
        with mock.patch("tankcharts.admin_views.call_command") as call_command_mock:
            response = self.client.post(self.url, {"dry_run": "1"})

        self.assertEqual(response.status_code, 302)
        call_command_mock.assert_called_once()
        self.assertEqual(
            call_command_mock.call_args.args[0], "generate_all_tank_charts"
        )
        self.assertTrue(call_command_mock.call_args.kwargs["dry_run"])

    def test_generation_command_builder(self):
        self.assertEqual(
            _generation_command(force=False),
            [sys.executable, str(MANAGE_SCRIPT), "generate_all_tank_charts"],
        )
        self.assertEqual(_generation_command(force=True)[-1], "--force")

    def test_requires_staff(self):
        plain = User.objects.create_user("plain", password="secret")
        self.client.force_login(plain)
        with mock.patch("tankcharts.admin_views.subprocess.Popen") as popen:
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
        popen.assert_not_called()
