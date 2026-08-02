from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet
from rapidfuzz import fuzz

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
        Filter documents by search query and dashboard filters.

        Commander's Intent:
        Field users must reliably find the right document with multi-token
        queries like "exxon charlotte nc". Weak search causes bad document
        retrieval in operational moments.
        """
        if queryset is None:
            queryset = Document.objects.all()

        queryset = cls.optimize_queryset(queryset)

        # Enforce public visibility constraint
        if is_public_only:
            queryset = queryset.filter(is_public=True)

        # 1. Search Query (Title, Description, or Tag Name)
        if search_query:
            queryset = cls._apply_token_aware_search(
                queryset=queryset,
                search_query=search_query,
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

    @classmethod
    def _apply_token_aware_search(
        cls,
        *,
        queryset: QuerySet,
        search_query: str,
    ) -> QuerySet:
        tokens = cls._tokenize(search_query)
        if not tokens:
            return queryset

        matched_store_ids = cls._find_matching_store_ids(tokens=tokens)
        matched_document_ids = cls._find_matching_document_ids(
            queryset=queryset,
            tokens=tokens,
            matched_store_ids=matched_store_ids,
        )
        if not matched_document_ids:
            return queryset.none()
        return queryset.filter(id__in=matched_document_ids)

    @staticmethod
    def _tokenize(search_query: str) -> list[str]:
        return [
            token.strip().lower() for token in search_query.split() if token.strip()
        ]

    @classmethod
    def _find_matching_store_ids(cls, *, tokens: list[str]) -> set[int]:
        threshold = int(getattr(settings, "DMS_STORE_TOKEN_THRESHOLD", 50))
        matched_ids: set[int] = set()

        for store in Store.objects.filter(store_num__isnull=False).only(
            "id",
            "store_num",
            "store_name",
            "city",
            "state",
        ):
            store_blob = cls._store_blob(store=store)
            if cls._tokens_match(text=store_blob, tokens=tokens, threshold=threshold):
                matched_ids.add(store.id)
        return matched_ids

    @classmethod
    def _find_matching_document_ids(
        cls,
        *,
        queryset: QuerySet,
        tokens: list[str],
        matched_store_ids: set[int],
    ) -> set[str]:
        threshold = int(getattr(settings, "DMS_DOCUMENT_TOKEN_THRESHOLD", 55))
        matched_ids: set[str] = set()
        store_content_type = ContentType.objects.get_for_model(Store)

        candidates = cls.optimize_queryset(queryset)
        for document in candidates:
            document_blob = cls._document_blob(document=document)
            if cls._tokens_match(
                text=document_blob, tokens=tokens, threshold=threshold
            ):
                matched_ids.add(document.id)
                continue

            if (
                document.content_type_id == store_content_type.id
                and document.object_id
                and document.object_id.isdigit()
                and int(document.object_id) in matched_store_ids
            ):
                matched_ids.add(document.id)
        return matched_ids

    @staticmethod
    def _tokens_match(*, text: str, tokens: list[str], threshold: int) -> bool:
        text_lower = text.lower()
        for token in tokens:
            score = fuzz.WRatio(token, text_lower)
            if score < threshold:
                return False
        return True

    @classmethod
    def _store_blob(cls, *, store: Store) -> str:
        state_value = (store.state or "").strip().lower()
        return " ".join(
            [
                str(store.store_num or ""),
                (store.store_name or "").lower(),
                (store.city or "").lower(),
                state_value,
                cls._state_aliases(state_value),
            ]
        ).strip()

    @staticmethod
    def _document_blob(*, document: Document) -> str:
        tag_names = " ".join(tag.name for tag in document.tags.all())
        collection_names = " ".join(
            collection.name for collection in document.collections.all()
        )
        category_name = document.category.name if document.category else ""
        return " ".join(
            [
                document.title or "",
                document.description or "",
                tag_names,
                category_name,
                collection_names,
            ]
        ).lower()

    @staticmethod
    def _state_aliases(state_value: str) -> str:
        state_alias_map = {
            "nc": "north carolina",
            "north carolina": "nc",
            "sc": "south carolina",
            "south carolina": "sc",
            "va": "virginia",
            "virginia": "va",
            "ga": "georgia",
            "georgia": "ga",
            "tn": "tennessee",
            "tennessee": "tn",
        }
        return state_alias_map.get(state_value, "")
