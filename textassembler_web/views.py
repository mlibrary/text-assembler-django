from django.http import HttpResponse
from django.shortcuts import render
from .forms import TextAssemblerWebForm
import logging
import traceback
import sys
import os
from django.conf import settings
from django.db import connections
from .search import Search


def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

def search(request):
    form = TextAssemblerWebForm(request.POST)

    response = {
        "form": form,
    } 

    if form.is_valid():
        clean = form.cleaned_data
        response["search"] = clean["search"]   
   
        if clean["search"]  != "":
            try:
                search_api = Search()
                results = search_api.search(clean["search"])
                if "value" in results and len(results["value"]) > 0:
                    search_results = results["value"][0]["Title"]
                else:
                    search_results = "No results found"
                
                response["message"] = search_results    
            except Exception as e:
                response["message"] = "{0} on line {1} of {2}: {3}\n{4}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e, traceback.format_exc())



    return render(request, "textassembler_web/search.html", response)
