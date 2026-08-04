import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.utils import timezone

from missionlog.models import LoadDelivery, Mission

_MIN_VALID_HOURS = Decimal("0.25")


@dataclass
class PeriodBounds:
    report_range: str
    period_start_local: datetime
    period_end_local: datetime
    previous_start_local: datetime
    previous_end_local: datetime
    period_label: str


class ProductionReportService:
    """
    Commander's Intent:
    Produces deterministic production metrics so operators can track true
    gallons-per-hour performance over a defined period without guesswork.
    """

    @staticmethod
    def resolve_user_timezone(user: AbstractBaseUser) -> ZoneInfo:
        profile_timezone = None
        try:
            profile = user.profile
            profile_timezone = getattr(profile, "timezone", None)
        except ObjectDoesNotExist:
            profile_timezone = None

        timezone_name = profile_timezone or settings.TIME_ZONE
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            return ZoneInfo(settings.TIME_ZONE)

    @staticmethod
    def resolve_period_bounds(
        *, report_range: str, now_utc: datetime, tz: ZoneInfo
    ) -> PeriodBounds:
        now_local = timezone.localtime(now_utc, tz)

        if report_range == "week":
            current_week_start = (
                now_local - timedelta(days=now_local.weekday())
            ).date()
            start_date = current_week_start
            end_date = current_week_start + timedelta(days=6)
            previous_start = start_date - timedelta(days=7)
            previous_end = start_date - timedelta(days=1)
        elif report_range == "month":
            first_of_current_month = now_local.date().replace(day=1)
            if first_of_current_month.month == 12:
                next_month_start = date(first_of_current_month.year + 1, 1, 1)
            else:
                next_month_start = date(
                    first_of_current_month.year,
                    first_of_current_month.month + 1,
                    1,
                )
            start_date = first_of_current_month
            end_date = next_month_start - timedelta(days=1)
            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end.replace(day=1)
        elif report_range == "quarter":
            quarter_start_month = ((now_local.month - 1) // 3) * 3 + 1
            current_quarter_start = date(now_local.year, quarter_start_month, 1)
            if quarter_start_month == 10:
                next_quarter_start = date(now_local.year + 1, 1, 1)
            else:
                next_quarter_start = date(now_local.year, quarter_start_month + 3, 1)
            start_date = current_quarter_start
            end_date = next_quarter_start - timedelta(days=1)
            previous_end = start_date - timedelta(days=1)
            previous_start_month = quarter_start_month - 3
            previous_start_year = now_local.year
            if previous_start_month <= 0:
                previous_start_month += 12
                previous_start_year -= 1
            previous_start = date(previous_start_year, previous_start_month, 1)
        elif report_range == "year":
            start_date = date(now_local.year, 1, 1)
            end_date = date(now_local.year, 12, 31)
            previous_start = date(now_local.year - 1, 1, 1)
            previous_end = date(now_local.year - 1, 12, 31)
        else:
            raise ValueError("Unsupported report range.")

        start_local = datetime.combine(start_date, time.min, tzinfo=tz)
        end_local = datetime.combine(end_date, time.max, tzinfo=tz)
        previous_start_local = datetime.combine(previous_start, time.min, tzinfo=tz)
        previous_end_local = datetime.combine(previous_end, time.max, tzinfo=tz)

        period_label = ProductionReportService._period_label(
            start_date, end_date, report_range
        )
        return PeriodBounds(
            report_range=report_range,
            period_start_local=start_local,
            period_end_local=end_local,
            previous_start_local=previous_start_local,
            previous_end_local=previous_end_local,
            period_label=period_label,
        )

    @staticmethod
    def build_report(
        *, user: AbstractBaseUser, report_range: str, now_utc: datetime | None = None
    ) -> dict:
        now_utc = now_utc or timezone.now()
        user_tz = ProductionReportService.resolve_user_timezone(user)
        bounds = ProductionReportService.resolve_period_bounds(
            report_range=report_range,
            now_utc=now_utc,
            tz=user_tz,
        )

        missions = ProductionReportService._fetch_missions(
            user=user,
            start_local=bounds.period_start_local,
            end_local=bounds.period_end_local,
            tz=user_tz,
        )
        previous_missions = ProductionReportService._fetch_missions(
            user=user,
            start_local=bounds.previous_start_local,
            end_local=bounds.previous_end_local,
            tz=user_tz,
        )

        current_metrics = ProductionReportService._aggregate_metrics(
            missions=missions,
            report_range=report_range,
            tz=user_tz,
        )
        previous_metrics = ProductionReportService._aggregate_metrics(
            missions=previous_missions,
            report_range=report_range,
            tz=user_tz,
        )

        comparison_text = ProductionReportService._comparison_text(
            current_overall_gph=current_metrics["overall_gph"],
            previous_overall_gph=previous_metrics["overall_gph"],
        )

        chart_png_bytes = ProductionReportService._render_gph_chart(
            report_range=report_range,
            period_label=bounds.period_label,
            bucket_rows=current_metrics["bucket_rows"],
            overall_gph=current_metrics["overall_gph"],
        )

        return {
            "period": {
                "range": report_range,
                "start_date": bounds.period_start_local.date(),
                "end_date": bounds.period_end_local.date(),
                "label": bounds.period_label,
            },
            "summary": current_metrics,
            "comparison_text": comparison_text,
            "chart_png_bytes": chart_png_bytes,
        }

    @staticmethod
    def _fetch_missions(
        *,
        user: AbstractBaseUser,
        start_local: datetime,
        end_local: datetime,
        tz: ZoneInfo,
    ) -> list[Mission]:
        start_utc = start_local.astimezone(datetime_timezone.utc)
        end_utc = end_local.astimezone(datetime_timezone.utc)

        queryset = (
            Mission.objects.filter(
                user=user, is_completed=True, shift_start__range=(start_utc, end_utc)
            )
            .prefetch_related(
                Prefetch(
                    "order_numbers__purchase_orders__loads",
                    queryset=LoadDelivery.objects.only(
                        "id",
                        "purchase_order_id",
                        "gross_gal",
                    ),
                )
            )
            .only(
                "id",
                "shift_start",
                "shift_end",
                "hours_on_duty",
                "total_gallons",
                "is_completed",
            )
        )
        return list(queryset)

    @staticmethod
    def _aggregate_metrics(
        *, missions: list[Mission], report_range: str, tz: ZoneInfo
    ) -> dict:
        bucket_map = {}
        included_count = 0
        excluded_count = 0
        excluded_reason_counts = {}
        total_gallons = Decimal("0")
        total_hours = Decimal("0")

        for mission in missions:
            gallons = ProductionReportService._resolve_mission_gallons(mission)
            valid_hours, invalid_reason = ProductionReportService._resolve_valid_hours(
                mission
            )

            if gallons <= 0:
                excluded_count += 1
                excluded_reason_counts["N/A - non-positive gallons"] = (
                    excluded_reason_counts.get("N/A - non-positive gallons", 0) + 1
                )
                continue

            if valid_hours is None:
                excluded_count += 1
                excluded_reason_counts[invalid_reason] = (
                    excluded_reason_counts.get(invalid_reason, 0) + 1
                )
                continue

            included_count += 1
            total_gallons += gallons
            total_hours += valid_hours

            bucket_label, bucket_sort = ProductionReportService._bucket_for_mission(
                mission=mission,
                report_range=report_range,
                tz=tz,
            )
            bucket_entry = bucket_map.setdefault(
                bucket_label,
                {
                    "bucket_label": bucket_label,
                    "bucket_sort": bucket_sort,
                    "gallons": Decimal("0"),
                    "hours": Decimal("0"),
                },
            )
            bucket_entry["gallons"] += gallons
            bucket_entry["hours"] += valid_hours

        overall_gph = None
        if total_hours > 0:
            overall_gph = float((total_gallons / total_hours).quantize(Decimal("0.1")))

        bucket_rows = []
        for bucket in sorted(bucket_map.values(), key=lambda item: item["bucket_sort"]):
            bucket_hours = bucket["hours"]
            bucket_gph = None
            if bucket_hours > 0:
                bucket_gph = float(
                    (bucket["gallons"] / bucket_hours).quantize(Decimal("0.1"))
                )
            bucket_rows.append(
                {
                    "bucket_label": bucket["bucket_label"],
                    "bucket_sort": bucket["bucket_sort"],
                    "gallons": float(bucket["gallons"]),
                    "hours": float(bucket_hours),
                    "gph": bucket_gph,
                }
            )

        best_bucket = None
        lowest_bucket = None
        valid_bucket_rows = [row for row in bucket_rows if row["gph"] is not None]
        if valid_bucket_rows:
            best_bucket = max(valid_bucket_rows, key=lambda row: row["gph"])
            lowest_bucket = min(valid_bucket_rows, key=lambda row: row["gph"])

        return {
            "total_gallons": float(total_gallons),
            "total_hours": float(total_hours),
            "overall_gph": overall_gph,
            "included_count": included_count,
            "excluded_count": excluded_count,
            "excluded_reason_counts": excluded_reason_counts,
            "bucket_rows": bucket_rows,
            "best_bucket": best_bucket,
            "lowest_bucket": lowest_bucket,
        }

    @staticmethod
    def _resolve_mission_gallons(mission: Mission) -> Decimal:
        if mission.total_gallons is not None:
            return Decimal(str(mission.total_gallons))

        gross_sum = Decimal("0")
        for order in mission.order_numbers.all():
            for purchase_order in order.purchase_orders.all():
                for load in purchase_order.loads.all():
                    if load.gross_gal is not None:
                        gross_sum += Decimal(str(load.gross_gal))
        return gross_sum

    @staticmethod
    def _resolve_valid_hours(mission: Mission) -> tuple[Decimal | None, str]:
        if mission.hours_on_duty_not_driving is not None:
            try:
                hours = Decimal(str(mission.hours_on_duty_not_driving))
            except Exception:
                return None, "N/A - invalid or insufficient on-duty-not-driving hours"
            if hours < _MIN_VALID_HOURS:
                return None, "N/A - invalid or insufficient on-duty-not-driving hours"
            return hours, ""

        return None, "N/A - invalid or insufficient on-duty-not-driving hours"

    @staticmethod
    def _bucket_for_mission(
        *, mission: Mission, report_range: str, tz: ZoneInfo
    ) -> tuple[str, date]:
        base_timestamp = mission.shift_end or mission.shift_start
        localized = timezone.localtime(base_timestamp, tz)
        localized_date = localized.date()

        if report_range in {"week", "month"}:
            return localized_date.strftime("%b %-d"), localized_date
        if report_range == "quarter":
            week_start = localized_date - timedelta(days=localized_date.weekday())
            return f"Week of {week_start.strftime('%b %-d')}", week_start
        month_anchor = date(localized_date.year, localized_date.month, 1)
        return month_anchor.strftime("%b %Y"), month_anchor

    @staticmethod
    def _comparison_text(
        *, current_overall_gph: float | None, previous_overall_gph: float | None
    ) -> str:
        if current_overall_gph is None or previous_overall_gph is None:
            return "Comparison unavailable"
        if previous_overall_gph == 0 and current_overall_gph > 0:
            return "Increased from zero production"
        if previous_overall_gph == 0 and current_overall_gph == 0:
            return "No production in either period"

        delta_percent = (
            (current_overall_gph - previous_overall_gph) / previous_overall_gph
        ) * 100
        rounded_delta = round(abs(delta_percent), 1)
        if delta_percent > 0:
            return f"{rounded_delta}% higher than the previous equivalent period"
        if delta_percent < 0:
            return f"{rounded_delta}% lower than the previous equivalent period"
        return "No change from the previous equivalent period"

    @staticmethod
    def _period_label(start_date: date, end_date: date, report_range: str) -> str:
        if report_range == "week":
            return f"Week of {start_date.strftime('%b %-d, %Y')}"
        if report_range == "month":
            return start_date.strftime("%B %Y")
        if report_range == "quarter":
            quarter = ((start_date.month - 1) // 3) + 1
            return f"Q{quarter} {start_date.year}"
        return str(start_date.year)

    @staticmethod
    def _render_gph_chart(
        *,
        report_range: str,
        period_label: str,
        bucket_rows: list[dict],
        overall_gph: float | None,
    ) -> bytes:
        ordered_rows = sorted(bucket_rows, key=lambda row: row["bucket_sort"])
        labels = [row["bucket_label"] for row in ordered_rows]
        gph_values = [row["gph"] for row in ordered_rows]
        x_indexes = list(range(len(labels)))

        figure, axis = plt.subplots(figsize=(12, 4), dpi=100)
        figure.patch.set_facecolor("white")
        axis.set_facecolor("white")

        axis.plot(
            x_indexes,
            gph_values,
            color="#3b82f6",
            marker="o",
            linewidth=2.0,
            markersize=4,
        )
        axis.axhline(
            float(getattr(settings, "MISSIONLOG_PRODUCTION_GPH_TARGET", 5000)),
            color="#d4943a",
            linestyle="--",
            linewidth=1.5,
            alpha=0.9,
        )

        axis.set_title(f"Gallons Per Hour - {period_label}", fontsize=12)
        axis.set_ylabel("Gallons per Hour (GPH)", fontsize=10)
        axis.set_ylim(bottom=0)
        axis.set_xticks(x_indexes)
        axis.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        axis.grid(True, axis="y", color="#cccccc", alpha=0.6)

        image_buffer = io.BytesIO()
        figure.tight_layout()
        figure.savefig(image_buffer, format="png")
        plt.close(figure)
        image_buffer.seek(0)
        return image_buffer.read()
