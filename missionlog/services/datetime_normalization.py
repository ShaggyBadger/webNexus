from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


class MissionDateTimeValidationError(ValueError):
    """Raised when a MissionLog datetime payload cannot be normalized safely."""


def resolve_user_timezone(user: AbstractBaseUser) -> ZoneInfo:
    """Resolve the authoritative timezone for MissionLog datetime interpretation."""
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


def parse_user_datetime_to_utc(
    *,
    value: str,
    user: AbstractBaseUser,
    field_name: str,
) -> datetime:
    """
    Commander's Intent:
    Preserve the operator's intended wall-clock timestamp by localizing
    timezone-less values in the operator timezone before UTC persistence.
    """
    if value is None or str(value).strip() == "":
        raise MissionDateTimeValidationError(f"{field_name} is required.")

    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise MissionDateTimeValidationError(
            f"{field_name} must be a valid ISO datetime."
        ) from exc

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, resolve_user_timezone(user))

    return parsed.astimezone(datetime_timezone.utc)
