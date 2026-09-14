from django.db import models


class StoreType(models.Model):
    """Standardized store or brand name available for future store links."""

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name
