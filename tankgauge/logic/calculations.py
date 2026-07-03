import math
import logging
from django.conf import settings
from tankgauge.models import Store, StoreTankMapping, TankChart, TankEstimation
from .geometry import GeometryEngine
from .estimation_service import EstimationService, MIN_HEIGHT_SPREAD, MIN_READINGS

# Tactical Logger
logger = logging.getLogger("tankgauge")

# Constants for Operating Modes
MODE_OFFICIAL = "OFFICIAL"
MODE_MATHEMATICAL = "MATHEMATICAL"
MODE_UNAVAILABLE = "UNAVAILABLE"


def _generated_chart_fallback_enabled():
    return getattr(settings, "TANKGAUGE_ENABLE_GENERATED_CHART_FALLBACK", False)


def _get_mode_priority():
    """
    Returns the active mode priority string: "OFFICIAL_FIRST" or "MATHEMATICAL_FIRST".

    Reads from the DB-backed TankGaugeConfig singleton so admins can flip the
    default at runtime. Falls back to settings.TANKGAUGE_DEFAULT_MODE_PRIORITY
    if the DB row doesn't exist yet (e.g. fresh install before first migration).
    """
    from tankgauge.models import TankGaugeConfig

    try:
        return TankGaugeConfig.get_solo().mode_priority
    except Exception:
        return getattr(settings, "TANKGAUGE_DEFAULT_MODE_PRIORITY", "OFFICIAL_FIRST")


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
            "CALC_START",
            extra={
                "tank_mapping_id": tank_mapping.id,
                "store_num": tank_mapping.store.store_num,
                "fuel_type": fuel_type,
                "current_inches": current_inches,
                "delivery_gallons": delivery_gallons,
                "reason_code": "mapped_tank",
            },
        )
        mode, source_meta = determine_operating_mode(tank_mapping)
    else:
        # TACTICAL_VIRTUAL_PATH: No explicit mapping exists, use virtual_meta
        fuel_type = virtual_meta.get("fuel_type")
        store_id = virtual_meta.get("store_id")
        tank_index = virtual_meta.get("tank_index")
        logger.info(
            "CALC_START_VIRTUAL",
            extra={
                "store_id": store_id,
                "tank_index": tank_index,
                "fuel_type": fuel_type,
                "current_inches": current_inches,
                "delivery_gallons": delivery_gallons,
                "reason_code": "virtual_tank",
            },
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
        logger.warning(
            "CALC_UNAVAILABLE",
            extra={
                "fuel_type": fuel_type,
                "reason_code": "mode_unavailable",
                "unavailable_message": unavailable_msg,
            },
        )
        return {
            "status": "UNAVAILABLE",
            "message": unavailable_msg,
            "mode": mode,
        }

    profiles = {}
    for candidate_mode in (MODE_OFFICIAL, MODE_MATHEMATICAL):
        profile = _calculate_profile_for_mode(
            tank_mapping=tank_mapping,
            current_inches=current_inches,
            delivery_gallons=delivery_gallons,
            virtual_meta=virtual_meta,
            mode=candidate_mode,
        )
        if profile:
            profiles[candidate_mode] = profile

    if not profiles:
        return {
            "status": "UNAVAILABLE",
            "message": "No tank chart or sufficient Veeder data exists for this tank.",
            "mode": MODE_UNAVAILABLE,
            "profiles": {},
        }

    preferred_mode = (
        MODE_MATHEMATICAL if MODE_MATHEMATICAL in profiles else MODE_OFFICIAL
    )
    selected = profiles[preferred_mode]

    result = {
        "status": "SUCCESS",
        "fuel_type": fuel_type,
        "mode": preferred_mode,
        "preferred_mode": preferred_mode,
        "available_modes": list(profiles.keys()),
        "profiles": {
            "official": profiles.get(MODE_OFFICIAL),
            "mathematical": profiles.get(MODE_MATHEMATICAL),
        },
        # Backward-compatible selected profile fields
        "data_source": selected["data_source"],
        "confidence": selected["confidence"],
        "initial_inches": selected["initial_inches"],
        "initial_gallons": selected["initial_gallons"],
        "delivery_gallons": selected["delivery_gallons"],
        "avail_90": selected["avail_90"],
        "final_gallons": selected["final_gallons"],
        "final_inches": selected["final_inches"],
        "max_capacity": selected["max_capacity"],
        "max_depth": selected["max_depth"],
        "ninety_limit": selected["ninety_limit"],
        "no_fit_warning": selected["no_fit_warning"],
    }

    logger.info(
        "CALC_COMPLETE",
        extra={
            "fuel_type": fuel_type,
            "mode": preferred_mode,
            "data_source": selected["data_source"],
            "initial_gallons": selected["initial_gallons"],
            "final_gallons": selected["final_gallons"],
            "delivery_gallons": int(delivery_gallons),
            "reason_code": "calculation_complete",
        },
    )
    return result


def _calculate_profile_for_mode(
    *, tank_mapping, current_inches, delivery_gallons, virtual_meta, mode
):
    if tank_mapping:
        resolved_mode, source_meta = determine_operating_mode(
            tank_mapping,
            force_source=mode,
        )
    else:
        resolved_mode, source_meta = determine_virtual_operating_mode(
            virtual_meta.get("store_id"),
            virtual_meta.get("fuel_type"),
            virtual_meta.get("tank_index"),
            force_source=mode,
        )

    if resolved_mode != mode or not source_meta:
        return None

    initial_gallons, _ = get_volume_from_depth(
        tank_mapping,
        current_inches,
        mode,
        source_meta,
    )
    final_gallons = initial_gallons + delivery_gallons
    final_inches = get_depth_from_volume(
        tank_mapping,
        final_gallons,
        mode,
        source_meta,
    )

    capacity = 0
    if tank_mapping and tank_mapping.tank_type:
        capacity = tank_mapping.tank_type.capacity or 0
    elif "capacity" in source_meta:
        capacity = source_meta["capacity"]

    ninety_percent_limit = capacity * 0.9
    gallons_to_ninety = max(0, ninety_percent_limit - initial_gallons)

    max_depth = 0.0
    if mode == MODE_MATHEMATICAL and source_meta.get("estimation"):
        max_depth = float(source_meta["estimation"].radius) * 2.0
    elif tank_mapping and tank_mapping.tank_type:
        max_depth = float(tank_mapping.tank_type.max_depth or 0)

    no_fit_warning = final_gallons > ninety_percent_limit
    estimated_ending_gallons = int(final_gallons)
    estimated_ending_inches = final_inches
    return {
        "mode": mode,
        "data_source": source_meta.get("name", mode),
        "confidence": source_meta.get("confidence", 1.0),
        "initial_inches": float(current_inches),
        "initial_gallons": int(initial_gallons),
        "delivery_gallons": int(delivery_gallons),
        "fillable_to_90": int(gallons_to_ninety),
        "estimated_ending_gallons": estimated_ending_gallons,
        "estimated_ending_inches": estimated_ending_inches,
        "max_capacity": int(capacity),
        "max_depth": round(max_depth, 2),
        "ninety_limit": int(ninety_percent_limit),
        "no_fit_warning": no_fit_warning,
        # Backward-compatible aliases
        "avail_90": int(gallons_to_ninety),
        "final_gallons": estimated_ending_gallons,
        "final_inches": estimated_ending_inches,
    }


def determine_operating_mode(tank_mapping, force_source=None):
    """
    Identifies the best available data source for an EXPLICIT tank mapping.

    Priority order is controlled by the TankGaugeConfig singleton (editable in
    Django admin). When both sources exist, the configured priority wins.
    When only one source is available, that source is always used regardless.

    OFFICIAL_FIRST order:  Chart → Mathematical → Unavailable
    MATHEMATICAL_FIRST order: Mathematical → Chart → Unavailable
    """
    priority = _get_mode_priority()
    logger.debug(
        "OPERATING_MODE_RESOLUTION_START",
        extra={
            "tank_mapping_id": tank_mapping.id,
            "priority": priority,
            "reason_code": "resolve_mode",
        },
    )

    # --- Resolve available sources without committing to either yet ---

    def _get_mathematical():
        """Returns (mode, meta) if any mathematical source is available, else None."""
        est = TankEstimation.objects.filter(
            tank_mapping=tank_mapping, is_active=True
        ).first()
        if est:
            return MODE_MATHEMATICAL, {
                "name": "MATHEMATICAL_ESTIMATE",
                "confidence": est.confidence,
                "estimation": est,
                "capacity": tank_mapping.tank_type.capacity or 0,
            }
        # Attempt on-the-fly estimation from Veeder data
        service = EstimationService()
        est = service.run_estimation_for_tank(tank_mapping)
        if est:
            return MODE_MATHEMATICAL, {
                "name": "MATHEMATICAL_ESTIMATE",
                "confidence": est.confidence,
                "estimation": est,
                "capacity": tank_mapping.tank_type.capacity or 0,
            }
        return None

    def _get_official():
        """Returns (mode, meta) if any official/generated chart is available, else None."""
        if TankChart.objects.filter(
            tank_type=tank_mapping.tank_type, is_official=True
        ).exists():
            return MODE_OFFICIAL, {"name": "OFFICIAL_CHART", "confidence": 1.0}
        if (
            _generated_chart_fallback_enabled()
            and TankChart.objects.filter(
                store=tank_mapping.store,
                tank_index=tank_mapping.tank_index,
                is_official=False,
            ).exists()
        ):
            return MODE_OFFICIAL, {
                "name": "GENERATED_CHART",
                "confidence": 1.0,
                "store": tank_mapping.store,
                "tank_index": tank_mapping.tank_index,
            }
        return None

    # --- Apply explicit source override when requested ---
    if force_source == MODE_MATHEMATICAL:
        result = _get_mathematical()
    elif force_source == MODE_OFFICIAL:
        result = _get_official()
    # --- Otherwise apply configured priority order ---
    elif priority == "MATHEMATICAL_FIRST":
        result = _get_mathematical() or _get_official()
    else:  # OFFICIAL_FIRST (default)
        result = _get_official() or _get_mathematical()

    if result:
        logger.debug(
            "OPERATING_MODE_RESOLVED",
            extra={
                "tank_mapping_id": tank_mapping.id,
                "mode": result[0],
                "source_name": result[1].get("name"),
                "reason_code": "mode_resolved",
            },
        )
        return result

    return MODE_UNAVAILABLE, None


def determine_virtual_operating_mode(
    store_id, fuel_type, tank_index, force_source=None
):
    """
    TACTICAL_INTEL: Reconstructs an estimation on-the-fly for unmapped tanks.
    Used when Veeder readings exist but no StoreTankMapping is defined.
    """
    from atg.models import VeederReading
    from tankgauge.models import VirtualTankEstimation
    from .utils import canonicalize_fuel

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

    latest = readings.order_by("-ticket__uploaded_at").first()
    store = latest.ticket.store
    fuel_key = canonicalize_fuel(fuel_type)

    # 2. Check for existing active VirtualTankEstimation (Priority)
    estimation = VirtualTankEstimation.objects.filter(
        store=store, fuel_type=fuel_key, tank_index=tank_index, is_active=True
    ).first()

    if estimation:
        mathematical_result = (
            MODE_MATHEMATICAL,
            {
                "name": "MATHEMATICAL_ESTIMATE",
                "confidence": estimation.confidence,
                "estimation": estimation,
                "capacity": float(latest.volume + latest.ullage),
            },
        )
        if force_source in (None, MODE_MATHEMATICAL):
            return mathematical_result

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
        mathematical_result = (
            MODE_MATHEMATICAL,
            {
                "name": "MATHEMATICAL_ESTIMATE",
                "confidence": estimation.confidence,
                "estimation": estimation,
                "capacity": total_capacity,
            },
        )
        if force_source in (None, MODE_MATHEMATICAL):
            return mathematical_result

    # 4. Fallback to existing generated chart
    if (
        force_source in (None, MODE_OFFICIAL)
        and _generated_chart_fallback_enabled()
        and TankChart.objects.filter(
            store=store, tank_index=tank_index, is_official=False
        ).exists()
    ):
        return MODE_OFFICIAL, {
            "name": "GENERATED_CHART",
            "confidence": 1.0,
            "store": store,
            "tank_index": tank_index,
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
        store = source_meta.get("store") or (
            tank_mapping.store if tank_mapping else None
        )
        tank_index = source_meta.get("tank_index") or (
            tank_mapping.tank_index if tank_mapping else None
        )
        tank_type = tank_mapping.tank_type if tank_mapping else None
        prefer_generated = source_meta.get("name") == "GENERATED_CHART"

        return (
            _get_volume_from_chart(
                tank_type,
                depth,
                store=store,
                tank_index=tank_index,
                prefer_generated=prefer_generated,
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
        store = source_meta.get("store") or (
            tank_mapping.store if tank_mapping else None
        )
        tank_index = source_meta.get("tank_index") or (
            tank_mapping.tank_index if tank_mapping else None
        )
        tank_type = tank_mapping.tank_type if tank_mapping else None
        prefer_generated = source_meta.get("name") == "GENERATED_CHART"

        return _get_depth_from_chart(
            tank_type,
            target_gallons,
            store=store,
            tank_index=tank_index,
            prefer_generated=prefer_generated,
        )

    if mode == MODE_MATHEMATICAL:
        estimation = source_meta.get("estimation")
        engine = GeometryEngine()
        depth = engine.depth_from_volume(
            estimation.radius, estimation.length, target_gallons
        )
        return float(depth)

    return 0.0


def _get_volume_from_chart(
    tank_type, depth, store=None, tank_index=None, prefer_generated=False
):
    """Internal: Original chart-based volume lookup."""

    # Resolve Chart Base Query: Prioritize generated chart if store/index provided
    chart_qs = TankChart.objects.none()
    if (
        prefer_generated
        and _generated_chart_fallback_enabled()
        and store
        and tank_index
    ):
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


def _get_depth_from_chart(
    tank_type, target_gallons, store=None, tank_index=None, prefer_generated=False
):
    """Internal: Original chart-based depth lookup."""

    # Resolve Chart Base Query: Prioritize generated chart if store/index provided
    chart_qs = TankChart.objects.none()
    if (
        prefer_generated
        and _generated_chart_fallback_enabled()
        and store
        and tank_index
    ):
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
