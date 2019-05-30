"""
Retrieve the available filters to use for searching
"""
import logging
import requests
import json
from django.conf import settings
import datetime
from .models import sources

class Filters:
    def __init__(self):
        self.api = None

    def getAvailableFilters(self):
        '''
        The id field matches the filter in the API $filter value, replace / with _
        The name is what to display on the page

        The 'help' field will be displayed in a popover on the page. It can include
        HTML elements, but ensure that all quotes are double quotes (") or the JS will
        have issues rendering it.
        '''

        return [{"id":"Language", "name":"Language"}, # TODO -- not allowing multiple filters, talk to LN
                {"id":"Source_Id", "name":"Source"}, # TODO -- not allowing multiple filters, talk to LN
                {"id":"Date", "name":"Date Range"},
                {"id":"year(Date)", "name":"Year"},
                {"id":"NegativeNews", "name":"Negative News Type"},
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
        '''
        Get the data for the given filter for the UI.
        This includes the data type, help text, and available options
        where applicable.
        '''

        name = self.getAvailableFilters()
        found_filters = [x['name'] for x in name if x['id'] == filter_type]
        if len(found_filters) == 1:
            name = found_filters[0]
        else:
            name = filter_type

        if filter_type == 'Language':
            return {'name':name, 'type':'select', 
                'help':'Filters the articles by the language they were written in',
                'choices':[
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

        elif filter_type == 'NegativeNewsType' or filter_type == 'NegativeNews':
            return {'name':name, 'type':'select', 
                'help':'Whether or not the news article is considered negative in either the personal or business context',
                'choices':[
                {'val':'Personal', 'name':'Personal',},
                {'val':'Business', 'name':'Business'}]}
            
        elif filter_type == 'GroupDuplicates':
            return {'name':name, 'type':'select', 
                'help':'The degree to which duplicate search results are grouped into single items',
                'choices':[
                {'val':'HighSimilarity', 'name':'High Similarity',},
                {'val':'ModerateSimilarity', 'name':'Moderate Similarity'}]}

        elif filter_type == 'SearchType':
            return {'name':name, 'type':'select', 
                'help':"""<div class="large-popover">Defaults to "Dynamic And" if not specified.
                <table class="popover-table">
                <tr><th>Type</th><th>Description</th></tr>
                <tr><td>Dynamic And</td>
                <td>Dynamic searches will analyze the search terms for its format. Search terms will only be matched as a group, so a search for "house boat" will not include results which only contain "house" or "boat".</td></tr>
                <tr><td>Dynamic Or</td>
                <td>Dynamic searches will analyze the search terms for its format. Search terms will be used both individually and as a group, so a search for "house boat" will also include results which only contain "house" or "boat".</tr></tr>
                <tr><td>Natural Language Or</td>
                <td>Executes a search using a natural language parser. Search terms will be used both individually and as a group.</td></tr>
                <tr><td>Natural Language And</td>
                <td>Executes a search using a natural language parser. Search terms will be used only as a group.</td></tr>
                <tr><td>Boolean</td>
                <td>Executes a search using a boolean parser.</td></tr>
                </table></div>""",
                'choices':[
                {'val':'DynamicAnd', 'name':'Dynamic And',},
                {'val':'DynamicOr', 'name':'Dynamic Or',},
                {'val':'NaturalLanguageOr', 'name':'Natural Language Or',},
                {'val':'NaturalLanguageAnd', 'name':'Natural Language And',},
                {'val':'Boolean', 'name':'Boolean'}]}

        elif filter_type == 'Source_Id':
            results = []
            for source in sources.objects.all():
                results.append({"val":source.source_id,"name":source.source_name})
            return {'name':'Source','type':'select', 
                'help':'The content source that is searched',
                'choices':results}

        elif filter_type == 'Date':
            return {'name':'Date', "type":"date", 
                'help':'The publication date',
                "choices":[
                {"val":"gt", "name":"&#62;"},
                {"val":"lt", "name":"&#60;"},
                {"val":"gte", "name":"&#8804;"},
                {"val":"lte", "name":"&#8805;"} ]}

        elif filter_type == 'Location':
            return {"name": name, "help": "The location of the publication", "type":"text"}

        elif filter_type == 'Geography':
            return {"name": name, "help": "The location of the news article", "type":"text"}

        elif filter_type == 'Industry':
            return {"name": name, "help": "The industry associated with the news article", "type":"text"}

        elif filter_type == 'Subject':
            return {"name": name, "help": "The subject matter of the news article", "type":"text"}

        elif filter_type == 'Section':
            return {"name": name, "help": "The section of the news article", "type":"text"}

        elif filter_type == 'Company':
            return {"name": name, "help": "The company or companies associated with the news article", "type":"text"}

        elif filter_type == 'PublicationType':
            return {"name": name, "help": "The publication type associated with the news article", "type":"text"}

        elif filter_type == 'Publisher':
            return {"name": name, "help": "The publisher of the news article", "type":"text"}

        elif filter_type == 'People':
            return {"name": name, "help": "Well-known people referenced by the news article", "type":"text"}
        


        # Handle all of the plain text fields without help text
        else:
            return {"name": name, "type":"text"}

    def getEnumNamespace(self, filter_type):
        '''
        Retrieve the LexisNexis namespace that should be associated with a filter value
        when calling the API
        '''
        # handle special case for post filter negative news type
        if filter_type in ['NegativeNewsType','NegativeNews']:
            return 'LexisNexis.ServicesApi.NegativeNewsType'
        if filter_type in ['Language','GroupDuplicates','SearchType']:
            return 'LexisNexis.ServicesApi.' + filter_type
        else:
            return ''
