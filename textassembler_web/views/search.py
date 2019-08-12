'''
Handles all web requests for the search page
'''
import json
import logging
import base64
import os
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.conf import settings
from textassembler_web.forms import TextAssemblerWebForm
from textassembler_web.ln_api import LNAPI
from textassembler_web.filters import get_available_filters, get_filter_values, get_enum_namespace, get_format_type
from textassembler_web.utilities import log_error, create_error_message, est_days_to_complete_search
from textassembler_web.models import available_formats, download_formats, searches, filters

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
