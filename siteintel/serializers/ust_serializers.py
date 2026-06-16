from rest_framework import serializers
from siteintel.models import USTPermit, USTVerification
from siteintel.logic.ust_service import calculate_permit_status

class USTPermitSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    
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
