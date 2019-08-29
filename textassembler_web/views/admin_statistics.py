'''
Handles all web requests for the statistics page
'''
import datetime
import re
from django.utils import timezone
from django.utils.timezone import make_aware
from django.shortcuts import render, redirect
from django.db.models import Q
from django.apps import apps
from textassembler_web.utilities import get_is_admin
from textassembler_web.models import searches, historical_searches

def admin_statistics(request):
    '''
    Render the statistics page
    '''
    # Verify that the user is logged in and an admin
    if not request.session.get('userid', False) or not get_is_admin(request.session['userid']):
        return redirect('/login')

    # Default the date range to the current month
    from_date = timezone.now().replace(day=1)
    to_date = timezone.now()

    # Parse the provided range if available
    if 'FromDate' in request.POST and 'ToDate' in request.POST:
        from_date = make_aware(datetime.datetime.strptime(request.POST['FromDate'], '%Y-%m-%d'))
        to_date = make_aware(datetime.datetime.strptime(request.POST['ToDate'], '%Y-%m-%d'))

    # Remove time from datetimes
    from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
    to_date = to_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get the statistics from the database
    searches_complete, num_results_downloaded = get_completed_search_stats(from_date, to_date)
    site_searches_run, download_cnt = get_api_log_stats(from_date, to_date)
    searches_processed = get_processed_search_stats(from_date, to_date)

    # Build the response
    response = {
        "searches_complete":searches_complete,
        "searches_processed":searches_processed,
        "num_results_downloaded":num_results_downloaded,
        "download_cnt":download_cnt,
        "site_searches_run":site_searches_run,
        "from_date": from_date,
        "to_date": to_date}

    return render(request, 'textassembler_web/statistics.html', response)

def get_processed_search_stats(from_date, to_date):
    '''
    Get Searches processed
    returns:
        searches_processed(int): Number of searches processed during time period
    '''
    search_recs_processed = searches.objects.filter(Q(update_date__lte=to_date) & Q(update_date__gte=from_date))
    search_hist_recs_processed = historical_searches.objects.filter(Q(update_date__lte=to_date) & Q(update_date__gte=from_date))
    searches_processed = len(search_recs_processed) + len(search_hist_recs_processed)

    return searches_processed

def get_completed_search_stats(from_date, to_date):
    '''
    Get completed searches
    returns:
        searches_complete(int): Number of completed searches in date range
        num_results_downloaded(int): Number of results downloaded for completed_searches
    '''
    search_recs = searches.objects.filter(Q(date_completed_compression__lte=to_date) & Q(date_completed_compression__gte=from_date))
    search_hist_recs = historical_searches.objects.filter(Q(date_completed_compression__lte=to_date) & Q(date_completed_compression__gte=from_date))
    searches_complete = len(search_recs) + len(search_hist_recs)

    ## Caclulate counts
    num_results_downloaded = 0
    for rec in search_recs:
        num_results_downloaded = num_results_downloaded + (rec.num_results_downloaded if rec.num_results_downloaded is not None else 0)
    for rec in search_hist_recs:
        num_results_downloaded = num_results_downloaded + (rec.num_results_downloaded if rec.num_results_downloaded is not None else 0)

    return searches_complete, num_results_downloaded

def get_api_log_stats(from_date, to_date):
    '''
    Get API Logs
    returns:
        site_searches_run(int): Number of site searches run (on search page)
        download_cnt(int): Number of files downloaded from the API in the date range
    '''
    api_log = apps.get_model('textassembler_processor', 'api_log')
    api_recs = api_log.objects.filter(Q(request_date__lte=to_date) & Q(request_date__gte=from_date) & Q(request_url__icontains="expand=PostFilters"))
    site_searches_run = len(api_recs)

    download_api_recs = api_log.objects.filter(Q(request_date__lte=to_date) & Q(request_date__gte=from_date) & Q(request_url__icontains="expand=Document"))
    download_cnt = 0
    pattern = r'(top=)(\d+)'
    for rec in download_api_recs:
        try:
            download_cnt = download_cnt + (int)(re.search(pattern, rec.request_url).groups()[1])
        except: # pylint: disable=bare-except
            pass # do nothing, we can't add this count to our total and that's fine

    return site_searches_run, download_cnt
