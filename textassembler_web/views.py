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

def search(request):
    form = TextAssemblerWebForm(request.POST or None)
    form.set_fields(get_filter_opts())

    response = {
        "form": form,
        "message": "",
    }
    # TODO -- if form is invalid, it is just showing an empty form

    # TODO -- send back filters in the form to pre-populate

    if request.method == 'POST' and form.is_valid():
        clean = form.cleaned_data
        #print(request.POST)
        response["search"] = clean["search"]   
   
        if clean["search"]  != "":
            try:
                search_api = Search()
                results = search_api.search(clean["search"])
                if "value" in results and len(results["value"]) > 0:
                    search_results = results["value"][0]["Title"]
                elif "error_message" in results:
                    search_results = results["error_message"]
                else:
                    search_results = "No results found"
                
                response["message"] += search_results    
            except Exception as e:
                response["message"] += "{0} on line {1} of {2}: {3}\n{4}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e, traceback.format_exc())

    return render(request, "textassembler_web/search.html", response)

def get_filter_opts():
    filters = Filters()
    return filters.getAvailableFilters()

def get_filter_val_input(request, filter_type):
    filters = Filters()
    return JsonResponse(filters.getFilterValues(filter_type))
