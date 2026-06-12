from rest_framework import serializers
from ..models import VeederTicket
from .reading_serializers import VeederReadingSerializer

class VeederTicketSerializer(serializers.ModelSerializer):
    """
    DATA ACQUISITION:
    Serializer for the physical ticket evidence.
    Includes nested readings for the monolithic 'Save' operation.
    """
    readings = VeederReadingSerializer(many=True, required=False)
    store_name = serializers.ReadOnlyField(source='store.store_name')
    uploaded_by_username = serializers.ReadOnlyField(source='uploaded_by.username')

    class Meta:
        model = VeederTicket
        fields = [
            'id', 
            'store', 
            'store_name',
            'image', 
            'ocr_text', 
            'ocr_status',
            'notes', 
            'ticket_timestamp', 
            'uploaded_by', 
            'uploaded_by_username',
            'uploaded_at',
            'readings'
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']
