from rest_framework import serializers
from ..models import VeederReading


class VeederReadingSerializer(serializers.ModelSerializer):
    """
    DATA ACQUISITION:
    Serializer for individual tank readings.
    Enforces that Fuel Type, Volume, Ullage, and Height are provided.
    """

    fuel_type_name = serializers.ReadOnlyField(source="fuel_type.name")
    tank_index = serializers.IntegerField(required=True, min_value=1)
    volume = serializers.IntegerField(required=True, min_value=0)
    ullage = serializers.IntegerField(required=True, min_value=0)
    height = serializers.FloatField(required=True, min_value=0)
    confidence_score = serializers.FloatField(required=False, min_value=0, max_value=1)

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
            "fuel_type": {"required": True},
        }

    def validate(self, attrs):
        water = attrs.get("water")
        if water is not None and water < 0:
            raise serializers.ValidationError("water must be >= 0")

        temp = attrs.get("temp")
        if temp is not None and abs(temp) > 200:
            raise serializers.ValidationError(
                "temp out of plausible range (-200 to 200)"
            )

        volume = attrs.get("volume")
        ullage = attrs.get("ullage")
        if volume is not None and ullage is not None and (volume + ullage) <= 0:
            raise serializers.ValidationError("volume + ullage must be > 0")

        return attrs
