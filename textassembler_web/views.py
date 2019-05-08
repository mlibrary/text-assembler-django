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
from .models import available_formats
import json
import logging

""" ------------------------------
    Search Page
    ------------------------------
""" 
def search(request):
    filter_data = get_filter_opts()
    set_filters = {}

    form = TextAssemblerWebForm(request.POST or None)
    form.set_fields(filter_data, request.POST['search'] if 'search' in request.POST else '')

    for opt in filter_data:
            filters = {k:v for k,v in dict(request.POST).items() if k == opt['id']}
            for k,v in filters.items():
                set_filters[k] = v

    response = {
        "form": form
    }

    response["post_data"] = json.dumps(set_filters)

    if request.method == 'POST' and form.is_valid():
        clean = form.cleaned_data
   
        if clean["search"]  != "":
            try:
                search_api = Search()
                results = search_api.search(clean["search"], set_filters)
                if "value" in results:
                    results['count'] = results['@odata.count']
                    results['postFilters'] = clean_post_filters(results['value'])
                    response['search_results'] = results
                if "error_message" in results:
                    response['error_message'] = results["error_message"]

                response['available_formats'] = available_formats.objects.all()
                
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
    for result in results:
        for postFilter in result['PostFilters']:
            for item in postFilter['FilterItems']:
                if item['Count'] != None and item['Count'] != 'null' and item['Count'] > 0:
                    if postFilter['PostFilterId'] not in postFilters:
                        postFilters[postFilter['PostFilterId']] = {}
                    postFilters[postFilter['PostFilterId']][item['Name']] = {"Count":item['Count'], "URL": item['SearchResults@odata.navigationLink']}
    print(postFilters)
    return postFilters


def get_filter_opts():
    filters = Filters()
    return filters.getAvailableFilters()

def get_filter_val_input(request, filter_type):
    filters = Filters()
    return JsonResponse(filters.getFilterValues(filter_type))

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
