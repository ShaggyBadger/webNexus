from decimal import Decimal, InvalidOperation


class ProductionHoursValidationError(ValueError):
    """Raised when production hours/minutes cannot be normalized."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.field = field


def parse_production_hours(data: dict, *, required: bool) -> Decimal | None:
    """Normalize component or legacy decimal production hours."""
    hours_key = "hours_on_duty_not_driving_hours"
    minutes_key = "hours_on_duty_not_driving_minutes"
    has_components = hours_key in data or minutes_key in data

    if not has_components:
        raw_value = data.get("hours_on_duty_not_driving")
        if raw_value is None or str(raw_value).strip() == "":
            if required:
                raise ProductionHoursValidationError(
                    "Production time is required.", "hours_on_duty_not_driving"
                )
            return None
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ProductionHoursValidationError(
                "Production time must be a valid number.",
                "hours_on_duty_not_driving",
            ) from exc
        if value < 0:
            raise ProductionHoursValidationError(
                "Production hours cannot be negative.",
                "hours_on_duty_not_driving",
            )
        return value

    raw_hours = data.get(hours_key)
    raw_minutes = data.get(minutes_key)
    hours_blank = raw_hours is None or str(raw_hours).strip() == ""
    minutes_blank = raw_minutes is None or str(raw_minutes).strip() == ""

    if hours_blank and minutes_blank:
        if required:
            raise ProductionHoursValidationError(
                "Production time is required.", "hours_on_duty_not_driving"
            )
        return None

    hours = _parse_component(
        raw_hours if not hours_blank else 0, "Production hours", hours_key, 0
    )
    minutes = _parse_component(
        raw_minutes if not minutes_blank else 0,
        "Production minutes",
        minutes_key,
        0,
        59,
    )
    return Decimal(hours) + (Decimal(minutes) / Decimal("60"))


def _parse_component(
    raw_value,
    label: str,
    field: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProductionHoursValidationError(
            f"{label} must be a whole number.", field
        ) from exc

    if value != value.to_integral_value():
        raise ProductionHoursValidationError(f"{label} must be a whole number.", field)
    integer_value = int(value)
    if integer_value < minimum or (maximum is not None and integer_value > maximum):
        if maximum is None:
            message = f"{label} must be at least {minimum}."
        else:
            message = f"{label} must be between {minimum} and {maximum}."
        raise ProductionHoursValidationError(message, field)
    return integer_value
