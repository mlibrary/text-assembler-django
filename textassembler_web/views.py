from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from .forms import TextAssemblerWebForm
import logging
import traceback
import sys
import os
from django.conf import settings
from django.db import connections
from .search import Search
from .filters import Filters
from .utilities import log_error
from .models import available_formats, download_formats, searches, filters
import json
import logging
from django.utils import timezone

""" ------------------------------
    Search Page
    ------------------------------
""" 
def search(request):
    filter_data = get_filter_opts()
    set_filters = {}
    set_formats = []
    set_post_filters = []

    print(request.POST)
    form = TextAssemblerWebForm(request.POST or None)
    form.set_fields(filter_data, request.POST['search'] if 'search' in request.POST else '')

    for opt in filter_data:
            filter_data = {k:v for k,v in dict(request.POST).items() if k == opt['id']}
            for k,v in filter_data.items():
                set_filters[k] = v

    if "selected-formats" in dict(request.POST):
        set_formats = dict(request.POST)['selected-formats']
    if "post_filters" in dict(request.POST):
        set_post_filters = dict(request.POST)['post_filters']
    
    # add post filters to set_filters
    print(set_filters)
    print(set_post_filters)
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

    response = {
        "form": form
    }
    
    response["post_data"] = json.dumps(set_filters)

    if request.method == 'POST' and form.is_valid():
        
        clean = form.cleaned_data
   
        if clean["search"]  != "":
                try:
                    if "preview-search" in dict(request.POST):
                        '''
                        Preview Search button selected
                        '''
                        print(set_filters)
                        search_api = Search()
                        results = search_api.search(clean["search"], set_filters)
                        if "value" in results:
                            results['count'] = results['@odata.count']
                            results['postFilters'] = clean_post_filters(results['value'])
                            response['search_results'] = results
                        if "error_message" in results:
                            response['error_message'] = results["error_message"]

                        response['available_formats'] = available_formats.objects.all()

                    elif "add-filters" in dict(request.POST):
                        '''
                        Refresh Result Preview button selected
                        '''
                        # Redo the search
                        search_api = Search()
                        results = search_api.search(clean["search"], set_filters)
                        if "value" in results:
                            results['count'] = results['@odata.count']
                            results['postFilters'] = clean_post_filters(results['value'])
                            response['search_results'] = results
                        if "error_message" in results:
                            response['error_message'] = results["error_message"]

                        response['available_formats'] = available_formats.objects.all()

                    elif "submit-search" in dict(request.POST):
                        '''
                        Submit Search button selected
                        '''
                        # Save the search record
                        search_obj = searches(userid = request.user, query=clean["search"])

                        search_obj.save()

                        # Save the selected filters
                        for k,v in set_filters.items():
                            for val in v:
                                filter_obj = filters(search_id = search_obj, filter_name = k, filter_value = val)
                                filter_obj.save()

                        # Save the selected download formats                    
                        for set_format in set_formats:
                            format_item = available_formats.objects.get(format_id=set_format)
                            format_obj = download_formats(search_id = search_obj, format_id = format_item)
                            format_obj.save()

                        response['saved'] = True
 
                except Exception as e:
                    error = "{0} on line {1} of {2}: {3}\n{4}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e, traceback.format_exc())
                    log_error(error, json.dumps(dict(request.POST)))
                    
                    if settings.DEBUG:
                        response["error_message"] = error
                    else:
                        response["error_message"] = "An unexpected error has occured."
    

    elif request.method == 'POST' and not form.is_valid():
        for field in form.errors:
            form[field].field.widget.attrs['class'] += ' error-field'
        

    return render(request, "textassembler_web/search.html", response)

def clean_post_filters(results):
    postFilters = {}
    filters = Filters()
    for result in results:
        for postFilter in result['PostFilters']:
            for item in postFilter['FilterItems']:
                if item['Count'] != None and item['Count'] != 'null' and item['Count'] > 0:
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

                    if filter_name not in postFilters:
                        postFilters[filter_name] = {}
                    postFilters[filter_name][item['Name']] = {"Count":item['Count'], "Value": value}
    return postFilters


def get_filter_opts():
    filters = Filters()
    return filters.getAvailableFilters()

def get_filter_val_input(request, filter_type):
    filters = Filters()
    return JsonResponse(filters.getFilterValues(filter_type))

def string_is_int(s):
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
    return render(request, 'textassembler_web/mysearches.html', {})

""" ------------------------------
    About Page
    ------------------------------
""" 
def about(request):
    return render(request, 'textassembler_web/about.html', {})
