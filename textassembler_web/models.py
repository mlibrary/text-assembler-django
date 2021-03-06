'''
Database models for the web interface
'''
from enum import Enum
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import pre_delete

class CallTypeChoice(Enum):
    '''
    API Call Types
    '''
    SRC = "Sources"
    SRH = "Search"
    DWL = "Download"

class sources(models.Model): # pylint: disable=invalid-name
    '''
    Searchable sources in the LexisNexis API
    '''
    source_id = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255)
    active = models.BooleanField(default=False)

class available_formats(models.Model): # pylint: disable=invalid-name
    '''
    Available download formats
    '''
    format_id = models.AutoField(primary_key=True)
    format_name = models.CharField(max_length=20)
    help_text = models.CharField(max_length=255)

class available_sort_orders(models.Model): # pylint: disable=invalid-name
    '''
    Available sort orders for searches
    '''
    sort_id = models.AutoField(primary_key=True)
    sort_value = models.CharField(max_length=30, null=False) # used for calling the api
    sort_label = models.CharField(max_length=255) # used for UI display
    removed = models.DateTimeField(null=True) # used when we remove an available sort option

class searches(models.Model): # pylint: disable=invalid-name
    '''
    User searches and their status
    '''
    search_id = models.AutoField(primary_key=True)
    userid = models.CharField(max_length=50) # user ID for the user requesting the search
    date_submitted = models.DateTimeField(auto_now_add=True) # date the user submitted the search request
    update_date = models.DateTimeField(auto_now_add=True) # time the search was last updated, i.e. more progress made on downloads
    query = models.TextField() # search term/query to use in the LN API
    sort_order = models.ForeignKey("available_sort_orders", models.SET_NULL, null=True) # the sort order for the search
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
    last_save_dir = models.CharField(max_length=1024, null=True) # the last directory, relative to the save path, where a result file was saved
    error_message = models.TextField(null=True)
    failed_date = models.DateTimeField(null=True) # date the search failed
    deleted = models.BooleanField(default=False) # flag the search for deletion

    def __str__(self):
        '''
        Printable string of the object with basic information
        '''
        obj_str = f"(ID: {self.search_id}) userid: {self.userid}. Date Submitted: {self.date_submitted}. "
        obj_str += f"Date Started: {self.date_started}. Date Completed: {self.date_completed}. "
        obj_str += f"Number of Results Downloaded: {self.num_results_downloaded}. Query: {self.query}"

        return obj_str

class filters(models.Model): # pylint: disable=invalid-name
    '''
    Filters selected for the search
    '''
    search_id = models.ForeignKey("searches", models.CASCADE)
    filter_name = models.CharField(max_length=255) # name of the filter in the LN API
    filter_value = models.CharField(max_length=255)

class download_formats(models.Model): # pylint: disable=invalid-name
    '''
    Selected download formats for the search
    '''
    search_id = models.ForeignKey("searches", models.CASCADE)
    format_id = models.ForeignKey("available_formats", models.CASCADE)

class administrative_users(models.Model): # pylint: disable=invalid-name
    '''
    Administrative users
    '''
    userid = models.CharField(max_length=50)

class api_limits(models.Model): # pylint: disable=invalid-name
    '''
    Controls number of API calls per minute/hour/day
    '''
    limit_type = models.CharField(
        max_length=20,
        choices=[(tag, tag.value) for tag in CallTypeChoice],
        primary_key=True,
    )
    limit_per_minute = models.IntegerField(default=0)
    limit_per_hour = models.IntegerField(default=0)
    limit_per_day = models.IntegerField(default=0)
    remaining_per_minute = models.IntegerField(default=0)
    remaining_per_hour = models.IntegerField(default=0)
    remaining_per_day = models.IntegerField(default=0)
    reset_on_minute = models.DateTimeField(null=True)
    reset_on_hour = models.DateTimeField(null=True)
    reset_on_day = models.DateTimeField(null=True)
    update_date = models.DateTimeField(auto_now=True)

class historical_searches(models.Model): # pylint: disable=invalid-name
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
    deleted = models.BooleanField(default=False)
    date_deleted = models.DateTimeField(auto_now_add=True)

@receiver(pre_delete, sender=searches)
def save_historical_search_data(sender, instance, **kwargs): # pylint: disable=unused-argument
    '''
    Once a record is deleted from the searches table, add it to the historical_searches table.
    '''
    search_obj = historical_searches(search_id=instance.search_id, date_submitted=instance.date_submitted,
                                     update_date=instance.update_date, query=instance.query,
                                     date_started=instance.date_started, date_completed=instance.date_completed,
                                     num_results_downloaded=instance.num_results_downloaded,
                                     num_results_in_search=instance.num_results_in_search,
                                     skip_value=instance.skip_value, date_started_compression=instance.date_started_compression,
                                     date_completed_compression=instance.date_completed_compression,
                                     user_notified=instance.user_notified, run_time_seconds=instance.run_time_seconds,
                                     retry_count=instance.retry_count, error_message=instance.error_message,
                                     failed_date=instance.failed_date, deleted=instance.deleted)
    search_obj.save()
