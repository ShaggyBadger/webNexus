from rest_framework import serializers
from tankgauge.models import Store

class StoreSerializer(serializers.ModelSerializer):
    """
    Serializer for Store lookup.
    Exposes key fields needed for the typeahead search.
    """
    name = serializers.CharField(source="store_name", read_only=True)
    store_pk = serializers.IntegerField(source="id", read_only=True)

    class Meta:
        model = Store
        fields = [
            "store_pk",
            "store_num",
            "name",
            "city",
            "state",
        ]
