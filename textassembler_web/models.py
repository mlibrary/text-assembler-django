from django.db import models


class sources(models.Model):
    """Searchable sources in the LexisNexis API"""
    source_id = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255)

class available_formats(models.Model):
    format_id = models.AutoField(primary_key=True)
    format_name = models.CharField(max_length=20)

class searches(models.Model):
    search_id = models.AutoField(primary_key=True)
    userid = models.CharField(max_length=50) # user ID for the user requesting the search
    date_submitted = models.DateTimeField(auto_now_add=True) # date the user submitted the search request
    update_date = models.DateTimeField() # time the search was last updated, i.e. more progress made on downloads
    query = models.TextField() # search term/query to use in the LN API
    date_startd = models.DateTimeField() # date the search actually started
    date_completed = models.DateTimeField() # date that the download of all results completed
    num_results_downloaded = models.IntegerField() # total number of results already downloaded from the search
    num_results_in_search = models.IntegerField()  # total number of results the search is expected to have
    skip_value = models.IntegerField() # used for the LN API calls to track how far into the search we are
    date_started_compression = models.DateTimeField() # need to track separately since this can take a while with long searches
    date_completed_compression = models.DateTimeField() # date the compression of all the search results completed
    user_notified = models.BooleanField(default=False) # flag indicating if the user has been send the email notification yet
    run_time_mins = models.IntegerField() # number of minutes the download has been actively running (not including waiting in queue)

class filters(models.Model):
    search_id = models.ForeignKey("searches", models.CASCADE)
    filter_name = models.CharField(max_length=255) # name of the filter in the LN API
    filter_value = models.CharField(max_length=255)

class download_formats(models.Model):
    search_id = models.ForeignKey("searches", models.CASCADE)
    format_id = models.ForeignKey("available_formats", models.CASCADE)
