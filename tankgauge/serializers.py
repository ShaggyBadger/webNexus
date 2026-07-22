from rest_framework import serializers


class CalcRequestSerializer(serializers.Serializer):
    store_id = serializers.CharField(required=True)
    fuel_type = serializers.CharField(required=True)
    tank_id = serializers.CharField(required=False, allow_blank=True)
    tank_index = serializers.IntegerField(required=False, allow_null=True)
    current_inches = serializers.FloatField(required=True, min_value=0)
    delivery_gallons = serializers.FloatField(required=True, min_value=0)
    display_mode = serializers.ChoiceField(
        required=False,
        choices=["AUTO", "OFFICIAL", "MATHEMATICAL"],
        default="AUTO",
    )


class CalcResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    fuel_type = serializers.CharField()
    mode = serializers.CharField()
    data_source = serializers.CharField()
    initial_inches = serializers.FloatField()
    initial_gallons = serializers.IntegerField()
    delivery_gallons = serializers.IntegerField()
    avail_90 = serializers.IntegerField()
    final_gallons = serializers.IntegerField()
    final_inches = serializers.FloatField()
    max_capacity = serializers.IntegerField(required=False)
    max_depth = serializers.FloatField(required=False)
    ninety_limit = serializers.IntegerField(required=False)
    no_fit_warning = serializers.BooleanField()
    message = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class EstimationHealthRequestSerializer(serializers.Serializer):
    store_id = serializers.CharField(required=False, allow_blank=True)
    fuel_type = serializers.CharField(required=False, allow_blank=True)
    tank_id = serializers.CharField(required=False, allow_blank=True)
    tank_index = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        tank_id = attrs.get("tank_id")
        has_mapping_id = bool(tank_id and str(tank_id).isdigit())
        has_virtual_identity = bool(
            attrs.get("store_id") and attrs.get("fuel_type") and attrs.get("tank_index")
        )

        if not has_mapping_id and not has_virtual_identity:
            raise serializers.ValidationError(
                "Provide either numeric tank_id or store_id + fuel_type + tank_index."
            )

        return attrs
