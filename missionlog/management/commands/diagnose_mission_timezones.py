import json
from datetime import datetime, timezone as datetime_timezone

from django.core.management.base import BaseCommand

from missionlog.models import Mission
from missionlog.services.datetime_normalization import resolve_user_timezone


def _parse_date_arg(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=datetime_timezone.utc)


class Command(BaseCommand):
    help = (
        "Read-only MissionLog timezone diagnostic. Reports stored UTC values, "
        "current local display, and proposed corrected values if stored wall-clock "
        "components were interpreted in the user's profile timezone."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, default=None)
        parser.add_argument("--start-utc", type=str, default=None)
        parser.add_argument("--end-utc", type=str, default=None)
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        queryset = Mission.objects.select_related("user", "user__profile").order_by(
            "shift_start", "id"
        )

        user_id = options.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        start_utc = _parse_date_arg(options.get("start_utc"))
        if start_utc:
            queryset = queryset.filter(shift_start__gte=start_utc)

        end_utc = _parse_date_arg(options.get("end_utc"))
        if end_utc:
            queryset = queryset.filter(shift_start__lte=end_utc)

        rows = []
        for mission in queryset[: options["limit"]]:
            tz = resolve_user_timezone(mission.user)
            start_utc_value = mission.shift_start.astimezone(datetime_timezone.utc)
            current_local_start = start_utc_value.astimezone(tz)

            proposed_local_start = start_utc_value.replace(tzinfo=None).replace(
                tzinfo=tz
            )
            proposed_utc_start = proposed_local_start.astimezone(datetime_timezone.utc)
            proposed_display_start = proposed_utc_start.astimezone(tz)

            row = {
                "mission_id": mission.id,
                "owner_id": mission.user_id,
                "owner_username": mission.user.username,
                "profile_timezone": str(tz),
                "stored_start_utc": start_utc_value.isoformat(),
                "current_local_start": current_local_start.isoformat(),
                "proposed_corrected_start_utc": proposed_utc_start.isoformat(),
                "proposed_corrected_local_start": proposed_display_start.isoformat(),
                "local_date_changes": current_local_start.date().isoformat()
                != proposed_display_start.date().isoformat(),
                "report_implication": "May change future report boundaries and history labels for this mission if corrected.",
            }

            if mission.shift_end:
                end_utc_value = mission.shift_end.astimezone(datetime_timezone.utc)
                current_local_end = end_utc_value.astimezone(tz)
                proposed_local_end = end_utc_value.replace(tzinfo=None).replace(
                    tzinfo=tz
                )
                proposed_utc_end = proposed_local_end.astimezone(datetime_timezone.utc)
                proposed_display_end = proposed_utc_end.astimezone(tz)
                row.update(
                    {
                        "stored_end_utc": end_utc_value.isoformat(),
                        "current_local_end": current_local_end.isoformat(),
                        "proposed_corrected_end_utc": proposed_utc_end.isoformat(),
                        "proposed_corrected_local_end": proposed_display_end.isoformat(),
                    }
                )

            rows.append(row)

        output = {
            "read_only": True,
            "count": len(rows),
            "filters": {
                "user_id": user_id,
                "start_utc": options.get("start_utc"),
                "end_utc": options.get("end_utc"),
                "limit": options["limit"],
            },
            "rows": rows,
        }
        self.stdout.write(json.dumps(output, indent=2))
