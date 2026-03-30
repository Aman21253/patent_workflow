from django.db import models


class Patent(models.Model):
    application_id = models.CharField(max_length=50, primary_key=True)
    title = models.TextField(blank=True, null=True)
    applicant_name = models.CharField(max_length=255, blank=True, null=True)
    inventor_name = models.CharField(max_length=255, blank=True, null=True)
    gau = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.application_id


class Attorney(models.Model):
    registration_no = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class PatentAttorney(models.Model):
    patent = models.ForeignKey(Patent, on_delete=models.CASCADE, related_name="attorneys_map")
    attorney = models.ForeignKey(Attorney, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("patent", "attorney")

class Recommendation(models.Model):
    attorney = models.ForeignKey(Attorney, on_delete=models.CASCADE)
    gau = models.CharField(max_length=20)

    total_cases = models.IntegerField(default=0)
    approved = models.IntegerField(default=0)
    rejected = models.IntegerField(default=0)
    pending = models.IntegerField(default=0)

    success_rate = models.FloatField(default=0)

    class Meta:
        unique_together = ('attorney', 'gau')