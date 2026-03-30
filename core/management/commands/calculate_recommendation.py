from django.core.management.base import BaseCommand
from core.models import Patent, PatentAttorney, Recommendation


class Command(BaseCommand):
    help = "Calculate attorney recommendations"

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 Calculating recommendations...")

        Recommendation.objects.all().delete()

        data = {}

        mappings = PatentAttorney.objects.select_related("patent", "attorney")

        for m in mappings:
            patent = m.patent
            attorney = m.attorney

            if not patent.gau:
                continue

            key = (attorney.registration_no, patent.gau)

            if key not in data:
                data[key] = {
                    "attorney": attorney,
                    "gau": patent.gau,
                    "total": 0,
                    "approved": 0,
                    "rejected": 0,
                    "pending": 0,
                }

            data[key]["total"] += 1

            status = (patent.status or "").lower()

            if any(word in status for word in [
                "docketed", "preexam", "processing", "classification"
            ]):
                continue
            
            if "grant" in status or "allow" in status:
                data[key]["approved"] += 1
            elif "reject" in status or "abandon" in status:
                data[key]["rejected"] += 1
            else:
                data[key]["pending"] += 1

        for d in data.values():
            total = d["total"]
            approved = d["approved"]

            success = (approved / total) * 100 if total > 0 else 0

            Recommendation.objects.create(
                attorney=d["attorney"],
                gau=d["gau"],
                total_cases=total,
                approved=d["approved"],
                rejected=d["rejected"],
                pending=d["pending"],
                success_rate=round(success, 2),
            )

        self.stdout.write("✅ Done!")