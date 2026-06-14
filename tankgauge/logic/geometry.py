import math
from typing import List, Tuple, Dict, Any


class GeometryEngine:
    """
    PURE MATHEMATICAL SERVICE:
    Reconstructs horizontal cylinder tank geometry from volume/height observations.
    This engine contains NO ORM access and is independently testable.
    """

    VERSION = "1.0.0"

    def __init__(self, increment: float = 0.1):
        self.increment = increment

    def calculate_best_fit(
        self, total_capacity_gallons: float, readings: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Executes the iterative best-fit algorithm.
        Input: total_capacity_gallons, readings [(height_inches, volume_gallons), ...]
        Output: Structured results including radius, length, and diagnostics.
        """
        if not readings:
            return self._empty_result("No readings provided.")

        # Determine search boundaries
        max_measured_height = max(r[0] for r in readings)
        min_radius = max_measured_height / 2.0

        # We search from min_radius up to a reasonable maximum (e.g., 120 inches / 10ft radius)
        # or at least 2x the min_radius.
        search_max = max(min_radius * 4, 120.0)

        best_fit_r = None
        min_total_error = float("inf")
        best_diagnostics = {}

        # Iterative search for best-fit radius
        current_r = min_radius
        iterations = 0

        while current_r <= search_max:
            length = self._calculate_length(total_capacity_gallons, current_r)

            errors = []
            for h, v in readings:
                est_v = self.volume_from_depth(current_r, length, h)
                errors.append(abs(v - est_v))

            mean_error = sum(errors) / len(errors)
            max_error = max(errors)

            if mean_error < min_total_error:
                min_total_error = mean_error
                best_fit_r = current_r
                best_diagnostics = {
                    "mean_error": round(mean_error, 2),
                    "max_error": round(max_error, 2),
                    "iterations": iterations,
                    "sample_count": len(readings),
                }

            current_r += self.increment
            iterations += 1

        if best_fit_r is None:
            return self._empty_result("Could not find a suitable fit.")

        best_length = self._calculate_length(total_capacity_gallons, best_fit_r)

        return {
            "radius": round(best_fit_r, 2),
            "length": round(best_length, 2),
            "confidence": self._calculate_confidence(readings, min_total_error),
            "diagnostics": best_diagnostics,
            "algorithm_version": self.VERSION,
            "status": "SUCCESS",
        }

    def volume_from_depth(self, radius: float, length: float, depth: float) -> float:
        """
        Calculates volume (gallons) for a horizontal cylinder segment.
        Formula: V = L * [r^2 * cos^-1((r-h)/r) - (r-h) * sqrt(2rh - h^2)] / 231
        """
        if depth <= 0:
            return 0.0
        if depth >= (2 * radius):
            # Full cylinder volume
            return (math.pi * radius**2 * length) / 231.0

        # Vertical distance from center to fuel surface
        vs = radius - depth

        # Theta (Angle of the segment in radians)
        # cf = cos fraction
        cf = vs / radius
        # Ensure cf is within [-1, 1] for acos due to floating point precision
        cf = max(-1.0, min(1.0, cf))
        theta = 2 * math.acos(cf)

        # Sector Area = (r^2 * theta) / 2
        sa = (radius**2 * theta) / 2.0

        # Triangle Area = 0.5 * r^2 * sin(theta)
        ta = 0.5 * radius**2 * math.sin(theta)

        # 2D Segment Area
        segment_area = sa - ta

        # 3D Volume (converted from cubic inches to gallons)
        segment_volume = (segment_area * length) / 231.0

        return segment_volume

    def depth_from_volume(
        self, radius: float, length: float, target_volume: float
    ) -> float:
        """
        Inverse calculation using binary search to find depth (inches) from volume (gallons).
        """
        total_capacity = (math.pi * radius**2 * length) / 231.0
        if target_volume <= 0:
            return 0.0
        if target_volume >= total_capacity:
            return 2 * radius

        low = 0.0
        high = 2 * radius
        # Binary search for depth with 0.01 precision
        for _ in range(20):
            mid = (low + high) / 2
            v = self.volume_from_depth(radius, length, mid)
            if v < target_volume:
                low = mid
            else:
                high = mid

        return round(high, 2)

    def _calculate_length(self, total_capacity_gallons: float, radius: float) -> float:
        """Helper to find length in inches from total capacity and radius."""
        v_cubic_inches = total_capacity_gallons * 231.0
        return v_cubic_inches / (math.pi * radius**2)

    def _calculate_confidence(
        self, readings: List[Tuple[float, float]], mean_error: float
    ) -> float:
        """
        Heuristic for confidence scoring.
        Factors: Number of readings, Spread of heights, and Mean Error.
        """
        if not readings:
            return 0.0

        # Base score from sample size
        sample_score = min(len(readings) / 10.0, 0.4)  # Max 0.4 for 10+ readings

        # Spread score (max height - min height / radius)
        heights = [r[0] for r in readings]
        spread = max(heights) - min(heights)
        # Assuming a typical radius of 48-60 inches, spread of 20+ is good
        spread_score = min(spread / 40.0, 0.4)  # Max 0.4 for 40+ inch spread

        # Error penalty
        error_penalty = min(mean_error / 100.0, 0.2)  # Up to 0.2 penalty for 100G error

        confidence = sample_score + spread_score - error_penalty
        return round(max(0.1, min(0.95, confidence)), 2)

    def _empty_result(self, message: str) -> Dict[str, Any]:
        return {
            "status": "FAILED",
            "message": message,
            "radius": 0,
            "length": 0,
            "confidence": 0,
            "diagnostics": {},
            "algorithm_version": self.VERSION,
        }
