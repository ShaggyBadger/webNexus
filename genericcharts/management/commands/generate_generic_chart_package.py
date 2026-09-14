from django.core.management.base import BaseCommand

from genericcharts.services.generation_service import run_generation


class Command(BaseCommand):
    help = "Run one admin-created CoreStarterPack generation job."

    def add_arguments(self, parser):
        parser.add_argument("--generation-id", type=int, required=True)

    def handle(self, *args, **options):
        generation = run_generation(options["generation_id"])
        if generation is None:
            self.stderr.write(self.style.ERROR("Generation job was not found."))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Generation {generation.id}: {generation.get_status_display()}"
            )
        )
