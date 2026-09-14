"""Immutable data contracts for the generic chart pipeline."""

from dataclasses import dataclass

from .scope import package_scope_key
from .states import canonical_state


@dataclass(frozen=True)
class SelectionSpec:
    """Describe which stores are eligible for one package generation."""

    state: str | None = None
    store_numbers: tuple[int, ...] = ()
    store_type_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        normalized_state = canonical_state(self.state)
        if normalized_state.upper() == "FULL" or not normalized_state:
            normalized_state = None
        object.__setattr__(self, "state", normalized_state)
        object.__setattr__(
            self,
            "store_numbers",
            tuple(sorted({int(number) for number in self.store_numbers})),
        )
        object.__setattr__(
            self,
            "store_type_ids",
            tuple(sorted({int(type_id) for type_id in self.store_type_ids})),
        )

    @property
    def is_full(self) -> bool:
        """Return whether the specification includes every state."""

        return self.state is None

    @property
    def package_scope_key(self) -> str:
        """Return the stable key used to isolate package history and files."""

        return package_scope_key(self.state, self.store_numbers, self.store_type_ids)


@dataclass(frozen=True)
class SelectedTank:
    """A normalized current tank assignment for a selected store."""

    mapping_id: int
    tank_index: int | None
    fuel_type: str
    tank_type_id: int | None
    tank_type_name: str
    capacity_gallons: int | None
    max_depth_inches: int | None


@dataclass(frozen=True)
class SelectedStore:
    """A normalized store and its mapped tank assignments."""

    store_id: int
    store_number: int | None
    riso_number: int | None
    store_name: str
    state: str
    store_type: str
    city: str
    tanks: tuple[SelectedTank, ...]


@dataclass(frozen=True)
class CurvePoint:
    """One depth and volume point in a generated curve."""

    depth_inches: int
    volume_gallons: float


@dataclass(frozen=True)
class GeneratedTank:
    """A deduplicated tank geometry candidate with its analytic curve."""

    store_id: int
    store_number: int | None
    tank_index: int | None
    fuel_type: str
    tank_type_id: int | None
    tank_type_name: str
    radius_inches: float
    length_inches: float
    max_depth_inches: int
    confidence: float
    sample_count: int
    source: str
    algorithm_version: str
    curve: tuple[CurvePoint, ...]


@dataclass(frozen=True)
class OfficialChartPoint:
    """One persisted official chart row."""

    tank_type_id: int | None
    tank_type_name: str
    store_id: int | None
    store_number: int | None
    tank_index: int | None
    depth_inches: int
    volume_gallons: int
    tank_name: str
