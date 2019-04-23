from django.db import models


class sources(models.Model):
    """Searchable sources in the LexisNexis API"""
    source_id = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255)
