import math
import logging
from tankgauge.models import Store, StoreTankMapping, TankChart, TankEstimation
from .geometry import GeometryEngine
from .estimation_service import EstimationService, MIN_HEIGHT_SPREAD, MIN_READINGS

# Tactical Logger
logger = logging.getLogger("tankgauge")

# Constants for Operating Modes
MODE_OFFICIAL = "OFFICIAL"
MODE_MATHEMATICAL = "MATHEMATICAL"
MODE_UNAVAILABLE = "UNAVAILABLE"


def perform_tank_calc(
    tank_mapping, current_inches, delivery_gallons, virtual_meta=None
):
    """
    OPERATIONAL FLOW:
    Executes the core volume estimation for a single tank.
    Translates physical depth into gallons, factors in planned delivery,
    and validates against safety limits (90% capacity).

    Priority:
    1. Official Tank Chart
    2. Experimental Estimation (Persisted)
    3. On-the-fly Estimation (Virtual)
    4. Unavailable

    Returns a dictionary of tactical results including source metadata.
    """
    if tank_mapping:
        tank_type = tank_mapping.tank_type
        fuel_type = tank_mapping.fuel_type
        logger.info(
            f"CALC_START: TankMapping {tank_mapping.id} ({fuel_type}) @ {current_inches} in + {delivery_gallons}G delivery"
        )
        mode, source_meta = determine_operating_mode(tank_mapping)
    else:
        # TACTICAL_VIRTUAL_PATH: No explicit mapping exists, use virtual_meta
        fuel_type = virtual_meta.get("fuel_type")
        store_id = virtual_meta.get("store_id")
        tank_index = virtual_meta.get("tank_index")
        logger.info(
            f"CALC_START_VIRTUAL: Store {store_id} Tank {tank_index} ({fuel_type})"
        )
        mode, source_meta = determine_virtual_operating_mode(
            store_id, fuel_type, tank_index
        )

    if mode == MODE_UNAVAILABLE:
        unavailable_msg = (
            "No tank chart or sufficient Veeder data exists for this tank."
        )
        if source_meta and source_meta.get("message"):
            unavailable_msg = source_meta["message"]
        return {
            "status": "UNAVAILABLE",
            "message": unavailable_msg,
            "mode": mode,
        }

    initial_gallons, _ = get_volume_from_depth(
        tank_mapping, current_inches, mode, source_meta
    )
    final_gallons = initial_gallons + delivery_gallons
    final_inches = get_depth_from_volume(tank_mapping, final_gallons, mode, source_meta)

    # CAPACITY_RESOLUTION:
    # Use TankType if available, otherwise source from estimate diagnostics or latest reading
    capacity = 0
    if tank_mapping and tank_mapping.tank_type:
        capacity = tank_mapping.tank_type.capacity or 0
    elif source_meta and "capacity" in source_meta:
        capacity = source_meta["capacity"]

    ninety_percent_limit = capacity * 0.9
    avail_90 = max(0, ninety_percent_limit - initial_gallons)

    max_depth = 0.0
    if mode == MODE_MATHEMATICAL and source_meta and source_meta.get("estimation"):
        max_depth = float(source_meta["estimation"].radius) * 2.0
    elif tank_mapping and tank_mapping.tank_type:
        max_depth = float(tank_mapping.tank_type.max_depth or 0)

    # NO_FIT_WARNING: Triggered if the final volume exceeds the 90% safety threshold.
    no_fit_warning = final_gallons > ninety_percent_limit

    result = {
        "status": "SUCCESS",
        "fuel_type": fuel_type,
        "mode": mode,
        "data_source": source_meta.get("name") if source_meta else "CHART",
        "confidence": source_meta.get("confidence") if source_meta else 1.0,
        "initial_inches": current_inches,
        "initial_gallons": int(initial_gallons),
        "delivery_gallons": int(delivery_gallons),
        "avail_90": int(avail_90),
        "final_gallons": int(final_gallons),
        "final_inches": final_inches,
        "max_capacity": int(capacity),
        "max_depth": round(max_depth, 2),
        "ninety_limit": int(ninety_percent_limit),
        "no_fit_warning": no_fit_warning,
    }

    logger.info(
        f"CALC_COMPLETE: Mode {mode} | Initial {int(initial_gallons)}G -> Final {int(final_gallons)}G"
    )
    return result


def determine_operating_mode(tank_mapping, force_source=None):
    """
    Identifies the best available data source for an EXPLICIT tank mapping.
    """
    # 1. Check for Generated Tank Chart (Highest Priority: ALWAYS default here if exists)
    if TankChart.objects.filter(
        store=tank_mapping.store, tank_index=tank_mapping.tank_index, is_official=False
    ).exists():
        return MODE_OFFICIAL, {
            "name": "GENERATED_CHART",
            "confidence": 1.0,
            "store": tank_mapping.store,
            "tank_index": tank_mapping.tank_index,
        }

    # 2. Check for Official Tank Chart
    if TankChart.objects.filter(
        tank_type=tank_mapping.tank_type, is_official=True
    ).exists():
        return MODE_OFFICIAL, {"name": "OFFICIAL_CHART", "confidence": 1.0}

    # 3. Check for Active Experimental Estimation
    estimation = TankEstimation.objects.filter(
        tank_mapping=tank_mapping, is_active=True
    ).first()
    if estimation:
        return MODE_MATHEMATICAL, {
            "name": "MATHEMATICAL_ESTIMATE",
            "confidence": estimation.confidence,
            "estimation": estimation,
            "capacity": tank_mapping.tank_type.capacity or 0,
        }

    # 4. Try to trigger an on-the-fly estimation if enough data exists
    service = EstimationService()
    estimation = service.run_estimation_for_tank(tank_mapping)
    if estimation:
        return MODE_MATHEMATICAL, {
            "name": "MATHEMATICAL_ESTIMATE",
            "confidence": estimation.confidence,
            "estimation": estimation,
            "capacity": tank_mapping.tank_type.capacity or 0,
        }

    return MODE_UNAVAILABLE, None


def determine_virtual_operating_mode(store_id, fuel_type, tank_index, force_source=None):
    """
    TACTICAL_INTEL: Reconstructs an estimation on-the-fly for unmapped tanks.
    Used when Veeder readings exist but no StoreTankMapping is defined.
    """
    from atg.models import VeederReading

    # 1. Find Readings
    readings = VeederReading.objects.filter(
        ticket__store_id=store_id,
        tank_index=tank_index,
        fuel_type__name__iexact=fuel_type,
    )

    if not readings.exists():
        return MODE_UNAVAILABLE, {
            "message": "No Veeder readings found for this tank/fuel combination.",
        }

    # 2. Check for existing generated chart (Priority)
    latest = readings.order_by("-ticket__uploaded_at").first()
    store = latest.ticket.store
    
    if TankChart.objects.filter(
        store=store, tank_index=tank_index, is_official=False
    ).exists():
        return MODE_OFFICIAL, {
            "name": "GENERATED_CHART",
            "confidence": 1.0,
            "store": store,
            "tank_index": tank_index,
        }
        
    # 3. Resolve/recompute persisted estimate from current evidence
    observations = [(float(r.height), float(r.volume)) for r in readings]
    count = len(observations)
    spread = max(o[0] for o in observations) - min(o[0] for o in observations)

    if count < MIN_READINGS:
        return MODE_UNAVAILABLE, {
            "message": f"Insufficient Veeder data for Mathematical Mode: {count} reading(s) found, {MIN_READINGS} required.",
        }

    if spread < MIN_HEIGHT_SPREAD:
        return MODE_UNAVAILABLE, {
            "message": f"Insufficient height spread for Mathematical Mode: {spread:.2f}in found, {MIN_HEIGHT_SPREAD:.2f}in required.",
        }

    total_capacity = float(latest.volume + latest.ullage)

    service = EstimationService()
    # Attempt to persist/get latest valid estimation
    estimation = service.run_virtual_estimation(
        store,
        fuel_type,
        tank_index,
        total_capacity,
        observations,
        latest_uploaded_at=latest.ticket.uploaded_at,
    )

    if estimation:
        return MODE_MATHEMATICAL, {
            "name": "MATHEMATICAL_ESTIMATE",
            "confidence": estimation.confidence,
            "estimation": estimation,
            "capacity": total_capacity,
        }

    return MODE_UNAVAILABLE, {
        "message": "Mathematical estimation failed for available Veeder data.",
    }


def get_volume_from_depth(tank_mapping, depth, mode, source_meta):
    """
    Translates depth to volume using the designated mode.
    """
    if depth <= 0:
        return 0.0, mode

    if mode == MODE_OFFICIAL:
        # Resolve store/index context from source_meta or mapping
        store = source_meta.get("store") or (tank_mapping.store if tank_mapping else None)
        tank_index = source_meta.get("tank_index") or (
            tank_mapping.tank_index if tank_mapping else None
        )
        tank_type = tank_mapping.tank_type if tank_mapping else None

        return (
            _get_volume_from_chart(
                tank_type, depth, store=store, tank_index=tank_index
            ),
            mode,
        )

    if mode == MODE_MATHEMATICAL:
        estimation = source_meta.get("estimation")
        engine = GeometryEngine()
        volume = engine.volume_from_depth(estimation.radius, estimation.length, depth)
        return float(volume), mode

    return 0.0, mode


def get_depth_from_volume(tank_mapping, target_gallons, mode, source_meta):
    """
    Translates volume to depth using the designated mode.
    """
    if target_gallons <= 0:
        return 0.0

    if mode == MODE_OFFICIAL:
        # Resolve store/index context from source_meta or mapping
        store = source_meta.get("store") or (tank_mapping.store if tank_mapping else None)
        tank_index = source_meta.get("tank_index") or (
            tank_mapping.tank_index if tank_mapping else None
        )
        tank_type = tank_mapping.tank_type if tank_mapping else None

        return _get_depth_from_chart(
            tank_type, target_gallons, store=store, tank_index=tank_index
        )

    if mode == MODE_MATHEMATICAL:
        estimation = source_meta.get("estimation")
        engine = GeometryEngine()
        depth = engine.depth_from_volume(
            estimation.radius, estimation.length, target_gallons
        )
        return float(depth)

    return 0.0


def _get_volume_from_chart(tank_type, depth, store=None, tank_index=None):
    """Internal: Original chart-based volume lookup."""

    # Resolve Chart Base Query: Prioritize generated chart if store/index provided
    chart_qs = TankChart.objects.none()
    if store and tank_index:
        chart_qs = TankChart.objects.filter(
            store=store, tank_index=tank_index, is_official=False
        )

    if not chart_qs.exists() and tank_type:
        chart_qs = TankChart.objects.filter(tank_type=tank_type, is_official=True)

    if not chart_qs.exists():
        return 0.0

    # BOUNDARY_CHECK: Handle depth exceeding chart limits
    max_entry = chart_qs.order_by("-inches").first()
    if max_entry and depth >= max_entry.inches:
        return float(max_entry.gallons)

    # OPTIMIZATION: Check for exact integer depth match
    if depth == int(depth):
        chart_entry = chart_qs.filter(inches=int(depth)).first()
        if chart_entry:
            return float(chart_entry.gallons)

    # INTERPOLATION_LOGIC: Find bounding inches
    lower_inch = math.floor(depth)
    upper_inch = math.ceil(depth)

    # Fetch bounding charts for linear interpolation
    charts = chart_qs.filter(inches__in=[lower_inch, upper_inch]).order_by("inches")

    if charts.count() == 2:
        c1, c2 = charts[0], charts[1]
        volume = c1.gallons + (depth - c1.inches) * (c2.gallons - c1.gallons)
        return float(volume)
    elif charts.count() == 1:
        return float(charts[0].gallons)

    return 0.0


def _get_depth_from_chart(tank_type, target_gallons, store=None, tank_index=None):
    """Internal: Original chart-based depth lookup."""

    # Resolve Chart Base Query: Prioritize generated chart if store/index provided
    chart_qs = TankChart.objects.none()
    if store and tank_index:
        chart_qs = TankChart.objects.filter(
            store=store, tank_index=tank_index, is_official=False
        )

    if not chart_qs.exists() and tank_type:
        chart_qs = TankChart.objects.filter(tank_type=tank_type, is_official=True)

    if not chart_qs.exists():
        return 0.0

    # BOUNDARY_CHECK: Handle target exceeding chart capacity
    max_entry = chart_qs.order_by("-gallons").first()
    if max_entry and target_gallons >= max_entry.gallons:
        return float(max_entry.inches)

    # BRACKETING: Find entries that bracket the target gallons
    lower_entry = (
        chart_qs.filter(gallons__lte=target_gallons).order_by("-gallons").first()
    )
    upper_entry = (
        chart_qs.filter(gallons__gte=target_gallons).order_by("gallons").first()
    )

    if not lower_entry:
        return 0.0

    if upper_entry:
        if lower_entry == upper_entry or lower_entry.gallons == upper_entry.gallons:
            return float(lower_entry.inches)

        # INTERPOLATION: Solve for depth (inches)
        x1, y1 = lower_entry.inches, lower_entry.gallons
        x2, y2 = upper_entry.inches, upper_entry.gallons

        depth = x1 + (target_gallons - y1) * (x2 - x1) / (y2 - y1)
        return round(float(depth), 2)

    return float(lower_entry.inches)
