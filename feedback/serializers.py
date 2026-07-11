import json

from django.conf import settings
from rest_framework import serializers

from .models import FeedbackReport


class FeedbackInitiateSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=1024)
    viewport_size = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )
    user_agent = serializers.CharField(required=False, allow_blank=True)
    page_metadata = serializers.DictField(required=False)

    def validate_page_metadata(self, value):
        max_bytes = getattr(settings, "FEEDBACK_MAX_METADATA_BYTES", 16384)
        serialized = json.dumps(value, ensure_ascii=True)
        if len(serialized.encode("utf-8")) > max_bytes:
            raise serializers.ValidationError(
                f"Metadata exceeds {max_bytes} bytes limit."
            )
        return value


class FeedbackSubmitSerializer(serializers.Serializer):
    click_event_id = serializers.IntegerField(min_value=1)
    category = serializers.ChoiceField(choices=FeedbackReport.CATEGORY_CHOICES)
    message = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    page_metadata = serializers.DictField(required=False)

    def validate_page_metadata(self, value):
        max_bytes = getattr(settings, "FEEDBACK_MAX_METADATA_BYTES", 16384)
        serialized = json.dumps(value, ensure_ascii=True)
        if len(serialized.encode("utf-8")) > max_bytes:
            raise serializers.ValidationError(
                f"Metadata exceeds {max_bytes} bytes limit."
            )
        return value
