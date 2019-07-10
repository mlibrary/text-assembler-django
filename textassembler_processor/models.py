from django.db import models

class api_log(models.Model):
    log_id = models.AutoField(primary_key=True)
    request_url = models.TextField()
    request_type = models.CharField(max_length=10) # POST, GET
    response_code = models.CharField(max_length=10)
    num_results = models.IntegerField()
    is_download = models.BooleanField() # set to true if download, false if search
    request_date = models.DateTimeField(auto_now=True)
