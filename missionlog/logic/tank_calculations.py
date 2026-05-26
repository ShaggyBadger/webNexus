import logging
from django.db.models import Q
from tankgauge.models.store_models import Store, StoreTankMapping
from tankgauge.models.hardware_models import TankChart

logger = logging.getLogger("webnexus")


def calculate_gallons(store_identifier, fuel_type_name, inches):
    """
    TACTICAL TANK CHART INTERPOLATION:
    Given a store identifier (database primary key or physical store number),
    a case-insensitive fuel type, and depth measurement in inches (float),
    looks up the associated calibration charts and performs high-precision
    linear interpolation to calculate opening/closing gallons.
    """
    try:
        # Resolve store by PK or store number
        store = Store.objects.filter(
            Q(id=store_identifier) | Q(store_num=store_identifier)
        ).first()
        if not store:
            logger.debug(f"CALC_FAIL: Store {store_identifier} not found in database.")
            return None

        # Match fuel type case-insensitively
        mapping = store.tank_mappings.filter(fuel_type__iexact=fuel_type_name).first()
        if not mapping:
            logger.debug(
                f"CALC_FAIL: No tank mapping found for store {store.store_num} with fuel type '{fuel_type_name}'."
            )
            return None

        tank_type = mapping.tank_type
        charts = TankChart.objects.filter(tank_type=tank_type).order_by("inches")
        if not charts.exists():
            logger.debug(
                f"CALC_FAIL: No calibration charts found for TankType '{tank_type.name}' (Store: {store.store_num})."
            )
            return None

        inches_float = float(inches)
        if inches_float <= 0:
            return 0.0

        # Find bounds for interpolation
        lower_bound = None
        upper_bound = None

        for chart in charts:
            if float(chart.inches) == inches_float:
                return float(chart.gallons)
            if float(chart.inches) < inches_float:
                lower_bound = chart
            if float(chart.inches) > inches_float:
                upper_bound = chart
                break

        if lower_bound and not upper_bound:
            return float(lower_bound.gallons)
        if upper_bound and not lower_bound:
            return float(upper_bound.gallons)

        # Linear Interpolation
        x1, y1 = float(lower_bound.inches), float(lower_bound.gallons)
        x2, y2 = float(upper_bound.inches), float(upper_bound.gallons)

        if x2 == x1:
            return y1

        interpolated = y1 + (inches_float - x1) * (y2 - y1) / (x2 - x1)
        logger.debug(
            f'CALC_SUCCESS: Interpolated {inches_float}" in {tank_type.name} to {interpolated:.2f} gal.'
        )
        return round(interpolated, 2)

    except Exception as e:
        logger.error(f"CALC_ERROR: Exception in tank volume interpolation: {str(e)}")
        return None


def calculate_inches(store_identifier, fuel_type_name, gallons):
    """
    INVERSE TANK CHART INTERPOLATION:
    Looks up the depth in inches for a given volume in gallons.
    """
    try:
        store = Store.objects.filter(
            Q(id=store_identifier) | Q(store_num=store_identifier)
        ).first()
        if not store:
            return None

        mapping = store.tank_mappings.filter(fuel_type__iexact=fuel_type_name).first()
        if not mapping:
            return None

        tank_type = mapping.tank_type
        charts = TankChart.objects.filter(tank_type=tank_type).order_by("gallons")
        if not charts.exists():
            return None

        gallons_float = float(gallons)
        if gallons_float <= 0:
            return 0.0

        lower_bound = None
        upper_bound = None

        for chart in charts:
            if float(chart.gallons) == gallons_float:
                return float(chart.inches)
            if float(chart.gallons) < gallons_float:
                lower_bound = chart
            if float(chart.gallons) > gallons_float:
                upper_bound = chart
                break

        if lower_bound and not upper_bound:
            return float(lower_bound.inches)
        if upper_bound and not lower_bound:
            return float(upper_bound.inches)

        # Linear Interpolation
        x1, y1 = float(lower_bound.gallons), float(lower_bound.inches)
        x2, y2 = float(upper_bound.gallons), float(upper_bound.inches)

        if x2 == x1:
            return y1

        interpolated = y1 + (gallons_float - x1) * (y2 - y1) / (x2 - x1)
        return round(interpolated, 2)
    except Exception as e:
        logger.error(
            f"CALC_ERROR: Exception in inverse tank volume interpolation: {str(e)}"
        )
        return None
