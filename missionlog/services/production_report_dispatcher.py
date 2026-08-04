import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("webnexus")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANAGE_SCRIPT = PROJECT_ROOT / "manage.py"
WORKER_LOG_FILE = PROJECT_ROOT / "logs" / "missionlog_production_report_worker.log"


class ProductionReportDispatcher:
    """
    Commander's Intent:
    Offload report-email generation out of the request cycle so MissionLog UI
    remains responsive and SMTP/chart delays never block field operators.
    """

    @staticmethod
    def enqueue(*, audit_id: int) -> bool:
        try:
            WORKER_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(WORKER_LOG_FILE, "ab") as log_file:
                spawn_env = os.environ.copy()
                spawn_env.setdefault("PYTHONUNBUFFERED", "1")
                subprocess.Popen(
                    [
                        sys.executable,
                        str(MANAGE_SCRIPT),
                        "send_production_report_email",
                        "--audit-id",
                        str(audit_id),
                    ],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=str(PROJECT_ROOT),
                    env=spawn_env,
                    close_fds=True,
                    start_new_session=True,
                )
        except OSError:
            logger.exception(
                "MISSIONLOG_REPORT_EMAIL_QUEUE_FAILED",
                extra={"audit_id": audit_id},
            )
            return False

        return True
