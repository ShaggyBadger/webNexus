from rest_framework import serializers


class CalcRequestSerializer(serializers.Serializer):
    store_id = serializers.CharField(required=True)
    fuel_type = serializers.CharField(required=True)
    tank_id = serializers.CharField(required=False, allow_blank=True)
    tank_index = serializers.IntegerField(required=False, allow_null=True)
    current_inches = serializers.FloatField(required=True, min_value=0)
    delivery_gallons = serializers.IntegerField(required=True, min_value=0)


class CalcResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    fuel_type = serializers.CharField()
    mode = serializers.CharField()
    data_source = serializers.CharField()
    confidence = serializers.FloatField()
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
