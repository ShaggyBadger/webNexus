from rest_framework import serializers
from siteintel.models import USTPermit, USTVerification
from siteintel.logic.ust_service import calculate_permit_status, normalize_expiration_date

class FlexibleDateField(serializers.DateField):
    """
    Custom field to handle YYYY-MM format from HTML5 month inputs,
    normalizing them to the end of the month.
    """
    def to_internal_value(self, value):
        if not value:
            return None
        
        # Try our service normalization first (handles YYYY-MM and YYYY-MM-DD)
        normalized = normalize_expiration_date(value)
        if normalized:
            return normalized
            
        return super().to_internal_value(value)

class USTPermitSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    expiration_date = FlexibleDateField()
    
    class Meta:
        model = USTPermit
        fields = [
            'id', 'store', 'is_active', 'permit_number', 
            'issue_date', 'expiration_date', 'permit_image', 
            'notes', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at', 'status']

    def get_status(self, obj):
        return calculate_permit_status(obj)


class USTVerificationSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    
    class Meta:
        model = USTVerification
        fields = [
            'id', 'store', 'user', 'username', 'timestamp', 
            'verification_type', 'notes'
        ]
        read_only_fields = ['id', 'user', 'timestamp']
