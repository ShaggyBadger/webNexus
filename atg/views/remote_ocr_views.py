import logging
import json
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import VeederTicket, VeederReading
from ..serializers import VeederTicketSerializer
from ..utils.permissions import IsRemoteOCRClient
from ..services import VeederUploadService

logger = logging.getLogger("webnexus")

class RemoteOCRInstructionsView(APIView):
    """
    ENDPOINT 1: INSTRUCTIONS
    Provides the manual and documentation for the Remote OCR Desktop client.
    """
    permission_classes = [IsRemoteOCRClient]

    def get(self, request):
        instructions = {
            "mission": "Offload OCR processing from Linode (4GB) to Desktop (GPU/12GB).",
            "protocol": "Fetch-Process-Resolve",
            "endpoints": {
                "GET /atg/api/v1/remote-ocr/instructions/": "This document.",
                "GET /atg/api/v1/remote-ocr/fetch-job/": "Acquire the oldest PENDING ticket and its image URL.",
                "POST /atg/api/v1/remote-ocr/resolve-job/": "Upload extracted JSON data for a ticket."
            },
            "resolve_payload_format": {
                "ticket_id": "ULID_STRING",
                "ocr_text": "FULL_RAW_TEXT_BLOCK",
                "readings": [
                    {
                        "tank_index": 1,
                        "fuel_type_id": 5,
                        "volume": 5000,
                        "ullage": 1200,
                        "height": 92.5,
                        "temp": 68.4,
                        "raw_line_text": "1 REGULAR 5000 1200 92.5"
                    }
                ]
            },
            "security": "Requires 'X-ATG-Remote-Key' header."
        }
        return Response(instructions)

class RemoteOCRFetchJobView(APIView):
    """
    ENDPOINT 2: FETCH_JOB
    Returns the oldest ticket with 'PENDING' status.
    Marks it as 'PROCESSING' to avoid race conditions.
    """
    permission_classes = [IsRemoteOCRClient]

    def get(self, request):
        with transaction.atomic():
            ticket = VeederTicket.objects.filter(ocr_status='PENDING').order_by('uploaded_at').first()
            if not ticket:
                return Response({"status": "idle", "message": "No pending jobs found."}, status=status.HTTP_200_OK)
            
            ticket.ocr_status = 'PROCESSING'
            ticket.save()
            
            serializer = VeederTicketSerializer(ticket)
            return Response(serializer.data)

class RemoteOCRResolveJobView(APIView):
    """
    ENDPOINT 3: RESOLVE_JOB
    Accepts extracted data, creates readings, and marks ticket as COMPLETED.
    """
    permission_classes = [IsRemoteOCRClient]

    def post(self, request):
        ticket_id = request.data.get('ticket_id')
        readings_data = request.data.get('readings', [])
        ocr_text = request.data.get('ocr_text', '')

        if not ticket_id:
            return Response({"error": "ticket_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                ticket = VeederTicket.objects.select_for_update().get(id=ticket_id)
                
                # 1. Update Ticket Metadata
                ticket.ocr_text = ocr_text
                ticket.ocr_status = 'COMPLETED'
                ticket.save()

                # 2. Create Readings (Standardized via established Service pattern)
                # We clear any partial readings first to ensure a clean slate
                ticket.readings.all().delete()
                
                for r_data in readings_data:
                    VeederReading.objects.create(
                        ticket=ticket,
                        tank_index=r_data.get('tank_index'),
                        fuel_type_id=r_data.get('fuel_type_id'),
                        volume=r_data.get('volume'),
                        ullage=r_data.get('ullage'),
                        height=r_data.get('height'),
                        temp=r_data.get('temp'),
                        water=r_data.get('water'),
                        raw_line_text=r_data.get('raw_line_text'),
                        confidence_score=r_data.get('confidence_score', 1.0),
                        is_user_corrected=True # Remote OCR client implies human-verified locally
                    )

                logger.info(f"REMOTE_OCR_RESOLVE: Ticket {ticket_id} resolved with {len(readings_data)} readings.")
                return Response({"status": "success", "ticket_id": ticket_id})

        except VeederTicket.DoesNotExist:
            return Response({"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"REMOTE_OCR_RESOLVE_FAILED: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
