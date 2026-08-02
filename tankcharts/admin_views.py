import logging
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANAGE_SCRIPT = PROJECT_ROOT / "manage.py"
BATCH_LOG_FILE = PROJECT_ROOT / "logs" / "generate_all_tank_charts.log"


@staff_member_required
@require_POST
def trigger_generate_all_tank_charts(request):
    """
    Staff action to trigger batch tank chart generation from admin panel.

    Dry-runs complete synchronously so the admin sees the report immediately.
    Real generation is offloaded to a detached subprocess so the request
    returns right away instead of blocking a Gunicorn worker thread.
    """
    force = request.POST.get("force") == "1"
    dry_run = request.POST.get("dry_run") == "1"

    if dry_run:
        return _run_dry_run(request, force=force)

    return _spawn_generation(request, force=force)


def _run_dry_run(request, *, force: bool):
    out = StringIO()
    try:
        call_command(
            "generate_all_tank_charts",
            stdout=out,
            force=force,
            dry_run=True,
        )
    except Exception as exc:
        logger.exception("BATCH_CHART_GENERATION_DRY_RUN_FAILED")
        messages.error(request, f"Batch chart generation DRY-RUN failed: {exc}")
    else:
        messages.info(
            request,
            f"Batch chart generation DRY-RUN completed.\n{out.getvalue()}",
        )
    return redirect("admin:index")


def _spawn_generation(request, *, force: bool):
    try:
        BATCH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BATCH_LOG_FILE, "ab") as log_file:
            spawn_env = os.environ.copy()
            spawn_env.setdefault("PYTHONUNBUFFERED", "1")
            subprocess.Popen(
                _generation_command(force=force),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
                env=spawn_env,
                close_fds=True,
                start_new_session=True,
            )
    except OSError as exc:
        logger.exception("BATCH_CHART_GENERATION_SPAWN_FAILED")
        messages.error(
            request,
            f"Batch chart generation could not be started: {exc}",
        )
        return redirect("admin:index")

    messages.info(
        request,
        "Batch chart generation started in the background. "
        f"Progress is written to {BATCH_LOG_FILE}.",
    )
    return redirect("admin:index")


def _generation_command(*, force: bool) -> list[str]:
    cmd = [sys.executable, str(MANAGE_SCRIPT), "generate_all_tank_charts"]
    if force:
        cmd.append("--force")
    return cmd
