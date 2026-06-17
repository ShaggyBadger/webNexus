from typing import List
from ..reports.context import Shift, TimelineEvent, EventType


def generate_event_stream(shift: Shift) -> List[TimelineEvent]:
    """
    Synthesizes a chronological stream of events for the mission.
    Handles lack of timestamps for deliveries by sequential placement.
    """
    events = []

    # 1. SHIFT_START
    events.append(
        TimelineEvent(
            event_type=EventType.SHIFT_START,
            timestamp=shift.start_time,
            description="Mission Log Initiated",
        )
    )

    # 2. TRUCK_FUEL
    for log in shift.truck_fuel_logs:
        events.append(
            TimelineEvent(
                event_type=EventType.FUEL_PURCHASE,
                timestamp=log.timestamp,
                description=f"Truck Fuel: {log.gallons} gal",
                metadata={"log_id": log.id},
            )
        )

    # 3. DELIVERIES
    # Fallback: Since LoadDelivery currently lacks individual timestamps,
    # we place them sequentially after SHIFT_START but before SHIFT_END.
    # We assign them a 'virtual' timestamp slightly after SHIFT_START
    # to maintain sorting integrity.
    for i, delivery in enumerate(shift.deliveries):
        events.append(
            TimelineEvent(
                event_type=EventType.DELIVERY,
                timestamp=shift.start_time,  # Sort key fallback
                description=f"Delivery: {delivery.fuel_type} to Store {delivery.store_number or 'Unknown'}",
                metadata={"delivery_id": delivery.id, "sequence": i},
            )
        )

    # 4. SHIFT_END
    if shift.end_time:
        events.append(
            TimelineEvent(
                event_type=EventType.SHIFT_END,
                timestamp=shift.end_time,
                description="Mission Complete Protocol",
            )
        )

    # Stable sort by timestamp.
    # For events with identical timestamps (like fallback deliveries),
    # Python's stable sort preserves the original order of insertion.
    return sorted(events, key=lambda x: x.timestamp)
