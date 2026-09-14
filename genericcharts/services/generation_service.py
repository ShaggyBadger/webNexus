"""Admin-controlled generic package generation orchestration."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from genericcharts.models import GenericChartGeneration
from genericcharts.pdf import CoreStarterPackPDFRenderer
from genericcharts.pipeline.dataclasses import SelectionSpec
from genericcharts.services.dms_service import GenericChartDMSService
from genericcharts.pipeline.package import build_package_data
from genericcharts.version import PACKAGE_VERSION

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATION_LOG_FILE = PROJECT_ROOT / "logs" / "generic_chart_generation.log"
STALE_GENERATION_MINUTES = 30


def create_generation(
    *, requested_by, selection: SelectionSpec, options: dict
) -> GenericChartGeneration:
    """Create a durable pending job from validated admin configuration."""

    return GenericChartGeneration.objects.create(
        state="FULL" if selection.is_full else selection.state,
        package_scope_key=selection.package_scope_key,
        generator_version=PACKAGE_VERSION,
        options=options,
        requested_by=requested_by,
    )


def launch_generation(generation_id: int) -> None:
    """Launch one worker process; the worker rechecks job state before running."""

    GENERATION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with GENERATION_LOG_FILE.open("ab") as log_file:
        subprocess.Popen(
            [
                sys.executable,
                str(PROJECT_ROOT / "manage.py"),
                "generate_generic_chart_package",
                "--generation-id",
                str(generation_id),
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            close_fds=True,
            start_new_session=True,
        )


def run_generation(generation_id: int) -> GenericChartGeneration | None:
    """Claim, build, publish, and finalize one package job."""

    now = timezone.now()
    with transaction.atomic():
        running = GenericChartGeneration.objects.select_for_update().filter(
            status=GenericChartGeneration.Status.RUNNING
        )
        stale_before = now - timedelta(minutes=STALE_GENERATION_MINUTES)
        stale_jobs = running.filter(started_at__lt=stale_before)
        stale_jobs.update(
            status=GenericChartGeneration.Status.FAILED,
            completed_at=now,
            failure_reason="Generation worker timed out.",
        )
        if running.exclude(started_at__lt=stale_before).exists():
            return GenericChartGeneration.objects.filter(id=generation_id).first()
        claimed = GenericChartGeneration.objects.filter(
            id=generation_id,
            status=GenericChartGeneration.Status.PENDING,
        ).update(status=GenericChartGeneration.Status.RUNNING, started_at=now)
    if claimed != 1:
        return GenericChartGeneration.objects.filter(id=generation_id).first()
    generation = GenericChartGeneration.objects.get(id=generation_id)
    try:
        options = generation.options
        selection = SelectionSpec(
            state=None if generation.state == "FULL" else generation.state,
            store_numbers=tuple(options.get("store_numbers", ())),
            store_type_ids=tuple(options.get("store_type_ids", ())),
        )
        package = build_package_data(
            selection=selection,
            volume_gap_percent=float(options["volume_gap_percent"]),
            near_duplicate_tolerance_percent=float(
                options["near_duplicate_tolerance_percent"]
            ),
            outlier_multiplier=float(options["outlier_multiplier"]),
        )
        pdf_bytes = CoreStarterPackPDFRenderer().render(package)
        summary = {
            "stores": len(package.stores),
            "generated_tanks": len(package.generated_tanks),
            "catalog_size": len(package.catalog),
            "coverage": package.coverage_report,
            "package_scope_key": generation.package_scope_key,
        }
        document = GenericChartDMSService().publish(
            generation=generation,
            pdf_bytes=pdf_bytes,
            summary=summary,
            description=options.get("document_description"),
        )
        generation.status = GenericChartGeneration.Status.COMPLETED
        generation.completed_at = timezone.now()
        generation.summary = summary
        generation.document = document
        generation.save(update_fields=["status", "completed_at", "summary", "document"])
    except Exception as exc:
        logger.exception(
            "GENERIC_CHART_PACKAGE_GENERATION_FAILED",
            extra={"generation_id": generation_id},
        )
        generation.status = GenericChartGeneration.Status.FAILED
        generation.completed_at = timezone.now()
        generation.failure_reason = str(exc)
        generation.save(update_fields=["status", "completed_at", "failure_reason"])
    return generation
