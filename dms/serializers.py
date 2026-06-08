from rest_framework import serializers
from django.contrib.auth.models import User
from dms.models import Category, Collection, Document, TemporaryUpload, Tag


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for the Category model.
    """

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "active", "sort_order"]


class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for the Tag model.
    """

    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class UserMiniSerializer(serializers.ModelSerializer):
    """
    Simplified User serializer for document metadata representation.
    """

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class CollectionSerializer(serializers.ModelSerializer):
    """
    Serializer for the Collection model.
    """

    class Meta:
        model = Collection
        fields = ["id", "name", "description", "is_public"]


class DocumentSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for the Document model.
    """

    uploaded_by = UserMiniSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    collections = CollectionSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    download_url = serializers.SerializerMethodField()
    linked_object = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "original_filename",
            "stored_filename",
            "file_path",
            "mime_type",
            "file_size",
            "sha256",
            "uploaded_by",
            "uploaded_at",
            "status",
            "version",
            "download_count",
            "category",
            "collections",
            "is_public",
            "tags",
            "content_type",
            "object_id",
            "download_url",
            "linked_object",
        ]
        read_only_fields = [
            "id",
            "original_filename",
            "stored_filename",
            "file_path",
            "mime_type",
            "file_size",
            "sha256",
            "uploaded_by",
            "uploaded_at",
            "download_count",
            "download_url",
            "linked_object",
        ]

    def get_download_url(self, obj: Document) -> str:
        """
        Return the application download endpoint path.
        """
        return f"/dms/documents/{obj.id}/download/"

    def get_linked_object(self, obj: Document) -> dict | None:
        """
        Return metadata of the generic linked content object (Store, Location, etc.)
        """
        if obj.content_object:
            return {
                "model": obj.content_type.model,
                "app_label": obj.content_type.app_label,
                "id": obj.object_id,
                "name": str(obj.content_object),
            }
        return None


class DocumentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating document metadata (title, description, status, category, collections, is_public, tags).
    """

    class Meta:
        model = Document
        fields = ["title", "description", "status", "category", "collections", "is_public", "tags"]

    def update(self, instance: Document, validated_data: dict) -> Document:
        collections = validated_data.pop("collections", None)
        tags = validated_data.pop("tags", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Increment version when metadata is updated
        instance.version += 1
        instance.save()

        if collections is not None:
            instance.collections.set(collections)
        if tags is not None:
            instance.tags.set(tags)

        return instance
