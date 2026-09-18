from rest_framework import serializers
from decimal import Decimal
from ..models import VeederReading


class VeederReadingSerializer(serializers.ModelSerializer):
    """
    DATA ACQUISITION:
    Serializer for individual tank readings.
    Enforces that Fuel Type, Volume, Ullage, and Height are provided.
    """

    fuel_type_name = serializers.ReadOnlyField(source="fuel_type.name")
    tank_index = serializers.IntegerField(required=True, min_value=1)
    volume = serializers.DecimalField(
        required=True,
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )
    ullage = serializers.DecimalField(
        required=True,
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )
    height = serializers.DecimalField(
        required=True,
        max_digits=8,
        decimal_places=3,
        min_value=Decimal("0"),
    )
    printed_physical_capacity_gallons = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )
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
            "printed_physical_capacity_gallons",
            "printed_capacity_text",
            "ullage_endpoint_gallons",
            "ullage_endpoint_percent_exact",
            "basis_status",
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

        printed_capacity = attrs.get("printed_physical_capacity_gallons")
        if printed_capacity is not None:
            if printed_capacity <= 0:
                raise serializers.ValidationError(
                    "printed_physical_capacity_gallons must be > 0"
                )
            endpoint = volume + ullage
            attrs["ullage_endpoint_gallons"] = endpoint
            attrs["ullage_endpoint_percent_exact"] = (
                endpoint / printed_capacity * Decimal("100")
            ).quantize(Decimal("0.0001"))
            if "basis_status" not in attrs or attrs["basis_status"] == "UNKNOWN":
                attrs["basis_status"] = "SUGGESTED"

        return attrs
