import json
from datetime import UTC, datetime
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone as django_timezone
from django.utils.text import slugify

from atg.models import VeederTicket
from dms.models import Category, Document, Tag, generate_ulid
from missionlog.models import FuelType
from tankgauge.models import Store, StoreTankMapping, TankEstimation


class DMSChartStorageService:
    """Manage tank chart PDF lifecycle in DMS."""

    def __init__(self) -> None:
        user_model = get_user_model()
        self.system_user, _ = user_model.objects.get_or_create(
            username="system",
            defaults={
                "first_name": "System",
                "last_name": "Automated",
                "is_staff": False,
                "is_active": True,
            },
        )
        self.tank_chart_category, _ = Category.objects.get_or_create(
            slug="tankchart",
            defaults={"name": "Tank Chart", "active": True, "sort_order": 10},
        )
        self.tank_chart_tag, _ = Tag.objects.get_or_create(
            slug="tankchart",
            defaults={"name": "Tank Chart"},
        )

    def find_existing(
        self,
        *,
        store_num: int,
        fuel_type: str,
        tank_index: int,
    ) -> Document | None:
        filename = self._build_original_filename(
            store_num=store_num,
            fuel_type=fuel_type,
            tank_index=tank_index,
        )
        return (
            Document.objects.filter(
                original_filename=filename,
                category=self.tank_chart_category,
                status="ACTIVE",
            )
            .order_by("-uploaded_at")
            .first()
        )

    def find_existing_store(self, *, store_num: int) -> Document | None:
        filename = self._build_store_original_filename(store_num=store_num)
        return (
            Document.objects.filter(
                original_filename=filename,
                category=self.tank_chart_category,
                status="ACTIVE",
            )
            .order_by("-uploaded_at")
            .first()
        )

    def is_stale(
        self,
        *,
        document: Document,
        store_num: int,
        tank_index: int,
    ) -> bool:
        mapping = (
            StoreTankMapping.objects.select_related("store", "tank_type")
            .filter(store__store_num=store_num, tank_index=tank_index)
            .first()
        )
        if not mapping:
            return True

        latest_ticket = (
            VeederTicket.objects.filter(store=mapping.store)
            .order_by("-uploaded_at")
            .values_list("uploaded_at", flat=True)
            .first()
        )
        latest_estimation = (
            TankEstimation.objects.filter(tank_mapping=mapping)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )

        if latest_ticket and latest_ticket > document.uploaded_at:
            return True
        if latest_estimation and latest_estimation > document.uploaded_at:
            return True

        return False

    def is_store_stale(self, *, document: Document, store_num: int) -> bool:
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            return True

        mappings = list(
            StoreTankMapping.objects.select_related("tank_type")
            .filter(store=store)
            .order_by("tank_index", "id")
        )
        if not mappings:
            return True

        for mapping in mappings:
            if self._tank_updated_after(
                mapping=mapping,
                uploaded_at=document.uploaded_at,
            ):
                return True

        return False

    def store(
        self,
        *,
        store_num: int,
        fuel_type: str,
        tank_index: int,
        pdf_bytes: bytes,
        metadata: dict,
    ) -> Document:
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            raise ValueError(f"Store {store_num} not found.")

        filename = self._build_original_filename(
            store_num=store_num,
            fuel_type=fuel_type,
            tank_index=tank_index,
        )

        metadata = self._with_tank_validity_metadata(
            metadata=metadata, store_num=store_num, tank_index=tank_index
        )
        with transaction.atomic():
            self.delete(
                store_num=store_num,
                fuel_type=fuel_type,
                tank_index=tank_index,
            )

            ulid_value = generate_ulid()
            year = datetime.now(tz=UTC).strftime("%Y")
            file_path = f"documents/{year}/{ulid_value}.pdf"
            store_content_type = ContentType.objects.get_for_model(Store)
            title = (
                f"Tank Field Chart - Store {store_num}, Tank {tank_index} ({fuel_type})"
            )

            document = Document.objects.create(
                title=title,
                original_filename=filename,
                stored_filename=f"{ulid_value}.pdf",
                file_path=file_path,
                mime_type="application/pdf",
                file_size=len(pdf_bytes),
                sha256=sha256(pdf_bytes).hexdigest(),
                uploaded_by=self.system_user,
                status="ACTIVE",
                category=self.tank_chart_category,
                content_type=store_content_type,
                object_id=str(store.pk),
                is_public=True,
                operational_state=self._operational_state(metadata),
                invalidation_reason=metadata.get("invalidation_reason", ""),
                source_profile_version=metadata.get("profile_version"),
                source_estimate_version=metadata.get("estimation_id"),
                description=json.dumps(metadata),
            )

            tags_to_add = [self.tank_chart_tag]
            fuel_tag = self._resolve_fuel_tag(fuel_type=fuel_type)
            if fuel_tag:
                tags_to_add.append(fuel_tag)
            if store.state:
                state_slug = slugify(store.state)
                state_tag, _ = Tag.objects.get_or_create(
                    slug=state_slug,
                    defaults={"name": store.state.upper()},
                )
                tags_to_add.append(state_tag)
            document.tags.add(*tags_to_add)

            default_storage.save(document.file_path, ContentFile(pdf_bytes))

        return document

    def store_store_chart(
        self,
        *,
        store_num: int,
        pdf_bytes: bytes,
        metadata: dict,
    ) -> Document:
        store = Store.objects.filter(store_num=store_num).first()
        if not store:
            raise ValueError(f"Store {store_num} not found.")

        filename = self._build_store_original_filename(store_num=store_num)

        metadata = self._with_store_validity_metadata(
            metadata=metadata, store_num=store_num
        )
        with transaction.atomic():
            self.delete_store(store_num=store_num)

            ulid_value = generate_ulid()
            year = datetime.now(tz=UTC).strftime("%Y")
            file_path = f"documents/{year}/{ulid_value}.pdf"
            store_content_type = ContentType.objects.get_for_model(Store)
            title = f"Store Field Chart - Store {store_num}"

            document = Document.objects.create(
                title=title,
                original_filename=filename,
                stored_filename=f"{ulid_value}.pdf",
                file_path=file_path,
                mime_type="application/pdf",
                file_size=len(pdf_bytes),
                sha256=sha256(pdf_bytes).hexdigest(),
                uploaded_by=self.system_user,
                status="ACTIVE",
                category=self.tank_chart_category,
                content_type=store_content_type,
                object_id=str(store.pk),
                is_public=True,
                operational_state=self._operational_state(metadata),
                invalidation_reason=metadata.get("invalidation_reason", ""),
                source_profile_version=metadata.get("profile_version"),
                source_estimate_version=metadata.get("estimation_id"),
                description=json.dumps(metadata),
            )

            tags_to_add = [self.tank_chart_tag]
            if store.state:
                state_slug = slugify(store.state)
                state_tag, _ = Tag.objects.get_or_create(
                    slug=state_slug,
                    defaults={"name": store.state.upper()},
                )
                tags_to_add.append(state_tag)
            document.tags.add(*tags_to_add)

            default_storage.save(document.file_path, ContentFile(pdf_bytes))

        return document

    def delete(self, *, store_num: int, fuel_type: str, tank_index: int) -> None:
        existing = self.find_existing(
            store_num=store_num,
            fuel_type=fuel_type,
            tank_index=tank_index,
        )
        if not existing:
            return

        existing.status = "SUPERSEDED"
        existing.operational_state = "SUPERSEDED"
        existing.is_public = False
        existing.save(
            update_fields=["status", "operational_state", "is_public", "updated_at"]
        )

    def delete_store(self, *, store_num: int) -> None:
        existing = self.find_existing_store(store_num=store_num)
        if not existing:
            return

        existing.status = "SUPERSEDED"
        existing.operational_state = "SUPERSEDED"
        existing.is_public = False
        existing.save(
            update_fields=["status", "operational_state", "is_public", "updated_at"]
        )

    def get_download_url(
        self,
        *,
        store_num: int,
        fuel_type: str,
        tank_index: int,
    ) -> str | None:
        existing = self.find_existing(
            store_num=store_num,
            fuel_type=fuel_type,
            tank_index=tank_index,
        )
        if not existing:
            return None
        if self.document_safety_reason(existing):
            return None
        return reverse("dms:document_download", kwargs={"ulid": existing.id})

    def get_store_download_url(self, *, store_num: int) -> str | None:
        existing = self.find_existing_store(store_num=store_num)
        if not existing:
            return None
        if self.document_safety_reason(existing):
            return None
        return reverse("dms:document_download", kwargs={"ulid": existing.id})

    def document_safety_reason(self, document: Document) -> str | None:
        """Return a stable blocking reason for a known unsafe chart document."""
        if document.operational_state == "UNSAFE":
            self._record_invalidation(
                document, "UNSAFE", document.invalidation_reason or "unsafe"
            )
            return "document_marked_unsafe"
        if document.operational_state in {"STALE", "SUPERSEDED"}:
            self._record_invalidation(
                document, document.operational_state, "document_not_current"
            )
            return "document_not_current"
        metadata = self._parse_metadata(document=document)
        if metadata.get("estimate_status") in {"STALE", "UNSAFE", "BLOCKED"}:
            self._record_invalidation(document, "UNSAFE", "estimate_unsafe")
            return "estimate_unsafe"
        if metadata.get("profile_status") == "REVIEW_REQUIRED":
            self._record_invalidation(document, "UNSAFE", "profile_unsafe")
            return "profile_unsafe"
        if (
            metadata.get("profile_status") == "UNAVAILABLE"
            and metadata.get("estimate_status") != "LEGACY_UNVERIFIED"
        ):
            self._record_invalidation(document, "UNSAFE", "profile_unsafe")
            return "profile_unsafe"

        store_num = metadata.get("store_num")
        tank_index = metadata.get("tank_index")
        if store_num is not None and tank_index is not None:
            if self.is_stale(
                document=document,
                store_num=int(store_num),
                tank_index=int(tank_index),
            ):
                self._record_invalidation(
                    document, "STALE", "source_data_newer_than_document"
                )
                return "source_data_newer_than_document"
            mapping = StoreTankMapping.objects.filter(
                store__store_num=int(store_num), tank_index=int(tank_index)
            ).first()
            if not mapping:
                self._record_invalidation(document, "STALE", "tank_mapping_missing")
                return "tank_mapping_missing"
            if metadata.get("profile_version") is not None and (
                mapping.profile_version != metadata["profile_version"]
            ):
                self._record_invalidation(document, "STALE", "profile_version_changed")
                return "profile_version_changed"
            estimation_id = metadata.get("estimation_id")
            if estimation_id is not None:
                current = (
                    TankEstimation.objects.filter(tank_mapping=mapping, is_active=True)
                    .order_by("-created_at")
                    .first()
                )
                if current is None or current.id != estimation_id:
                    self._record_invalidation(document, "STALE", "estimate_changed")
                    return "estimate_changed"
            return None

        for item in metadata.get("source_validity", ()):
            if item.get("estimate_status") in {"STALE", "UNSAFE", "BLOCKED"}:
                self._record_invalidation(document, "UNSAFE", "estimate_unsafe")
                return "estimate_unsafe"
            if item.get("profile_status") == "REVIEW_REQUIRED":
                self._record_invalidation(document, "UNSAFE", "profile_unsafe")
                return "profile_unsafe"
            if (
                item.get("profile_status") == "UNAVAILABLE"
                and item.get("estimate_status") != "LEGACY_UNVERIFIED"
            ):
                self._record_invalidation(document, "UNSAFE", "profile_unsafe")
                return "profile_unsafe"
        if store_num is not None and self.is_store_stale(
            document=document, store_num=int(store_num)
        ):
            self._record_invalidation(
                document, "STALE", "source_data_newer_than_document"
            )
            return "source_data_newer_than_document"
        return None

    @staticmethod
    def _record_invalidation(document: Document, state: str, reason: str) -> None:
        """Persist runtime invalidation metadata while retaining the artifact."""
        if (
            document.operational_state == state
            and document.invalidation_reason == reason
            and document.invalidated_at is not None
        ):
            return
        document.operational_state = state
        document.invalidation_reason = reason
        document.invalidated_at = document.invalidated_at or django_timezone.now()
        document.save(
            update_fields=[
                "operational_state",
                "invalidation_reason",
                "invalidated_at",
                "updated_at",
            ]
        )

    def batch_generate(self, *, store_num: int, force: bool = False) -> dict:
        from tankcharts.rendering import PDFRenderer
        from tankcharts.services.field_chart_service import TankFieldChartService

        chart_service = TankFieldChartService()
        renderer = PDFRenderer()

        started_at = datetime.now(tz=UTC)
        summary = {
            "charts_generated": 0,
            "charts_skipped": 0,
            "charts_updated": 0,
            "charts_failed": 0,
            "failures": [],
            "total_time_ms": 0,
        }

        mappings = list(
            StoreTankMapping.objects.select_related("store")
            .filter(store__store_num=store_num)
            .order_by("tank_index")
        )

        for mapping in mappings:
            fuel_type = mapping.fuel_type or "unknown"
            try:
                existing = self.find_existing(
                    store_num=store_num,
                    fuel_type=fuel_type,
                    tank_index=mapping.tank_index,
                )

                if (
                    existing
                    and not force
                    and not self.is_stale(
                        document=existing,
                        store_num=store_num,
                        tank_index=mapping.tank_index,
                    )
                ):
                    summary["charts_skipped"] += 1
                    continue

                chart = chart_service.build(
                    store_num=store_num,
                    tank_index=mapping.tank_index,
                )
                pdf_bytes = renderer.render(chart)
                metadata = {
                    "store_num": chart.store_num,
                    "tank_index": chart.tank_index,
                    "fuel_type": chart.fuel_type,
                    "veeder_count": chart.veeder_observation_count,
                    "estimation_id": chart.estimation_id,
                    "generated_at": chart.generated_at.isoformat(),
                }
                self.store(
                    store_num=chart.store_num,
                    fuel_type=chart.fuel_type,
                    tank_index=chart.tank_index,
                    pdf_bytes=pdf_bytes,
                    metadata=metadata,
                )

                if existing:
                    summary["charts_updated"] += 1
                else:
                    summary["charts_generated"] += 1
            except Exception as error:
                summary["charts_failed"] += 1
                summary["failures"].append(
                    {
                        "tank_index": mapping.tank_index,
                        "fuel_type": fuel_type,
                        "error": str(error),
                    }
                )

        elapsed = datetime.now(tz=UTC) - started_at
        summary["total_time_ms"] = int(elapsed.total_seconds() * 1000)
        return summary

    def _build_original_filename(
        self,
        *,
        store_num: int,
        fuel_type: str,
        tank_index: int,
    ) -> str:
        fuel_abbreviation = self._resolve_fuel_abbreviation(fuel_type=fuel_type)
        return f"{store_num}_{fuel_abbreviation}_T{tank_index}.pdf"

    def _build_store_original_filename(self, *, store_num: int) -> str:
        return f"{store_num}_STORE.pdf"

    def _resolve_fuel_abbreviation(self, *, fuel_type: str) -> str:
        fuel_type_obj = FuelType.objects.filter(name__iexact=fuel_type).first()
        if fuel_type_obj and fuel_type_obj.abbreviation:
            return fuel_type_obj.abbreviation.upper()

        fallback = (fuel_type or "UNK")[:3].upper()
        return fallback or "UNK"

    def _resolve_fuel_tag(self, *, fuel_type: str) -> Tag | None:
        abbreviation = self._resolve_fuel_abbreviation(fuel_type=fuel_type)
        if not abbreviation:
            return None
        slug = slugify(abbreviation)
        tag, _ = Tag.objects.get_or_create(
            slug=slug,
            defaults={"name": abbreviation},
        )
        return tag

    def _parse_metadata(self, *, document: Document) -> dict:
        if not document.description:
            return {}
        try:
            parsed = json.loads(document.description)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
        return {}

    @staticmethod
    def _operational_state(metadata: dict) -> str:
        """Persist the conservative state used by runtime artifact checks."""
        if metadata.get("estimate_status") in {"UNSAFE", "BLOCKED"}:
            return "UNSAFE"
        if metadata.get("profile_status") in {"UNSAFE", "REVIEW_REQUIRED"}:
            return "UNSAFE"
        return "USABLE"

    def _with_tank_validity_metadata(
        self, *, metadata: dict, store_num: int, tank_index: int
    ) -> dict:
        mapping = (
            StoreTankMapping.objects.filter(
                store__store_num=store_num, tank_index=tank_index
            )
            .order_by("id")
            .first()
        )
        estimate = (
            TankEstimation.objects.filter(tank_mapping=mapping, is_active=True)
            .order_by("-created_at")
            .first()
            if mapping
            else None
        )
        return {
            **metadata,
            "store_num": store_num,
            "tank_index": tank_index,
            "profile_version": (
                mapping.profile_version if mapping else metadata.get("profile_version")
            ),
            "profile_status": (
                mapping.profile_status if mapping else metadata.get("profile_status")
            ),
            "estimate_status": (
                estimate.estimate_status
                if estimate
                else metadata.get("estimate_status")
            ),
            "estimation_id": estimate.id if estimate else metadata.get("estimation_id"),
        }

    def _with_store_validity_metadata(self, *, metadata: dict, store_num: int) -> dict:
        validity = []
        mappings = StoreTankMapping.objects.filter(store__store_num=store_num).order_by(
            "tank_index", "id"
        )
        for mapping in mappings:
            estimate = (
                TankEstimation.objects.filter(tank_mapping=mapping, is_active=True)
                .order_by("-created_at")
                .first()
            )
            validity.append(
                {
                    "mapping_id": mapping.id,
                    "tank_index": mapping.tank_index,
                    "profile_version": mapping.profile_version,
                    "profile_status": mapping.profile_status,
                    "estimate_id": estimate.id if estimate else None,
                    "estimate_status": estimate.estimate_status if estimate else None,
                }
            )
        return {**metadata, "store_num": store_num, "source_validity": validity}

    def _tank_updated_after(
        self,
        *,
        mapping: StoreTankMapping,
        uploaded_at,
    ) -> bool:
        latest_ticket = (
            VeederTicket.objects.filter(store=mapping.store)
            .order_by("-uploaded_at")
            .values_list("uploaded_at", flat=True)
            .first()
        )
        latest_estimation = (
            TankEstimation.objects.filter(tank_mapping=mapping)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if latest_ticket and latest_ticket > uploaded_at:
            return True
        if latest_estimation and latest_estimation > uploaded_at:
            return True
        return False
