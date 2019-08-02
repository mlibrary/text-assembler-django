'''
Handles all web requests for the application
'''
import json
import logging
import datetime
import shutil
import base64
import os
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.conf import settings
from .forms import TextAssemblerWebForm
from .ln_api import LNAPI
from .oauth_client import OAuthClient
from .filters import get_available_filters, get_filter_values, get_enum_namespace, get_format_type
from .utilities import log_error, create_error_message, est_days_to_complete_search
from .models import available_formats, download_formats, searches, filters

""" ------------------------------
    Login
    ------------------------------
""" # pylint: disable=pointless-string-statement
def login(request):
    '''
    Handles login requests
    '''
    # Check if bypass mode is enabled
    if settings.OAUTH_BYPASS:
        request.session['userid'] = settings.OAUTH_BYPASS_USER
        logging.debug(f"OAuth bypass mode is enabled. Logging in as {request.session['userid']}")
        return redirect('/search')

    # If they are already logged in, send users to search page
    if request.session.get('userid', False):
        logging.debug(f"User already logged in: {request.session['userid']}")
        return redirect('/search')

    # Initialize the OAuth client
    app_auth = OAuthClient(settings.APP_CLIENT_ID, settings.APP_CLIENT_SECRET, \
        settings.APP_REDIRECT_URL, settings.APP_AUTH_URL, \
        settings.APP_TOKEN_URL, settings.APP_PROFILE_URL)

    # Check if the logon was successful already
    if 'code' in request.GET and request.session.get('state', False):
        logging.debug("Getting OAuth access token from the code")
        app_auth.set_state(request.session['state'])
        request.session['access_token'] = app_auth.get_access_token(request.GET['code'])

    # Call the OAuth provider to authenticate
    if not request.session.get('access_token', False):
        logging.debug("Authenticating the user")
        app_auth.init_auth_url()
        request.session['state'] = app_auth.get_state() # save the state in the session to use later
        return redirect(app_auth.get_auth_url())

    # Retrieve user information after a successful logon
    if request.session.get('access_token', False) and not request.session.get('userid', False):
        logging.debug("Getting the authenticated user's userid")
        app_auth.set_access_token(request.session['access_token'])
        results = app_auth.fetch()
        request.session['userid'] = results['info'][settings.APP_USER_ID_FIELD]

    # Check if the userid is still not set
    if not request.session.get('userid', False):
        logging.warning("UserID was still not set after authentication against OAuth")
        return HttpResponse('Unable to log in. You must be an active MSU user to use this resource.')

    # Send users to the search page on sucessful login
    return redirect('/search')

""" ------------------------------
    Logout
    ------------------------------
""" # pylint: disable=pointless-string-statement
def logout(request):
    '''
    Handles logout requests
    '''
    # Clear the session
    request.session['userid'] = None
    request.session['access_token'] = None
    request.session['state'] = None

    # Redirect to OAuth logout page
    return redirect(settings.APP_LOGOUT_URL)

""" ------------------------------
    Search Page
    ------------------------------
""" # pylint: disable=pointless-string-statement
def search(request): # pylint:disable=too-many-locals, too-many-branches, too-many-statements
    '''
    Render the search page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    filter_data = get_available_filters()
    set_filters = {}
    set_formats = []
    set_post_filters = []

    logging.debug("==== POST DATA ====")
    logging.debug(request.POST)

    # Set the initial form data
    form = TextAssemblerWebForm(request.POST or None)
    form.set_fields(get_available_filters(False), request.POST['search'] if 'search' in request.POST else '')

    response = {
        "form": form,
        "error_message": "",
        "available_formats":available_formats.objects.all()
    }

    # Parse the POST data
    for opt in filter_data:
        filter_data = {k:v for k, v in dict(request.POST).items() if k.lower() == opt['id'].lower()}
        for fld, vals in filter_data.items():
            set_filters[fld] = vals
    if "selected-formats" in dict(request.POST):
        set_formats = dict(request.POST)['selected-formats']
    if "post_filters" in dict(request.POST):
        set_post_filters = dict(request.POST)['post_filters']

    # Add post filters to set_filters
    for post_filter in set_post_filters:
        name = post_filter.split("||")[0]
        value = post_filter.split("||")[-1]
        fmt = get_format_type(name)
        # convert the value(s) from base64 if the filter expects it
        if fmt == 'base64':
            value = base64.b64decode(value + "=========").decode('utf-8')
        if string_is_int(value):
            value = int(value)
        if name in set_filters:
            set_filters[name].append(value)
        else:
            set_filters[name] = [value]

    logging.debug("==== SET FILTERS ====")
    logging.debug(set_filters)


    # Validate any data necessary from the post data
    for key, values in set_filters.items():
        ## Make sure Year is an integer
        if key == 'year(Date)':
            for value in values:
                if not string_is_int(value) and not isinstance(value, int):
                    response['error_message'] += \
                        f"The 'Year' field requires only numeric input, provided: {value}."
        else:
            for value in values:
                if not value:
                    response['error_message'] += \
                        f"The '{key}' field can not be blank, please provide a value or remove the filter."
                    break
    if 'Date' in set_filters and 'year(Date)' in set_filters:
        response['error_message'] += \
            "Please you either the year filter or the range filter for dates, but not a combination of both."

    # Send the set filters back to the form to pre-populate the fields
    response["post_data"] = json.dumps(set_filters)

    # Set the last result data to be used in event of form failure to prevent another call to LN API
    if 'result_data' in request.POST and request.POST['result_data']:
        response["result_data"] = json.loads(request.POST['result_data'])

    if request.method == 'POST' and form.is_valid() and response['error_message'] == '':

        clean = form.cleaned_data

        if clean["search"] != "":
            try:
                if "preview-search" in dict(request.POST) or "add-filters" in dict(request.POST):
                    # Preview Search button selected
                    response = handle_preview_search(clean['search'], set_filters, response)

                elif "submit-search" in dict(request.POST):
                    # Submit Search button selected
                    response = handle_save_search(request.session['userid'], clean['search'], set_filters, set_formats, response)
                    return response

            except Exception as exp: # pylint: disable=broad-except
                error = create_error_message(exp, os.path.basename(__file__))
                log_error(f"Error occurred while processing search request. {error}", json.dumps(dict(request.POST)))

                if settings.DEBUG:
                    response["error_message"] = error
                else:
                    response["error_message"] = "An unexpected error has occurred."

                # Set the result data with the previous results if an error occurs
                # only do this if there are not already results since we don't want to overwrite those
                if "result_data" in response and 'search_results' not in response:
                    response['search_results'] = response['result_data']

    elif request.method == 'POST' and not form.is_valid():
        # If there are any form errors, add them to the fields to they highlight the issues
        for field in form.errors:
            form[field].field.widget.attrs['class'] += ' error-field'


    return render(request, "textassembler_web/search.html", response)


def handle_preview_search(term, set_filters, response):
    '''
    Gets the preview results from the API and populates the response object
    '''
    search_api = LNAPI()
    results = search_api.search(term, set_filters)
    if "value" in results:
        # add estimated number of days to complete to result set
        results['est_days_to_complete'] = est_days_to_complete_search(int(results['@odata.count']))
        results['count'] = results['@odata.count']
        results['postFilters'] = clean_post_filters(results['value'])
        response['search_results'] = results
        response["search_results_json"] = json.dumps(results) # used in the event of failure after search
    if "error_message" in results:
        response['error_message'] = \
            f"Error returned from LexisNexis: {'[Not Set]' if not results['error_message'] else results['error_message']}"

    elif settings.PREVIEW_FORMAT == "FULL":
        # Get the full-text for the 10 results to display on the page
        results = search_api.download(term, set_filters)
        if "value" in results:
            results['est_days_to_complete'] = est_days_to_complete_search(int(results['@odata.count']))
            results['count'] = results['@odata.count']
            results['postFilters'] = response['search_results']['postFilters']
            response['search_results'] = results
            response["search_results_json"] = json.dumps(results) # used in the event of failure after search
        if "error_message" in results:
            response['error_message'] = \
                f"Error returned from LexisNexis: {'[Not Set]' if not results['error_message'] else results['error_message']}"

    return response


def handle_save_search(userid, term, set_filters, set_formats, response):
    '''
    Handles the search being queued for full download
    '''
    # Perform any validation before saving
    if not set_formats:
        response["error_message"] = "At least one download format must be selected."
        # Set the result data with the previous results if an error occurs
        # only do this if there are not already results since we don't want to overwrite those
        if "result_data" in response and 'search_results' not in response:
            response['search_results'] = response['result_data']

    if response["error_message"] == "":
        # Save the search record
        search_obj = searches(userid=userid, query=term)

        search_obj.save()

        # Save the selected filters
        for k, vals in set_filters.items():
            if k == "Date":
                for i in range(0, len(vals), 2):
                    filter_obj = filters(search_id=search_obj, filter_name=k, filter_value=vals[i] + " " + vals[i+1])
                    filter_obj.save()
            else:
                for val in vals:
                    filter_obj = filters(search_id=search_obj, filter_name=k, filter_value=val)
                    filter_obj.save()

        # Save the selected download formats
        for set_format in set_formats:
            format_item = available_formats.objects.get(format_id=set_format)
            format_obj = download_formats(search_id=search_obj, format_id=format_item)
            format_obj.save()

        response = redirect('/mysearches')
    return response

def clean_post_filters(results):
    '''
    Take the full results from the search and parse out only the post filters.
    Provide them back in a format that can be added to the display.
    '''

    post_filters = {}
    for result in results:
        for post_filter in result['PostFilters']:
            for item in post_filter['FilterItems']:
                if item['Count'] != None and item['Count'] != 'null' and item['Count'] > 0:
                    # Clean the URL to get only the name of the filter and the value of the filter
                    # The benefit to using this instead of the PostFilterId field is that is has a better
                    # display name for the UI (PublicationType vs publicationtype)
                    url = item['SearchResults@odata.navigationLink']
                    only_filters = url[url.find('$filter='):].replace("$filter=", "")
                    if '%20and%20' in only_filters:
                        only_filter = only_filters.split('%20and%20')[-1]
                    else:
                        only_filter = only_filters
                    filter_name = only_filter.split("%20eq%20")[0].replace("/", "_")
                    if filter_name[0] == '(':
                        filter_name = filter_name[1:]

                    value = only_filter.split("%20eq%20")[1]
                    namespace = get_enum_namespace(filter_name)
                    value = value.replace(namespace, '') # remove the namespace from the value since we add it in at search time
                    if "'" in value:
                        value = value.replace("'", "")
                    else:
                        value = int(value)

                    # Add the filter option and value to the results, grouped by the filter name
                    if filter_name not in post_filters:
                        post_filters[filter_name] = {}
                    post_filters[filter_name][item['Name']] = {
                        "Count":item['Count'], \
                        "Value": value, \
                        "est_days_to_complete": est_days_to_complete_search(item['Count'])
                        }
    return post_filters

def get_filter_val_input(request, filter_type):
    '''
    Get the type and available values for the given filter
    '''
    return JsonResponse(get_filter_values(filter_type))

def string_is_int(sval):
    '''
    Check if the string contains an integer (because checking isinstance will return false for
    a string variable containing an integer.
    '''
    try:
        int(sval)
        return True
    except ValueError:
        return False

""" ------------------------------
    My Searches Page
    ------------------------------
""" # pylint: disable=pointless-string-statement
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

""" ------------------------------
    About Page
    ------------------------------
""" # pylint: disable=pointless-string-statement
def about(request):
    '''
    Render the About page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    return render(request, 'textassembler_web/about.html', {})
