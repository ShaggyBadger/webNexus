from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from datetime import datetime
from decimal import Decimal
from enum import Enum
from missionlog.models import Mission, LoadDelivery, TruckFuelLog


class EventType(Enum):
    SHIFT_START = "SHIFT_START"
    SHIFT_END = "SHIFT_END"
    DELIVERY = "DELIVERY"
    FUEL_PURCHASE = "FUEL_PURCHASE"


@dataclass(frozen=True)
class TimelineEvent:
    """Represents a discrete moment in time during a mission."""
    event_type: EventType
    timestamp: datetime
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Delivery:
    """Canonical domain model for a single fuel delivery."""
    id: int
    store_number: Optional[str]
    fuel_type: str
    gross_gal: Optional[int]
    net_gal: Optional[int]
    temp: Optional[float]
    start_gallons: Optional[float]
    end_gallons: Optional[float]
    price_at_store: Optional[Decimal]


@dataclass(frozen=True)
class TruckFuel:
    """Canonical domain model for truck fuel purchase."""
    id: int
    gallons: Decimal
    price_per_gallon: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Shift:
    """Canonical domain model for a single operational mission/shift."""
    id: int
    user_email: str
    start_time: datetime
    end_time: Optional[datetime]
    start_miles: Optional[int]
    end_miles: Optional[int]
    is_completed: bool
    deliveries: List[Delivery] = field(default_factory=list)
    truck_fuel_logs: List[TruckFuel] = field(default_factory=list)
    events: List[TimelineEvent] = field(default_factory=list)

    @property
    def duration_hours(self) -> Optional[float]:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return None

    @property
    def total_miles(self) -> int:
        if self.end_miles is not None and self.start_miles is not None:
            return self.end_miles - self.start_miles
        return 0


class ReportContext:
    """
    Normalizes Django ORM models into stable Domain Models.
    This layer isolates reporting logic from database schema changes.
    """

    def __init__(self, mission: Mission):
        self.mission = mission
        self.shift = self._normalize_mission(mission)

    def _normalize_mission(self, mission: Mission) -> Shift:
        deliveries = []
        
        # Flatten the hierarchy: Mission -> Order -> PO -> LoadDelivery
        for order in mission.order_numbers.all():
            for po in order.purchase_orders.all():
                for load in po.loads.all():
                    deliveries.append(self._normalize_delivery(load))

        truck_fuel = [self._normalize_truck_fuel(log) for log in mission.fuel_logs.all()]

        return Shift(
            id=mission.id,
            user_email=mission.user.email,
            start_time=mission.shift_start,
            end_time=mission.shift_end,
            start_miles=mission.start_miles,
            end_miles=mission.end_miles,
            is_completed=mission.is_completed,
            deliveries=deliveries,
            truck_fuel_logs=truck_fuel
        )

    def _normalize_delivery(self, load: LoadDelivery) -> Delivery:
        return Delivery(
            id=load.id,
            store_number=str(load.store.store_num) if load.store and load.store.store_num else None,
            fuel_type=load.fuel_type.name,
            gross_gal=load.gross_gal,
            net_gal=load.net_gal,
            temp=load.temp,
            start_gallons=load.start_gallons,
            end_gallons=load.end_gallons,
            price_at_store=load.price_at_store
        )

    def _normalize_truck_fuel(self, log: TruckFuelLog) -> TruckFuel:
        return TruckFuel(
            id=log.id,
            gallons=log.gallons,
            price_per_gallon=log.price_per_gallon,
            timestamp=log.timestamp
        )
