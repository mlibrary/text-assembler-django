from django.db import models
from django.dispatch import receiver
from django.db.models.signals import pre_delete


class sources(models.Model):
    """Searchable sources in the LexisNexis API"""
    source_id = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255)
    active = models.BooleanField(default=False)

class available_formats(models.Model):
    format_id = models.AutoField(primary_key=True)
    format_name = models.CharField(max_length=20)
    help_text = models.CharField(max_length=255)

class searches(models.Model):
    search_id = models.AutoField(primary_key=True)
    userid = models.CharField(max_length=50) # user ID for the user requesting the search
    date_submitted = models.DateTimeField(auto_now_add=True) # date the user submitted the search request
    update_date = models.DateTimeField(auto_now_add=True) # time the search was last updated, i.e. more progress made on downloads
    query = models.TextField() # search term/query to use in the LN API
    date_started = models.DateTimeField(null=True) # date the search actually started
    date_completed = models.DateTimeField(null=True) # date that the download of all results completed
    num_results_downloaded = models.IntegerField(default=0) # total number of results already downloaded from the search
    num_results_in_search = models.IntegerField(default=0)  # total number of results the search is expected to have
    skip_value = models.IntegerField(default=0) # used for the LN API calls to track how far into the search we are
    date_started_compression = models.DateTimeField(null=True) # need to track separately since this can take a while with long searches
    date_completed_compression = models.DateTimeField(null=True) # date the compression of all the search results completed
    user_notified = models.BooleanField(default=False) # flag indicating if the user has been send the email notification yet
    run_time_seconds = models.IntegerField(default=0) # number of seconds the download has been actively running (not including waiting in queue)
    retry_count = models.IntegerField(default=0) # number of times a call to the API failed
    error_message = models.TextField(null=True)
    failed_date = models.DateTimeField(null=True) # date the search failed

    def __str__(self):
        return "(ID: {0}) userid: {1}. Date Submitted: {2}. Date Started: {3}. Date Completed: {4}. Number of Results Downloaded: {5}. Query: {6}".format(self.search_id, self.userid, 
            self.date_submitted, 
            self.date_started, 
            self.date_completed, 
            str(self.num_results_downloaded), self.query)

class filters(models.Model):
    search_id = models.ForeignKey("searches", models.CASCADE)
    filter_name = models.CharField(max_length=255) # name of the filter in the LN API
    filter_value = models.CharField(max_length=255)

class download_formats(models.Model):
    search_id = models.ForeignKey("searches", models.CASCADE)
    format_id = models.ForeignKey("available_formats", models.CASCADE)

class historical_searches(models.Model):
    '''
    Used to store deleted searches for later querying for reporting purposes.
    '''
    search_id = models.IntegerField(default=0)
    date_submitted = models.DateTimeField(null=True)
    update_date = models.DateTimeField(null=True)
    query = models.TextField()
    date_started = models.DateTimeField(null=True)
    date_completed = models.DateTimeField(null=True)
    num_results_downloaded = models.IntegerField(default=0)
    num_results_in_search = models.IntegerField(default=0)
    skip_value = models.IntegerField(default=0) 
    date_started_compression = models.DateTimeField(null=True) 
    date_completed_compression = models.DateTimeField(null=True)
    user_notified = models.BooleanField(default=False)
    run_time_seconds = models.IntegerField(default=0)
    retry_count = models.IntegerField(default=0) 
    error_message = models.TextField(null=True)
    failed_date = models.DateTimeField(null=True)
    date_deleted = models.DateTimeField(auto_now_add=True)

@receiver(pre_delete, sender=searches)
def save_historical_search_data(sender, instance, **kwargs):
    '''
    Once a record is deleted from the searches table, add it to the historical_searches table.
    '''
    search_obj = historical_searches( search_id=instance.search_id, date_submitted=instance.date_submitted, update_date=instance.update_date,
        query=instance.query, date_started=instance.date_started, date_completed=instance.date_completed,
        num_results_downloaded=instance.num_results_downloaded, num_results_in_search=instance.num_results_in_search,
        skip_value=instance.skip_value, date_started_compression=instance.date_started_compression,
        date_completed_compression=instance.date_completed_compression, user_notified=instance.user_notified,
        run_time_seconds=instance.run_time_seconds, retry_count=instance.retry_count,
        error_message=instance.error_message, failed_date=instance.failed_date)
    search_obj.save()
