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
        '''
        The id field matches the filter in the API $filter value, replace / with _
        The name is what to display on the page
        '''
        return [{"id":"Language", "name":"Language"}, # TODO -- not allowing multiple filters
                {"id":"Source_Id", "name":"Source"},
                {"id":"Date", "name":"Date"},
                {"id":"NegativeNewsType", "name":"Negative News Type"}, # TODO -- not working
                {"id":"GroupDuplicates", "name":"Group Duplicates"},
                {"id":"SearchType", "name": "Search Type"},
                {"id":"Location", "name": "Location"},
                {"id":"Geography", "name": "Geography"},
                {"id":"Industry", "name": "Industry"},
                {"id":"Subject", "name": "Subject"},
                {"id":"Section", "name": "Section"},
                {"id":"Company", "name": "Company"},
                {"id":"PublicationType", "name": "Publication Type"},
                {"id":"Publisher", "name": "Publisher"},
                {"id":"People", "name":"People"}]

    def getFilterValues(self, filter_type):
        name = self.getAvailableFilters()
        name = [x['name'] for x in name if x['id'] == filter_type][0]

        if filter_type == 'Language':
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

        elif filter_type == 'NegativeNewsType':
            return {'name':name, 'type':'select', 'choices':[
                {'val':'Personal', 'name':'Personal',},
                {'val':'Business', 'name':'Business'}]}
            
        elif filter_type == 'GroupDuplicates':
            return {'name':name, 'type':'select', 'choices':[
                {'val':'HighSimilarity', 'name':'High Similarity',},
                {'val':'ModerateSimilarity', 'name':'Moderate Similarity'}]}

        elif filter_type == 'SearchType':
            return {'name':name, 'type':'select', 'choices':[
                {'val':'DynamicAnd', 'name':'Dynamic And',},
                {'val':'DynamicOr', 'name':'Dynamic Or',},
                {'val':'NaturalLanguageOr', 'name':'Natural Language Or',},
                {'val':'NaturalLanguageAnd', 'name':'Natural Language And',},
                {'val':'Boolean', 'name':'Boolean'}]}

        elif filter_type == 'Source_Id':
            results = []
            for source in sources.objects.all():
                results.append({"val":source.source_id,"name":source.source_name})
            return {'name':'Source','type':'select', 'choices':results}

        elif filter_type == 'Date':
            return {'name':'Date', "type":"date", "choices":[
                {"val":"gt", "name":"&#62;"},
                {"val":"lt", "name":"&#60;"},
                {"val":"gte", "name":"&#8804;"},
                {"val":"lte", "name":"&#8805;"} ]}

        # Handle all of the plain text fields
        else:
            return {"name": name, "type":"text"}

    def getEnumNamespace(self, filter_type):
        if filter_type in ['Language','NegativeNewsType','GroupDuplicates','SearchType']:
            return 'LexisNexis.ServicesApi.' + filter_type
        else:
            return ''
