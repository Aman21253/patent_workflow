from django.core.management.base import BaseCommand
from core.models import Patent, Attorney, PatentAttorney
from core.services import fetch_patents


class Command(BaseCommand):
    help = "Import patents from Solr"

    def handle(self, *args, **kwargs):
        docs = fetch_patents()

        for doc in docs:
            app_id = doc.get("id")
            if not app_id:
                continue

            patent, _ = Patent.objects.update_or_create(
                application_id=app_id,
                defaults={
                    "title": doc.get("title"),
                    "applicant_name": doc.get("first_named_applicant"),
                    "inventor_name": doc.get("first_named_inventor"),
                    "gau": doc.get("gau"),
                    "status": doc.get("application_status"),
                }
            )

            names = doc.get("all_attorney_names") or []
            regs = doc.get("all_attorney_registration_numbers") or []

            if isinstance(names, str):
                names = [names]

            if isinstance(regs, str):
                regs = [regs]

            for i in range(min(len(names), len(regs))):
                attorney, _ = Attorney.objects.get_or_create(
                    registration_no=str(regs[i]),
                    defaults={"name": names[i]},
                )

                PatentAttorney.objects.get_or_create(
                    patent=patent,
                    attorney=attorney
                )

        self.stdout.write(self.style.SUCCESS("✅ Data Imported Successfully"))