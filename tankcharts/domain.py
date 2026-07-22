from dataclasses import dataclass
from datetime import datetime


@dataclass
class TankFieldChart:
    """Portable tank field chart payload used by rendering and storage layers."""

    store_num: int
    store_name: str
    address: str
    city: str
    state: str

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
    generated_at: datetime
