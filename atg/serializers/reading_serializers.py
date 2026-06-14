from rest_framework import serializers
from ..models import VeederReading


class VeederReadingSerializer(serializers.ModelSerializer):
    """
    DATA ACQUISITION:
    Serializer for individual tank readings.
    Enforces that Fuel Type, Volume, Ullage, and Height are provided.
    """

    fuel_type_name = serializers.ReadOnlyField(source="fuel_type.name")

    class Meta:
        model = VeederReading
        fields = [
            "id",
            "tank_index",
            "fuel_type",
            "fuel_type_name",
            "volume",
            "ullage",
            "height",
            "temp",
            "water",
            "raw_line_text",
            "confidence_score",
            "is_user_corrected",
        ]
        extra_kwargs = {
            "tank_index": {"required": False},  # Optional if not parsed
            "volume": {"required": True},
            "ullage": {"required": True},
            "height": {"required": True},
            "fuel_type": {"required": True},
        }
