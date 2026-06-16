import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from tankgauge.models import Store
from siteintel.models import USTPermit, USTVerification
from siteintel.serializers.ust_serializers import USTPermitSerializer, USTVerificationSerializer
from siteintel.logic import ust_service
from tankgauge.logic.utils import haversine

logger = logging.getLogger("webnexus")

class USTPermitDetailView(APIView):
    """
    API endpoint for retrieving and updating a store's active UST permit.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        permit = USTPermit.objects.filter(store=store, is_active=True).first()
        if not permit:
            return Response({"detail": "No active permit found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = USTPermitSerializer(permit)
        return Response(serializer.data)

    def patch(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        # We use the service to handle deactivation of old and creation of new to preserve history
        # and ensure atomic verification log entry.
        
        # Use serializer for validation
        serializer = USTPermitSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            permit_data = serializer.validated_data
            # Extract verification notes if provided (not part of permit model)
            notes = request.data.get('verification_notes')
            
            new_permit, _ = ust_service.update_permit(
                store=store,
                user=request.user,
                permit_data=permit_data,
                notes=notes
            )
            
            # Re-serialize the new permit (which will have proper date objects)
            return Response(USTPermitSerializer(new_permit).data)
        except Exception as e:
            logger.error(f"UST_API_ERROR: Failed to update permit for store {store_id}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class USTVerificationListView(APIView):
    """
    API endpoint for listing and creating UST verification records.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        verifications = USTVerification.objects.filter(store=store)
        serializer = USTVerificationSerializer(verifications, many=True)
        return Response(serializer.data)

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        v_type = request.data.get('verification_type', 'confirmed')
        notes = request.data.get('notes')
        
        if v_type == 'confirmed':
            verification = ust_service.confirm_permit(store, request.user, notes)
            serializer = USTVerificationSerializer(verification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif v_type == 'updated':
            # This path is usually handled by the permit PATCH, but we support it here if they 
            # provide permit data.
            permit_data = request.data.get('permit_data')
            if not permit_data:
                return Response({"error": "permit_data required for 'updated' type"}, status=status.HTTP_400_BAD_REQUEST)
            
            new_permit, verification = ust_service.update_permit(store, request.user, permit_data, notes)
            serializer = USTVerificationSerializer(verification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response({"error": "Invalid verification type"}, status=status.HTTP_400_BAD_REQUEST)


class NearbyStoreListView(APIView):
    """
    UI Utility endpoint to find nearby stores for GPS triggering.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        
        if not lat or not lng:
            return Response({"error": "lat and lng required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            lat = float(lat)
            lng = float(lng)
        except ValueError:
            return Response({"error": "Invalid coordinates"}, status=status.HTTP_400_BAD_REQUEST)
        
        # In a real production app with many stores, we'd use GIS queries.
        # For this project, we'll iterate and use haversine if the list is manageable.
        stores = Store.objects.filter(lat__isnull=False, lon__isnull=False)
        nearby_stores = []
        
        for store in stores:
            dist = haversine(lat, lng, store.lat, store.lon)
            if dist <= 0.1:  # ~500 feet (0.1 miles is approx 528 feet)
                nearby_stores.append({
                    "id": store.id,
                    "store_num": store.store_num,
                    "name": store.store_name,
                    "distance_miles": dist,
                    "status": ust_service.calculate_permit_status(
                        USTPermit.objects.filter(store=store, is_active=True).first()
                    )
                })
        
        return Response(nearby_stores)
