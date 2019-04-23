from django.db import models

class limits(models.Model):
    """Contains the search limitations with the LexisNexis API."""
    searches_per_minute = models.IntegerField()
    searches_per_hour = models.IntegerField()
    searches_per_day = models.IntegerField()
    downloads_per_minute = models.IntegerField()
    downloads_per_hour = models.IntegerField()
    downloads_per_day = models.IntegerField()
    weekday_start_time = models.TimeField()
    weekday_end_time = models.TimeField()
    weekend_start_time = models.TimeField()
    weekend_end_time = models.TimeField()

class api_log(models.Model):
    log_id = models.AutoField(primary_key=True)
    request_url = models.CharField(max_length=500)
    request_type = models.CharField(max_length=10) # POST, GET
    response_code = models.CharField(max_length=10)
    num_results = models.IntegerField()
    is_download = models.BooleanField() # set to true if download, false if search
    request_date = models.DateTimeField(auto_now=True)
