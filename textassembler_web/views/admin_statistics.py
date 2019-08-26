'''
Handles all web requests for the statistics page
'''
import datetime
import re
from django.utils import timezone
from django.utils.timezone import make_aware
from django.shortcuts import render, redirect
from textassembler_web.utilities import get_is_admin
from textassembler_web.models import searches, historical_searches
from django.db.models import Q
from django.apps import apps

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
        from_date = make_aware(datetime.datetime.strptime(request.POST['FromDate'],'%Y-%m-%d'))
        to_date = make_aware(datetime.datetime.strptime(request.POST['ToDate'],'%Y-%m-%d'))

    # Remove time from datetimes
    from_date = from_date.replace(hour=0,minute=0,second=0,microsecond=0)
    to_date = to_date.replace(hour=0,minute=0,second=0,microsecond=0)

    # Get the statistics from the database
    # TODO -- add a line for number of searches processed during the time period?
    # TODO - what other information is useful on this page?
    search_recs = searches.objects.filter(Q(date_completed_compression__lte=to_date) & Q(date_completed_compression__gte=from_date))
    search_hist_recs = historical_searches.objects.filter(Q(date_completed_compression__lte=to_date) & Q(date_completed_compression__gte=from_date))
    searches_complete = len(search_recs) + len(search_hist_recs)

    num_results_downloaded = 0
    for rec in search_recs:
        num_results_downloaded = num_results_downloaded + (rec.num_results_downloaded if rec.num_results_downloaded is not None else 0)
    for rec in search_hist_recs:
        num_results_downloaded = num_results_downloaded + (rec.num_results_downloaded if rec.num_results_downloaded is not None else 0)

    api_log = apps.get_model('textassembler_processor', 'api_log')
    api_recs = api_log.objects.filter(Q(request_date__lte=to_date) & Q(request_date__gte=from_date) & Q(request_url__icontains="expand=PostFilters"))
    site_searches_run = len(api_recs)

    download_api_recs = api_log.objects.filter(Q(request_date__lte=to_date) & Q(request_date__gte=from_date) & Q(request_url__icontains="expand=Document"))
    download_cnt = 0
    pattern = '(top=)(\d+)'
    for rec in download_api_recs:
        try:
            download_cnt = download_cnt + (int)(re.search(pattern, rec.request_url).groups()[1])
        except:
            pass # do nothing, we can't add this count to our total and that's fine

    response = {
        "searches_complete":searches_complete,
        "num_results_downloaded":num_results_downloaded,
        "download_cnt":download_cnt,
        "site_searches_run":site_searches_run,
        "from_date": from_date,
        "to_date": to_date}

    return render(request, 'textassembler_web/statistics.html', response)
