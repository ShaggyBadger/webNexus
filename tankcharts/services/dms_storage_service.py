import json
from datetime import UTC, datetime
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.urls import reverse
from django.utils.text import slugify

from atg.models import VeederTicket
from dms.models import Category, Document, Tag, generate_ulid
from missionlog.models import FuelType
from tankgauge.models import Store, StoreTankMapping, TankChart, TankEstimation


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

        metadata = self._parse_metadata(document=document)
        prior_official_row_count = metadata.get("official_row_count")
        if prior_official_row_count is None:
            return True

        current_official_row_count = self._official_row_count(mapping=mapping)
        return int(prior_official_row_count) != int(current_official_row_count)

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

        metadata = self._parse_metadata(document=document)
        prior_official_counts = metadata.get("official_row_counts")
        if not isinstance(prior_official_counts, dict):
            return True

        for mapping in mappings:
            if self._tank_updated_after(
                mapping=mapping,
                uploaded_at=document.uploaded_at,
            ):
                return True

            key = str(mapping.tank_index)
            if key not in prior_official_counts:
                return True

            current_count = self._official_row_count(mapping=mapping)
            if int(prior_official_counts[key]) != int(current_count):
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

        existing.status = "ARCHIVED"
        existing.save(update_fields=["status", "updated_at"])

    def delete_store(self, *, store_num: int) -> None:
        existing = self.find_existing_store(store_num=store_num)
        if not existing:
            return

        existing.status = "ARCHIVED"
        existing.save(update_fields=["status", "updated_at"])

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
        return reverse("dms:document_download", kwargs={"ulid": existing.id})

    def get_store_download_url(self, *, store_num: int) -> str | None:
        existing = self.find_existing_store(store_num=store_num)
        if not existing:
            return None
        return reverse("dms:document_download", kwargs={"ulid": existing.id})

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
                    "official_row_count": chart.official_row_count,
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

    def _official_row_count(self, *, mapping: StoreTankMapping) -> int:
        store_specific_count = TankChart.objects.filter(
            store=mapping.store,
            tank_index=mapping.tank_index,
            is_official=True,
        ).count()
        if store_specific_count > 0:
            return store_specific_count

        if not mapping.tank_type:
            return 0

        return TankChart.objects.filter(
            tank_type=mapping.tank_type,
            is_official=True,
        ).count()

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
