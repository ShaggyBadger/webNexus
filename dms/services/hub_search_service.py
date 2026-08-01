from typing import Any, Dict, List, Tuple
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from rapidfuzz import fuzz

from dms.models import Category, Collection, Document, Tag
from tankgauge.models import Store


class FuzzyCorpus:
    """Per-field fuzzy matcher. Scores each field independently, keeps the best."""

    def __init__(self, records: List[Tuple[Any, Dict[str, Any]]]) -> None:
        """
        records: list of (record_id, {"field1": val1, "field2": val2, ...})
        """
        self.ids = [r[0] for r in records]
        self.field_sets = [r[1] for r in records]

    def search(self, query: str, threshold: float) -> List[Tuple[Any, int]]:
        best: List[Tuple[Any, int]] = []
        for record_id, fields in zip(self.ids, self.field_sets):
            scores: List[float] = []
            for value in fields.values():
                if value is None:
                    continue
                val_str = str(value)
                if not val_str:
                    continue
                score = fuzz.WRatio(query, val_str, score_cutoff=threshold)
                if score:
                    scores.append(score)
            if scores:
                best.append((record_id, int(max(scores))))
        return best


class HubSearchService:
    """
    Hybrid fuzzy / ORM search service for Location Document Hub.
    Combines ORM candidate generation with per-field RapidFuzz scoring.
    """

    @classmethod
    def search(
        cls,
        query: str,
        limit: int = 20,
        offset: int = 0,
        public_only: bool = True,
    ) -> Dict[str, Any]:
        min_len = getattr(settings, "HUB_MIN_QUERY_LENGTH", 2)
        clean_q = query.strip() if query else ""
        if not clean_q or len(clean_q) < min_len:
            return {"query": clean_q, "count": 0, "stores": [], "documents": []}

        max_limit = 50
        limit = min(limit, max_limit)

        store_threshold = getattr(settings, "HUB_FUZZY_STORE_THRESHOLD", 50)
        doc_threshold = getattr(settings, "HUB_FUZZY_DOCUMENT_THRESHOLD", 55)
        icontains_boost = getattr(settings, "HUB_ICONTAINS_BOOST", 25)
        fuzzy_docs_enabled = getattr(settings, "HUB_FUZZY_DOCUMENTS", True)
        full_corpus = getattr(settings, "HUB_FUZZY_FULL_CORPUS", False)

        # ----------------------------------------------------
        # 1. STORES SEARCH
        # ----------------------------------------------------
        store_ct = ContentType.objects.get_for_model(Store)

        # ORM candidate subset
        if full_corpus:
            store_qs = Store.objects.filter(store_num__isnull=False)
        else:
            store_qs = Store.objects.filter(
                Q(store_num__icontains=clean_q)
                | Q(store_name__icontains=clean_q)
                | Q(city__icontains=clean_q)
                | Q(state__icontains=clean_q)
            ).filter(store_num__isnull=False)

        # Extract candidates for fuzzy corpus
        store_records = []
        orm_store_hits = set()
        exact_num_match_id = None

        for st in store_qs:
            store_records.append(
                (
                    st.id,
                    {
                        "store_num": st.store_num,
                        "store_name": st.store_name,
                        "city": st.city,
                        "state": st.state,
                        "zip_code": st.zip_code,
                    },
                )
            )
            orm_store_hits.add(st.id)
            if clean_q.isdigit() and st.store_num == int(clean_q):
                exact_num_match_id = st.id

        # Score store fuzzy corpus
        store_corpus = FuzzyCorpus(store_records)
        store_fuzzy_results = store_corpus.search(clean_q, store_threshold)

        # Build final store score map
        store_scores: Dict[int, int] = {}
        for st_id, f_score in store_fuzzy_results:
            final_score = f_score
            if st_id in orm_store_hits:
                final_score = min(100, final_score + icontains_boost)
            store_scores[st_id] = final_score

        # Ensure pure ORM hits that had 0 fuzzy score are included with boost
        for st_id in orm_store_hits:
            if st_id not in store_scores:
                store_scores[st_id] = min(100, icontains_boost)

        if exact_num_match_id:
            store_scores[exact_num_match_id] = 100

        matched_store_ids = list(store_scores.keys())

        # Fetch store data + document_count in bulk
        matched_stores_qs = (
            Store.objects.filter(id__in=matched_store_ids)
            .annotate(
                doc_count=Count(
                    "id",
                    filter=Q(
                        id__in=Document.objects.filter(
                            content_type=store_ct,
                            status="ACTIVE",
                            **({"is_public": True} if public_only else {}),
                        ).values_list("object_id", flat=True)
                    ),
                )
            )
            .only("id", "store_num", "store_name", "city", "state")
        )

        # We compute document_count properly via GenericFK
        # Notice string conversion for object_id GFK matching:
        doc_count_map: Dict[int, int] = {}
        if matched_store_ids:
            str_store_ids = [str(sid) for sid in matched_store_ids]
            doc_counts = (
                Document.objects.filter(
                    content_type=store_ct,
                    object_id__in=str_store_ids,
                    status="ACTIVE",
                    **({"is_public": True} if public_only else {}),
                )
                .values("object_id")
                .annotate(cnt=Count("id"))
            )
            for dc in doc_counts:
                try:
                    doc_count_map[int(dc["object_id"])] = dc["cnt"]
                except (ValueError, TypeError):
                    pass

        store_list = []
        for st in matched_stores_qs:
            score = store_scores.get(st.id, 0)
            store_list.append(
                {
                    "store_num": st.store_num,
                    "store_name": st.store_name or f"STORE #{st.store_num}",
                    "city": st.city or "",
                    "state": st.state or "",
                    "score": score,
                    "document_count": doc_count_map.get(st.id, 0),
                    "_id": st.id,
                }
            )

        # Sort stores desc by score, ties by store_num
        store_list.sort(key=lambda x: (x["score"], x["store_num"] or 0), reverse=True)

        # ----------------------------------------------------
        # 2. DOCUMENTS SEARCH
        # ----------------------------------------------------
        base_doc_qs = Document.objects.filter(status="ACTIVE")
        if public_only:
            base_doc_qs = base_doc_qs.filter(is_public=True)

        matched_str_store_ids = [str(st["_id"]) for st in store_list if st.get("_id")]

        if full_corpus:
            doc_candidate_qs = base_doc_qs
        else:
            doc_candidate_qs = base_doc_qs.filter(
                Q(title__icontains=clean_q)
                | Q(description__icontains=clean_q)
                | Q(tags__name__icontains=clean_q)
                | Q(category__name__icontains=clean_q)
                | Q(collections__name__icontains=clean_q)
                | Q(content_type=store_ct, object_id__in=matched_str_store_ids)
            ).distinct()

        doc_records = []
        orm_doc_hits = set()
        cascade_doc_hits = set()

        doc_objs = doc_candidate_qs.select_related(
            "category", "content_type"
        ).prefetch_related("tags")

        # Map store id to store_num for response formatting
        store_num_map = {
            str(st["_id"]): st["store_num"] for st in store_list if st.get("_id")
        }

        for doc in doc_objs:
            tag_names = [t.name for t in doc.tags.all()]
            cat_name = doc.category.name if doc.category else ""
            fields_dict = {
                "title": doc.title,
                "category": cat_name,
            }
            for i, tag in enumerate(tag_names):
                fields_dict[f"tag_{i}"] = tag

            doc_records.append((doc.id, fields_dict))

            # Check if direct ORM match
            if (
                clean_q.lower() in doc.title.lower()
                or (doc.description and clean_q.lower() in doc.description.lower())
                or (cat_name and clean_q.lower() in cat_name.lower())
                or any(clean_q.lower() in t.lower() for t in tag_names)
            ):
                orm_doc_hits.add(doc.id)

            if (
                doc.content_type_id == store_ct.id
                and doc.object_id in matched_str_store_ids
            ):
                cascade_doc_hits.add(doc.id)

        doc_scores: Dict[str, int] = {}
        if fuzzy_docs_enabled:
            doc_corpus = FuzzyCorpus(doc_records)
            doc_fuzzy_results = doc_corpus.search(clean_q, doc_threshold)
            for d_id, f_score in doc_fuzzy_results:
                final_s = f_score
                if d_id in orm_doc_hits:
                    final_s = min(100, final_s + icontains_boost)
                doc_scores[d_id] = final_s

        for d_id in orm_doc_hits:
            if d_id not in doc_scores:
                doc_scores[d_id] = min(100, icontains_boost)

        for d_id in cascade_doc_hits:
            # Cascade match gets boosted based on store score or fallback 70
            if d_id not in doc_scores:
                doc_scores[d_id] = 70

        doc_list = []
        for doc in doc_objs:
            score = doc_scores.get(doc.id, 0)
            if score <= 0:
                continue

            st_num = None
            if doc.content_type_id == store_ct.id and doc.object_id:
                st_num = store_num_map.get(doc.object_id)
                if st_num is None:
                    # Fallback lookup store_num if not in matched stores list
                    try:
                        st_obj = Store.objects.filter(id=int(doc.object_id)).first()
                        if st_obj:
                            st_num = st_obj.store_num
                    except (ValueError, TypeError):
                        pass

            download_url = f"/dms/documents/{doc.id}/download/"

            doc_list.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "category": doc.category.name if doc.category else "Uncategorized",
                    "store_num": st_num,
                    "score": score,
                    "download_url": download_url,
                }
            )

        doc_list.sort(key=lambda x: (x["score"], x["title"]), reverse=True)

        total_count = len(store_list) + len(doc_list)

        # Strip private `_id` key from stores output
        final_stores = []
        for st in store_list[offset : offset + limit]:
            st_copy = dict(st)
            st_copy.pop("_id", None)
            final_stores.append(st_copy)

        final_docs = doc_list[offset : offset + limit]

        return {
            "query": clean_q,
            "count": total_count,
            "stores": final_stores,
            "documents": final_docs,
        }
