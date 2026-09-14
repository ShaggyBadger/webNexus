"""Application service for assembling the generic chart review payload."""

from genericcharts.pipeline.package import build_package_data


def build_review_context(
    *,
    selection,
    volume_gap_percent,
    near_duplicate_tolerance_percent,
    outlier_multiplier,
):
    """Assemble review data without exposing ORM objects to the template."""

    package = build_package_data(
        selection=selection,
        volume_gap_percent=volume_gap_percent,
        near_duplicate_tolerance_percent=near_duplicate_tolerance_percent,
        outlier_multiplier=outlier_multiplier,
    )
    return {
        "selection": selection,
        "scope_key": selection.package_scope_key,
        "generated_tank_count": len(package.generated_tanks),
        "catalog": package.catalog,
        "graphs": package.review_graphs,
        "collisions": package.collisions,
        "coverage_report": package.coverage_report,
        "package": package,
    }
