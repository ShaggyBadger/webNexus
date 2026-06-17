from abc import ABC, abstractmethod
from typing import Dict, List, Any
from .context import ReportContext


class BaseSection(ABC):
    """
    A single unit of intelligence within a report.
    Returns a stable, serializable dictionary contract.
    """

    def __init__(self, context: ReportContext):
        self.context = context

    @abstractmethod
    def generate(self) -> Dict[str, Any]:
        """Returns the section data payload."""
        pass


class BaseReport(ABC):
    """
    A collection of sections forming a complete intelligence package.
    """
    title: str = "Base Tactical Report"
    sections_classes: List[type] = []

    def __init__(self, context: ReportContext):
        self.context = context
        self.sections = [cls(context) for cls in self.sections_classes]

    def generate(self) -> Dict[str, Any]:
        """
        Aggregates all sections into a unified JSON-serializable package.
        """
        return {
            "metadata": {
                "title": self.title,
                "generated_at": str(self.context.mission.shift_start),  # Simplified
                "mission_id": self.context.shift.id,
            },
            "sections": {
                sec.__class__.__name__.lower(): sec.generate() for sec in self.sections
            }
        }
