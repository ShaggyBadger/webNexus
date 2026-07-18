from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CalculationMode(str, Enum):
    """Supported tank calculation display modes."""

    AUTO = "AUTO"
    OFFICIAL = "OFFICIAL"
    MATHEMATICAL = "MATHEMATICAL"


class ConfidenceLevel(str, Enum):
    """Discrete confidence levels used across API and UI layers."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


@dataclass(frozen=True)
class ModeAvailability:
    """Availability status for one calculation mode."""

    mode: CalculationMode
    available: bool
    reason: Optional[str]
    confidence: ConfidenceLevel

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "available": self.available,
            "reason": self.reason,
            "confidence": self.confidence.value,
        }


@dataclass(frozen=True)
class TankLimits:
    """Authoritative capacity/depth limit values for one selected mode."""

    capacity_gallons: Optional[int]
    max_depth_inches: Optional[float]
    ninety_percent_gallons: Optional[int]
    source: str
    confidence: ConfidenceLevel
    mode: CalculationMode
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "capacity_gallons": self.capacity_gallons,
            "max_depth_inches": self.max_depth_inches,
            "ninety_percent_gallons": self.ninety_percent_gallons,
            "source": self.source,
            "confidence": self.confidence.value,
            "mode": self.mode.value,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CalculationProfile:
    """Result payload for one concrete calculation mode."""

    mode: CalculationMode
    capacity: TankLimits
    initial_gallons: int
    initial_inches: float
    delivery_gallons: int
    final_gallons: int
    final_inches: float
    fillable_to_90: int
    ninety_limit: int
    no_fit_warning: bool
    confidence: ConfidenceLevel
    data_source: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "capacity": self.capacity.to_dict(),
            "initial_gallons": self.initial_gallons,
            "initial_inches": self.initial_inches,
            "delivery_gallons": self.delivery_gallons,
            "final_gallons": self.final_gallons,
            "final_inches": self.final_inches,
            "fillable_to_90": self.fillable_to_90,
            "ninety_limit": self.ninety_limit,
            "no_fit_warning": self.no_fit_warning,
            "confidence": self.confidence.value,
            "data_source": self.data_source,
            "warnings": list(self.warnings),
        }
