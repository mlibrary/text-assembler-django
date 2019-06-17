from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect
from .forms import TextAssemblerWebForm
import logging
import traceback
import sys
import os
from django.conf import settings
from django.db import connections
from .ln_api import LN_API
from .filters import Filters
from .utilities import log_error
from .models import available_formats, download_formats, searches, filters
import json
import logging
from django.utils import timezone
import shutil
from django.core.exceptions import PermissionDenied


""" ------------------------------
    Search Page
    ------------------------------
"""
def search(request):
    '''
    Render the search page
    '''

    filter_data = get_filter_opts()
    set_filters = {}
    set_formats = []
    set_post_filters = []

    print(request.POST)
    # Set the initial form data
    form = TextAssemblerWebForm(request.POST or None)
    form.set_fields(filter_data, request.POST['search'] if 'search' in request.POST else '')

    response = {
        "form": form,
        "error_message": "",
        "available_formats":available_formats.objects.all()
    }

    # Parse the POST data
    for opt in filter_data:
            filter_data = {k:v for k,v in dict(request.POST).items() if k == opt['id']}
            for k,v in filter_data.items():
                set_filters[k] = v
    if "selected-formats" in dict(request.POST):
        set_formats = dict(request.POST)['selected-formats']
    if "post_filters" in dict(request.POST):
        set_post_filters = dict(request.POST)['post_filters']

    # Add post filters to set_filters
    for post_filter in set_post_filters:
        name = post_filter.split("||")[0]
        value = post_filter.split("||")[-1]
        if string_is_int(value):
            value = int(value)
        if name in set_filters:
            set_filters[name].append(value)
        else:
            set_filters[name] = [value]

    print(set_filters)


    # Validate any data necessary from the post data
    for key, values in set_filters.items():
        ## Make sure Year is an integer
        if key == 'year(Date)':
            for value in values:
                if not string_is_int(value) or isinstance(value,int):
                    response['error_message'] += "The 'Year' field requires only numeric input, provided: {0}.".format(value);
    if 'Date' in set_filters and 'year(Date)' in set_filters:
        response['error_message'] += "Please you either the year filter or the range filter for dates, but not a combination of both."

    # Send the set filters back to the form to pre-populate the fields
    response["post_data"] = json.dumps(set_filters)

    # Set the last result data to be used in event of form failure to prevent another call to LN API
    if 'result_data' in request.POST and len(request.POST['result_data']) > 0:
        response["result_data"] = json.loads(request.POST['result_data'])

    if request.method == 'POST' and form.is_valid() and response['error_message'] == '':

        clean = form.cleaned_data

        if clean["search"]  != "":
                try:
                    if "preview-search" in dict(request.POST) or "add-filters" in dict(request.POST):
                        '''
                        Preview Search button selected
                        '''
                        search_api = LN_API()
                        results = search_api.search(clean["search"], set_filters)
                        if "value" in results:
                            results['count'] = results['@odata.count']
                            results['postFilters'] = clean_post_filters(results['value'])
                            response['search_results'] = results
                            response["search_results_json"] = json.dumps(results) # used in the event of failure after search
                        if "error_message" in results:
                            response['error_message'] = results["error_message"]



                    elif "submit-search" in dict(request.POST):
                        '''
                        Submit Search button selected
                        '''
                        # Perform any validation before saving
                        if len(set_formats) == 0:
                            response["error_message"] = "At least one download format must be selected."
                            # Set the result data with the previous results if an error occurs
                            # only do this if there are not already results since we don't want to overwrite those
                            if "result_data" in response and 'search_results' not in response:
                                response['search_results'] = response['result_data']

                        if response["error_message"] == "":
                            # Save the search record
                            search_obj = searches(userid = request.user, query=clean["search"])

                            search_obj.save()

                            # Save the selected filters
                            for k,v in set_filters.items():
                                if k == "Date":
                                    for i in range(0,len(v),2):
                                        filter_obj = filters(search_id = search_obj, filter_name = k, filter_value = v[i] + " " + v[i+1])
                                        filter_obj.save()
                                else:
                                    for val in v:
                                        filter_obj = filters(search_id = search_obj, filter_name = k, filter_value = val)
                                        filter_obj.save()

                            # Save the selected download formats
                            for set_format in set_formats:
                                format_item = available_formats.objects.get(format_id=set_format)
                                format_obj = download_formats(search_id = search_obj, format_id = format_item)
                                format_obj.save()

                            response = redirect('/mysearches')
                            return response

                except Exception as e:
                    error = "Error occured while processing search request. {0} on line {1} of {2}: {3}\n{4}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e, traceback.format_exc())
                    log_error(error, json.dumps(dict(request.POST)))

                    if settings.DEBUG:
                        response["error_message"] = error
                    else:
                        response["error_message"] = "An unexpected error has occured."

                    # Set the result data with the previous results if an error occurs
                    # only do this if there are not already results since we don't want to overwrite those
                    if "result_data" in response and 'search_results' not in response:
                        response['search_results'] = response['result_data']

    elif request.method == 'POST' and not form.is_valid():
        # If there are any form errors, add them to the fields to they highlight the issues
        for field in form.errors:
            form[field].field.widget.attrs['class'] += ' error-field'


    return render(request, "textassembler_web/search.html", response)

def clean_post_filters(results):
    '''
    Take the full results from the search and parse out only the post filters.
    Provide them back in a format that can be added to the display.
    '''

    postFilters = {}
    filters = Filters()
    for result in results:
        for postFilter in result['PostFilters']:
            for item in postFilter['FilterItems']:
                if item['Count'] != None and item['Count'] != 'null' and item['Count'] > 0:
                    # Clean the URL to get only the name of the filter and the value of the filter
                    # The benefit to using this instead of the PostFilterId field is that is has a better
                    # display name for the UI (PublicationType vs publicationtype)
                    url = item['SearchResults@odata.navigationLink']
                    only_filters = url[url.find('$filter='):].replace("$filter=","")
                    if '%20and%20' in only_filters:
                        only_filter = only_filters.split('%20and%20')[-1]
                    else:
                        only_filter = only_filters
                    filter_name = only_filter.split("%20eq%20")[0].replace("/","_")

                    value = only_filter.split("%20eq%20")[1]
                    namespace = filters.getEnumNamespace(filter_name)
                    value = value.replace(namespace,'') # remove the namespace from the value since we add it in at search time
                    if "'" in value:
                        value = value.replace("'","")
                    else:
                        value = int(value)

                    # Add the filter option and value to the results, grouped by the filter name
                    if filter_name not in postFilters:
                        postFilters[filter_name] = {}
                    postFilters[filter_name][item['Name']] = {"Count":item['Count'], "Value": value}
    return postFilters


def get_filter_opts():
    '''
    Get the available filters that the UI can use
    '''
    filters = Filters()
    return filters.getAvailableFilters()

def get_filter_val_input(request, filter_type):
    '''
    Get the type and available values for the given filter
    '''
    filters = Filters()
    return JsonResponse(filters.getFilterValues(filter_type))

def string_is_int(s):
    '''
    Check if the string contains an integer (because checking isinstance will return false for
    a string variable containing an integer.
    '''
    try:
        int(s)
        return True
    except ValueError:
        return False

""" ------------------------------
    My Searches Page
    ------------------------------
"""
def mysearches(request):
    '''
    Render the My Searches page
    '''
    response = {}
    response["headings"] = ["Date Submitted", "Query", "Progress", "Actions"]

    if "error_message" in request.session:
        response["error_message"] = request.session["error_message"]
        request.session["error_message"] = "" # clear it out so it won't show on refresh

    all_user_searches = searches.objects.all().filter(userid=request.user).order_by('-date_submitted')

    for search in all_user_searches:
        search = set_search_info(search)

    response["searches"] = all_user_searches

    return render(request, 'textassembler_web/mysearches.html', response)

def set_search_info(search):
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
         "args": str(search.search_id)
        }
    download = {
         "method": "POST",
         "label": "Download",
         "action": "download",
         "class": "btn-primary",
         "args": str(search.search_id)
        }

    if search.date_completed_compression != None:
        actions.append(download)
    actions.append(delete)
    search.actions = actions

    # Build progress data
    search.filters = filters.objects.filter(search_id=search.search_id)
    formats = download_formats.objects.filter(search_id=search.search_id)
    search.download_formats = []

    for f in formats:
        search.download_formats.append(available_formats.objects.get(format_id=f.format_id.format_id))

    search.status = "Queued"
    if search.date_started != None:
        search.status = "In Progress"
    if search.date_started_compression != None:
        search.status = "Preparing Results for Download"
    if search.date_completed_compression != None:
        search.status = "Completed"
    # TODO -- handle Failed searches
    if search.failed_date != None:
        search.status = "Failed"

    if search.num_results_in_search == None or search.num_results_in_search == 0:
        search.percent_complete = 0
    else:
        logging.debug(round((search.num_results_downloaded / search.num_results_in_search) * 100,0))
        search.percent_complete = round((search.num_results_downloaded / search.num_results_in_search) * 100,0)

    # TODO if the search is complete, show the date that the search will be deleted

    return search

def delete_search(request, search_id):
    '''
    Will remove the search from the database and delete files on the server
    '''
    # TODO - put this in a try-catch block and have error show on page like in download
    search = searches.objects.get(search_id=search_id)
    logging.info("Deleting search: {0}. {1}".format(search_id, search))

    # delete files on the server
    ## verify the storage location is accessibly
    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
        log_error("Could not delete files for search {0} due to storage location being inaccessible or not writable. {1}".format(search_id, settings.STORAGE_LOCATION), search)

    else:
        save_location = os.path.join(settings.STORAGE_LOCATION,search_id)
        zip_path = find_zip_file(search_id)

        if os.path.isdir(save_location):
            try:
                shutil.rmtree(save_location)
            except Exception as e1:
                log_error("Could not delete files for search {0}. {1}".format(search_id,e1), search)
        if zip_path != None and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception as e2:
                log_error("Could not delete the zipped file for search {0}. {1}".format(search_id, e2), search)
        # TODO -- not deleting root directory

    # delete the records from the database regardless of if we can delete the files
    search.delete()

    return redirect(mysearches)

def download_search(request, search_id):
    '''
    need to download files from the server for the search
    '''
    error_message = ""
    try:
        # make sure the search documents requested are for the user that made the search (HTTP 403)
        search = searches.objects.filter(search_id=search_id)
        if len(search) == 1:
            search = search[0]
        else:
            error_message = "The search record could not be located on the server. please contact a system administator."
        if search.userid != str(request.user):
            error_message = "You do not have permissions to download searches other than ones you requested."

        # make sure the search file exists (HTTP 404)
        if error_message == "":
            zipfile = find_zip_file(search_id)
            if zipfile == None or not os.path.exists(zipfile) or not os.access(zipfile, os.R_OK):
                error_message = "The search results can not be located on the server. please contact a system administator."

        if error_message == "":
            # download the search zip
            with open(zipfile, 'rb') as fh:
                    response = HttpResponse(fh.read(), content_type="application/force-download")
                    response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zipfile)
                    return response
    except Exception as e:
        error = "Error downloading search {0}. {1} on line {2} of {3}: {4}\n{5}".format(str(search_id), type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e, traceback.format_exc())
        log_error(error, json.dumps(dict(request.POST)))

        if settings.DEBUG:
            error_message = error
        else:
            error_message = "An unexpected error has occured."

    request.session["error_message"] = error_message
    return redirect(mysearches)


def find_zip_file(search_id):
    '''
    For the given search ID, it will locate the full path for the zip file
    '''
    filepath = os.path.join(settings.STORAGE_LOCATION,search_id)
    for root, dirs, files in os.walk(filepath):
        for name in files:
            if name.endswith("zip"):
                return os.path.join(root,name)
    return None

""" ------------------------------
    About Page
    ------------------------------
"""
def about(request):
    '''
    Render the About page
    '''
    return render(request, 'textassembler_web/about.html', {})
