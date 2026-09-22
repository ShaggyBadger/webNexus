import math

from rest_framework import serializers


class WeatherRequestSerializer(serializers.Serializer):
    """Validate coordinates submitted to the weather endpoint."""

    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)

    def validate(self, attrs):
        if not all(math.isfinite(attrs[field]) for field in ("latitude", "longitude")):
            raise serializers.ValidationError("Coordinates must be finite numbers.")
        return attrs
