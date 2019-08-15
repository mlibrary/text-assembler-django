'''
Handles all web requests for the my searches page
'''
import json
import logging
import os
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.conf import settings
from textassembler_web.utilities import log_error, create_error_message, build_search_info
from textassembler_web.models import searches

def mysearches(request):
    '''
    Render the My Searches page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    response = {}
    response["headings"] = ["Date Submitted", "Query", "Progress", "Actions"]

    if "error_message" in request.session:
        response["error_message"] = request.session["error_message"]
        request.session["error_message"] = "" # clear it out so it won't show on refresh

    all_user_searches = searches.objects.all().filter(userid=request.session['userid'], deleted=False).order_by('-date_submitted')

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

    return build_search_info(search_obj)

def delete_search(request, search_id):
    '''
    Will flag the search as deleted, which the deletion processor will pick up
    and remove from the DB and the storage location
    '''

    error_message = ""
    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    try:
        search_obj = searches.objects.get(search_id=search_id)
        logging.info(f"Marking search as deleted: {search_id}. {search_obj}")

        search_obj.deleted = True
        search_obj.save()

    except Exception as exp: # pylint: disable=broad-except
        error = create_error_message(exp, os.path.basename(__file__))
        log_error(f"Error marking search as deleted:  {search_id}. {error}", json.dumps(dict(request.POST)))

        if settings.DEBUG:
            error_message = error
        else:
            error_message = "An unexpected error has occurred."

    request.session["error_message"] = error_message
    return redirect(mysearches)

def download_search(request, search_id):
    '''
    need to download files from the server for the search
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    error_message = ""
    try:
        # make sure the search documents requested are for the user that made the search (HTTP 403)
        search_obj = searches.objects.filter(search_id=search_id)
        if len(search_obj) == 1:
            search_obj = search_obj[0]
        else:
            error_message = \
                "The search record could not be located on the server. please contact a system administator."
        if search_obj.userid != str(request.session['userid']):
            error_message = "You do not have permissions to download searches other than ones you requested."

        # make sure the search file exists (HTTP 404)
        if error_message == "":
            zipfile = find_zip_file(search_id)
            if zipfile is None or not os.path.exists(zipfile) or not os.access(zipfile, os.R_OK):
                error_message = \
                    "The search results can not be located on the server. please contact a system administator."

        if error_message == "":
            # download the search zip
            with open(zipfile, 'rb') as flh:
                response = HttpResponse(flh.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zipfile)
                request.session["error_message"] = error_message
                return response
    except Exception as exp: # pylint: disable=broad-except
        error = create_error_message(exp, os.path.basename(__file__))
        log_error(f"Error downloading search {search_id}. {error}", json.dumps(dict(request.POST)))

        if settings.DEBUG:
            error_message = error
        else:
            error_message = "An unexpected error has occurred."

    request.session["error_message"] = error_message
    return redirect(mysearches)


def find_zip_file(search_id):
    '''
    For the given search ID, it will locate the full path for the zip file
    '''
    filepath = os.path.join(settings.STORAGE_LOCATION, search_id)
    for root, _, files in os.walk(filepath):
        for name in files:
            if name.endswith("zip"):
                return os.path.join(root, name)
    return None
