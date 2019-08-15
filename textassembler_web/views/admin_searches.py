'''
Handles all requests to the admin page
'''
import json
import logging
import datetime
import os
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.conf import settings
from textassembler_web.utilities import log_error, create_error_message, est_days_to_complete_search
from textassembler_web.models import available_formats, download_formats, searches, filters, admin_users

def admin_searches(request):
    '''
    Render the admin page
    '''
    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    # Verify that the user is an admin
    admin_user = admin_users.objects.all().filter(userid=request.session['userid'])
    if not admin_user:
        return redirect('/login')

    response = {}
    response["headings"] = ["Date Submitted", "Query", "Progress", "Actions"]

    if "error_message" in request.session:
        response["error_message"] = request.session["error_message"]
        request.session["error_message"] = "" # clear it out so it won't show on refresh

    all_user_searches = searches.objects.all().filter(deleted=False).order_by('-date_submitted')

    for search_obj in all_user_searches:
        search_obj = set_search_info(search_obj)

    response["searches"] = all_user_searches
    response["num_months_keep_searches"] = settings.NUM_MONTHS_KEEP_SEARCHES

    return render(request, 'textassembler_web/mysearches.html', response)

def set_search_info(search_obj):
    '''
    Add additional information to each search result object for the page to use when rendering
    '''

    # Add actions for Download and Delete
    actions = []

    delete = {
        "method": "POST",
        "label": "Delete",
        "action": "delete",
        "class": "btn-danger",
        "args": str(search_obj.search_id)
        }
    download = {
        "method": "POST",
        "label": "Download",
        "action": "download",
        "class": "btn-primary",
        "args": str(search_obj.search_id)
        }

    if search_obj.date_completed_compression != None:
        actions.append(download)
    actions.append(delete)
    search_obj.actions = actions

    # Build progress data
    search_obj.filters = filters.objects.filter(search_id=search_obj.search_id)
    formats = download_formats.objects.filter(search_id=search_obj.search_id)
    search_obj.download_formats = []

    for fmt in formats:
        search_obj.download_formats.append(available_formats.objects.get(format_id=fmt.format_id.format_id))

    # determine the status
    search_obj.status = "Queued"
    if search_obj.date_started != None:
        search_obj.status = "In Progress"
    if search_obj.date_started_compression != None:
        search_obj.status = "Preparing Results for Download"
    if search_obj.date_completed_compression != None:
        search_obj.status = "Completed"
    if search_obj.failed_date != None:
        search_obj.status = "Failed"

    # set date the search_obj is set to be deleted on
    if search_obj.status == "Completed":
        search_obj.delete_date = search_obj.date_completed_compression + datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)
    if search_obj.status == "Failed":
        search_obj.delete_date = search_obj.failed_date + datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)

    if (search_obj.status == "Queued" or search_obj.status == "In Progress") and search_obj.num_results_in_search and search_obj.num_results_in_search > 0:
        search_obj.est_days_to_complete = est_days_to_complete_search(search_obj.num_results_in_search - search_obj.num_results_downloaded)

    # calculate percent complete
    if search_obj.num_results_in_search is None or search_obj.num_results_in_search == 0:
        search_obj.percent_complete = 0
    else:
        search_obj.percent_complete = round((search_obj.num_results_downloaded / search_obj.num_results_in_search) * 100, 0)

    # Clear out the error message from the display if the status is not Failed
    if search_obj.status != "Failed":
        search_obj.error_message = ""

    return search_obj
