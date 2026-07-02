from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from dms.api.mixins import StandardAPIResponseMixin
from dms.models import Category, Collection, Tag
from dms.serializers import CategorySerializer, CollectionSerializer, TagSerializer


class CategoryListView(APIView, StandardAPIResponseMixin):
    """
    GET /api/v1/categories/
    List all active categories.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        categories = Category.objects.filter(active=True)
        serializer = CategorySerializer(categories, many=True)
        return self.success_response(serializer.data)


class CollectionListView(APIView, StandardAPIResponseMixin):
    """
    GET /api/v1/collections/
    List all active collections.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        collections = Collection.objects.all()
        if not (request.user.is_staff or request.user.is_superuser):
            collections = collections.filter(is_public=True)

        serializer = CollectionSerializer(collections, many=True)
        return self.success_response(serializer.data)


class TagListView(APIView, StandardAPIResponseMixin):
    """
    GET /api/v1/tags/
    List all tags.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        tags = Tag.objects.all()
        serializer = TagSerializer(tags, many=True)
        return self.success_response(serializer.data)
