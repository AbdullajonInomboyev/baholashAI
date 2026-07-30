from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from academics.models import AcademicYear, Faculty, StudyForm
from academics.services.importer import import_curriculum


class Command(BaseCommand):
    help = "O‘quv reja Excel faylini import qiladi."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Excel fayl yo‘li")
        parser.add_argument("--faculty", default="Axborot texnologiyalari fakulteti")
        parser.add_argument("--year", default="2025-2026")
        parser.add_argument(
            "--form", choices=[c for c, _ in StudyForm.choices], action="append",
            help="Import qilinadigan ta'lim shakli (bir nechta marta berilishi mumkin).",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Fayl topilmadi: {path}")

        faculty, _ = Faculty.objects.get_or_create(name=options["faculty"])
        year, _ = AcademicYear.objects.get_or_create(faculty=faculty, title=options["year"])

        result = import_curriculum(year, str(path), forms=options.get("form"))

        self.stdout.write(self.style.SUCCESS(
            f"Yo‘nalish: {result['direction'].code} — {result['direction'].name}"
        ))
        self.stdout.write(f"Ta'lim shakllari: {', '.join(result['forms'])}")
        self.stdout.write(f"Jami yozilgan fan yozuvlari: {result['courses']}")
