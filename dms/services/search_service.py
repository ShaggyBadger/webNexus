from django.db.models import Q, QuerySet
from django.contrib.contenttypes.models import ContentType
from dms.models import Document
from siteintel.models import Location
from tankgauge.models import Store


class DocumentSearchService:
    """
    Service to perform server-side searching and filtering of documents.
    """

    @classmethod
    def search_documents(
        cls,
        queryset: QuerySet = None,
        search_query: str = None,
        category_id: int = None,
        category_slug: str = None,
        collection_id: str = None,
        status: str = None,
        uploaded_by_id: int = None,
        upload_date_start=None,
        upload_date_end=None,
        state: str = None,
        tag_id: int = None,
        tag_slug: str = None,
        is_public_only: bool = False,
    ) -> QuerySet:
        """
        Filter documents query based on query parameters, category, collection, tags, state, and public visibility.
        """
        if queryset is None:
            queryset = Document.objects.all()

        queryset = cls.optimize_queryset(queryset)

        # Enforce public visibility constraint
        if is_public_only:
            queryset = queryset.filter(is_public=True)

        # 1. Search Query (Title, Description, or Tag Name)
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(tags__name__icontains=search_query)
            )

        # 2. Category Filter
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        elif category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # 3. Collection Filter
        if collection_id:
            queryset = queryset.filter(collections__id=collection_id)

        # 4. Status Filter
        if status:
            queryset = queryset.filter(status=status)

        # 5. Uploaded By Filter
        if uploaded_by_id:
            queryset = queryset.filter(uploaded_by_id=uploaded_by_id)

        # 6. Upload Date Filter
        if upload_date_start:
            queryset = queryset.filter(uploaded_at__date__gte=upload_date_start)
        if upload_date_end:
            queryset = queryset.filter(uploaded_at__date__lte=upload_date_end)

        # 7. Tag Filter
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
        elif tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)

        # 8. State Filter (Location / Store state)
        if state:
            # Normalize state input (e.g. "NC")
            state_upper = state.strip().upper()

            # Find matching Location IDs and Store IDs in this state
            matching_location_ids = list(
                Location.objects.filter(state__iexact=state_upper).values_list(
                    "id", flat=True
                )
            )
            matching_store_ids = list(
                Store.objects.filter(state__iexact=state_upper).values_list(
                    "id", flat=True
                )
            )

            # Map them to content types
            location_ct = ContentType.objects.get_for_model(Location)
            store_ct = ContentType.objects.get_for_model(Store)

            # Filter documents whose GenericForeignKey points to one of these locations or stores
            location_q = Q(
                content_type=location_ct,
                object_id__in=[str(lid) for lid in matching_location_ids],
            )
            store_q = Q(
                content_type=store_ct,
                object_id__in=[str(sid) for sid in matching_store_ids],
            )

            queryset = queryset.filter(location_q | store_q)

        return queryset.distinct()

    @staticmethod
    def optimize_queryset(queryset: QuerySet) -> QuerySet:
        """
        Apply common relational loading hints used by list/detail views.
        """
        return queryset.select_related(
            "category",
            "uploaded_by",
            "content_type",
        ).prefetch_related("tags", "collections")
