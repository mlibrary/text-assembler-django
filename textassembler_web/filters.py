"""
Retrieve the available filters to use for searching
"""
import logging
import requests
import json
from django.conf import settings
import datetime
from .search import Search
from .models import sources

class Filters:
    def __init__(self):
        self.api = None

    def getAvailableFilters(self):
        return [{"id":"lang", "name":"Language"},
                {"id":"source", "name":"Source"},
                {"id":"people", "name":"People"},
                {"id":"date", "name":"Date"}]

    def getFilterValues(self, filter_type):
        if filter_type is None:
            return {}

        if filter_type == 'people':
            return {'name':"People", 'type':'text'}

        if filter_type == 'lang':
            return {'name':'Language', 'type':'select', 'choices':[
                {'val':'English','name':'English'},
                {'val':'French', 'name':'French'},
                {'val':'German', 'name':'German'},
                {'val':'Spanish', 'name':'Spanish'},
                {'val':'Dutch', 'name':'Dutch'},
                {'val':'Portuguese', 'name':'Portuguese'},
                {'val':'Italian', 'name':'Italian'},
                {'val':'Russian', 'name':'Russian'},
                {'val':'Japanese', 'name':'Japanese'},
                {'val':'Danish', 'name':'Danish'},
                {'val':'Swedish', 'name':'Swedish'},
                {'val':'Norwegian', 'name':'Norwegian'},
                {'val':'Indonesian', 'name':'Indonesian'},
                {'val':'Vietnamese', 'name':'Vietnamese'},
                {'val':'Romanian', 'name':'Romanian'},
                {'val':'Turkish', 'name':'Turkish'},
                {'val':'Korean', 'name':'Korean'},
                {'val':'Greek', 'name':'Greek'},
                {'val':'Arabic', 'name':'Arabic'},
                {'val':'Afrikaans', 'name':'Afrikaans'},
                {'val':'Croatian', 'name':'Croatian'},
                {'val':'Czech', 'name':'Czech'},
                {'val':'Catalan', 'name':'Catalan'}]}

        if filter_type == 'source':
            results = []
            print("number of sources: {0}".format(sources.objects.all().count()))
            for source in sources.objects.all():
                results.append({"val":source.source_id,"name":source.source_name})
            return {'name':'Source','type':'select', 'choices':results}

        if filter_type == 'date':
            return {'name':'Date', "type":"date", "choices":[
                {"val":"gt", "name":"&#62;"},
                {"val":"lt", "name":"&#60;"},
                {"val":"gte", "name":"&#8804;"},
                {"val":"lte", "name":"&#8805;"} ]}
