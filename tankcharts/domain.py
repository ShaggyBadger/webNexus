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

    curves: list[dict]
    veeder_points: list[dict]

    official_row_count: int
    estimation_id: int | None
    estimation_radius_inches: float | None
    estimation_length_inches: float | None
    generated_at: datetime
