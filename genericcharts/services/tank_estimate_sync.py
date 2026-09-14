"""Asynchronous admin launch and status helpers for tank estimate syncs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.utils import timezone

from genericcharts.models import TankEstimateSyncRun

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNC_LOG_FILE = PROJECT_ROOT / "logs" / "tank_estimate_sync.log"


def launch_tank_estimate_sync(run: TankEstimateSyncRun) -> None:
    """Launch the sync worker outside the request process."""

    SYNC_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(PROJECT_ROOT / "manage.py"),
        "run_tank_estimate_sync",
        "--run-id",
        str(run.id),
    ]
    with SYNC_LOG_FILE.open("ab") as log_file:
        try:
            subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                close_fds=True,
                start_new_session=True,
            )
        except Exception as exc:
            run.status = TankEstimateSyncRun.Status.FAILED
            run.completed_at = timezone.now()
            run.failure_reason = str(exc)
            run.save(update_fields=["status", "completed_at", "failure_reason"])
            raise
