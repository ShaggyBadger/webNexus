import json
from rest_framework.views import APIView
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from ..models import VeederTicket, VeederReading
from ..serializers import VeederTicketSerializer, VeederReadingSerializer
from ..services import VeederUploadService


class VeederTicketViewSet(viewsets.ModelViewSet):
    """
    TACTICAL API:
    Manage Veeder Tickets and their associated readings.
    Supports monolithic creation via the Service Layer.
    """

    queryset = VeederTicket.objects.all().prefetch_related("readings")
    serializer_class = VeederTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Redirect creation to the Service Layer for monolithic processing.
        """
        # We try to get readings from JSON string first (preferred for multipart)
        # then fallback to direct list (standard JSON API).
        readings_json = self.request.data.get("readings_json")
        if readings_json:
            try:
                readings_data = json.loads(readings_json)
            except (ValueError, TypeError):
                readings_data = []
        else:
            readings_data = self.request.data.get("readings", [])

        # We handle the creation manually via service to maintain strict atomicity
        # across the ticket and its multiple readings.
        try:
            ticket = VeederUploadService.process_ticket_submission(
                user=self.request.user,
                store=serializer.validated_data.get("store"),
                image=serializer.validated_data.get("image"),
                ticket_timestamp=serializer.validated_data.get("ticket_timestamp"),
                notes=serializer.validated_data.get("notes"),
                readings_data=readings_data,
            )
        except Exception as e:
            # Catching at view level to return 400 instead of 500
            raise serializers.ValidationError({"error": str(e)})

        # Update the serializer instance so the response contains the new ID
        serializer.instance = ticket


class VeederReadingViewSet(viewsets.ModelViewSet):
    """
    TACTICAL API:
    Manage individual tank readings.
    Used for granular corrections or analysis.
    """

    queryset = VeederReading.objects.all()
    serializer_class = VeederReadingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["fuel_type", "ticket__store"]


class VeederStatsView(APIView):
    """
    ML DATA EXPORT:
    Returns a flattened dataset of all tank readings across the fleet.
    Optimized for JSON/CSV consumption in Machine Learning environments.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        readings = VeederReading.objects.select_related(
            "ticket__store", "fuel_type"
        ).all()

        data = []
        for r in readings:
            data.append(
                {
                    "ticket_id": r.ticket.id,
                    "store_num": r.ticket.store.store_num,
                    "tank_index": r.tank_index,
                    "fuel_type": r.fuel_type.name,
                    "volume_gal": r.volume,
                    "ullage_gal": r.ullage,
                    "height_in": r.height,
                    "temp_f": r.temp,
                    "water_in": r.water,
                    "timestamp": r.ticket.ticket_timestamp or r.ticket.uploaded_at,
                    "is_verified": r.is_user_corrected,
                }
            )

        return Response({"status": "success", "count": len(data), "data": data})
