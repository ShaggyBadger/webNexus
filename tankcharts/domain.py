from dataclasses import dataclass
from datetime import datetime


@dataclass
class TankFieldChart:
    """Portable tank field chart payload used by rendering and storage layers."""

    store_num: int
    riso_num: int | None
    store_name: str
    store_type: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float | None
    longitude: float | None

    tank_index: int
    fuel_type: str
    tank_type_name: str
    capacity_gallons: int
    max_depth_inches: int

    table_rows: list[dict]

    has_official_chart: bool
    official_chart_source: str | None
    coverage_percent: float
    veeder_observation_count: int
    estimation_sample_count: int
    is_low_confidence: bool

    curves: list[dict]
    veeder_points: list[dict]

    official_row_count: int
    estimation_id: int | None
    estimation_radius_inches: float | None
    estimation_length_inches: float | None
    generated_at: datetime


@dataclass
class StoreTankSummary:
    """Summary metadata for one tank on a store-wide chart."""

    tank_index: int | None
    fuel_type: str
    tank_type_name: str
    capacity_gallons: int
    max_depth_inches: int
    veeder_observation_count: int
    sample_count: int
    is_low_confidence: bool


@dataclass
class StoreTankOmission:
    """Summary metadata for mapped tanks omitted from Veeder-only store charts."""

    tank_index: int | None
    fuel_type: str
    reason_code: str
    veeder_observation_count: int


@dataclass
class StoreFieldChart:
    """Store-wide field chart payload for rendering/storage layers."""

    store_num: int
    riso_num: int | None
    store_name: str
    store_type: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float | None
    longitude: float | None

    tanks: list[StoreTankSummary]
    omitted_tanks: list[StoreTankOmission]
    combined_table_rows: list[dict]
    curves: list[dict]

    max_depth_inches_global: int
    total_veeder_observation_count: int
    generated_at: datetime
