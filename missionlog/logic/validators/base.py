from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from ..reports.context import ReportContext


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity
    affected_ids: List[int] = None


class BaseValidator(ABC):
    """
    Base class for all automated anomaly detectors.
    """

    def __init__(self, context: ReportContext):
        self.context = context

    @abstractmethod
    def validate(self) -> List[ValidationIssue]:
        """Returns a list of detected issues."""
        pass
