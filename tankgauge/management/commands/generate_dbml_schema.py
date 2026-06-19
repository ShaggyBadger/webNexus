from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models


PROJECT_APP_LABELS = {
    "accounts",
    "atg",
    "dms",
    "homepage",
    "missionlog",
    "siteintel",
    "tankgauge",
}


EXTERNAL_TABLE_STUBS = (
    "Table auth_user {\n  id int [pk]\n}",
    "Table django_content_type {\n  id int [pk]\n}",
)


class Command(BaseCommand):
    help = "Generate instructions/database_schema.dbml from Django models."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--output",
            default="instructions/database_schema.dbml",
            help="Output path for DBML schema snapshot.",
        )
        parser.add_argument(
            "--stdout",
            action="store_true",
            help="Print DBML to stdout instead of writing file.",
        )

    def handle(self, *args, **options) -> None:
        dbml_text = self._build_dbml()

        if options["stdout"]:
            self.stdout.write(dbml_text)
            return

        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dbml_text, encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(f"DBML schema written to {output_path.as_posix()}")
        )

    def _build_dbml(self) -> str:
        models_list = self._get_project_models()

        lines = [
            "// Master database schema for project-owned Django models.",
            "// Format: DBML",
            "// Scope: accounts, atg, dms, missionlog, siteintel, tankgauge",
            "// Note: auth_user and django_content_type are included as external dependency stubs.",
            "",
        ]

        for stub in EXTERNAL_TABLE_STUBS:
            lines.append(stub)
            lines.append("")

        refs: list[tuple[str, str, str, str, bool]] = []

        for model in models_list:
            lines.extend(self._render_table(model, refs))
            lines.append("")

        for ref in self._render_refs(refs):
            lines.append(ref)

        return "\n".join(lines).rstrip() + "\n"

    def _get_project_models(self) -> list[type[models.Model]]:
        filtered_models: list[type[models.Model]] = []

        for model in apps.get_models(include_auto_created=True):
            model_meta = model._meta
            if model_meta.app_label not in PROJECT_APP_LABELS:
                continue
            if model_meta.proxy or model_meta.swapped:
                continue
            filtered_models.append(model)

        return sorted(
            filtered_models, key=lambda m: (m._meta.app_label, m._meta.db_table)
        )

    def _render_table(
        self,
        model: type[models.Model],
        refs: list[tuple[str, str, str, str, bool]],
    ) -> list[str]:
        model_meta = model._meta
        out_lines = [f"Table {model_meta.db_table} {{"]

        for field in model_meta.local_fields:
            out_lines.append(self._render_field_line(field))
            self._collect_ref(model_meta.db_table, field, refs)

        for unique_tuple in model_meta.unique_together:
            columns = ", ".join(unique_tuple)
            out_lines.append(f'  Note: "unique_together: ({columns})"')

        for constraint in model_meta.constraints:
            if isinstance(constraint, models.UniqueConstraint):
                columns = ", ".join(constraint.fields)
                out_lines.append(
                    f'  Note: "unique_constraint {constraint.name}: ({columns})"'
                )

        out_lines.append("}")
        return out_lines

    def _render_field_line(self, field: models.Field) -> str:
        field_name = field.column
        field_type = self._dbml_type(field)
        attrs: list[str] = []

        if field.primary_key:
            attrs.append("pk")
            if field.get_internal_type() in {
                "AutoField",
                "BigAutoField",
                "SmallAutoField",
            }:
                attrs.append("increment")

        if not field.null and not field.primary_key:
            attrs.append("not null")

        if field.unique and not field.primary_key:
            attrs.append("unique")

        max_length = getattr(field, "max_length", None)
        if max_length and field_type == "varchar":
            attrs.append(f'note: "max_length={max_length}"')

        attr_suffix = f" [{', '.join(attrs)}]" if attrs else ""
        return f"  {field_name} {field_type}{attr_suffix}"

    def _collect_ref(
        self,
        source_table: str,
        field: models.Field,
        refs: list[tuple[str, str, str, str, bool]],
    ) -> None:
        if (
            not field.is_relation
            or not field.remote_field
            or not field.remote_field.model
        ):
            return

        target_model = field.remote_field.model
        refs.append(
            (
                source_table,
                field.column,
                target_model._meta.db_table,
                target_model._meta.pk.column,
                isinstance(field, models.OneToOneField),
            )
        )

    def _render_refs(self, refs: list[tuple[str, str, str, str, bool]]) -> list[str]:
        unique_refs = sorted(set(refs))
        rendered: list[str] = []

        for (
            source_table,
            source_column,
            target_table,
            target_column,
            is_one_to_one,
        ) in unique_refs:
            operator = "-" if is_one_to_one else ">"
            rendered.append(
                f"Ref: {source_table}.{source_column} {operator} {target_table}.{target_column}"
            )

        return rendered

    def _dbml_type(self, field: models.Field) -> str:
        if field.is_relation and getattr(field, "target_field", None):
            return self._simple_dbml_type(field.target_field.get_internal_type())

        return self._simple_dbml_type(field.get_internal_type())

    def _simple_dbml_type(self, internal_type: str) -> str:
        if internal_type in {
            "AutoField",
            "BigAutoField",
            "SmallAutoField",
            "IntegerField",
            "PositiveIntegerField",
            "PositiveSmallIntegerField",
            "SmallIntegerField",
            "BigIntegerField",
        }:
            return "int"

        if internal_type in {"FloatField", "DecimalField"}:
            return "float"

        if internal_type in {"BooleanField", "NullBooleanField"}:
            return "boolean"

        if internal_type == "DateTimeField":
            return "datetime"

        if internal_type == "DateField":
            return "date"

        if internal_type == "TimeField":
            return "time"

        if internal_type == "TextField":
            return "text"

        if internal_type == "JSONField":
            return "json"

        return "varchar"
