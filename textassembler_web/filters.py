"""
Retrieve the available filters to use for searching
"""
from .models import sources

def get_available_filters(include_all=True):
    '''
    The id field matches the filter in the API $filter value, replace / with _
    The name is what to display on the page

    The 'help' field will be displayed in a popover on the page. It can include
    HTML elements, but ensure that all quotes are double quotes (") or the JS will
    have issues rendering it.
    '''

    # Removed fields from dropdown that only accept coded values as input in the
    # API. Ex: Alaska expects US-AK for location, and Google expects CC00055NZ for company
    filter_opts = [{"id":"Language", "name":"Language"},
                   {"id":"Source_Id", "name":"Source"},
                   {"id":"Date", "name":"Date Range"},
                   {"id":"year(Date)", "name":"Year"},
                   {"id":"NegativeNews", "name":"Negative News Type"},
                   {"id":"GroupDuplicates", "name":"Group Duplicates"},
                   {"id":"SearchType", "name": "Search Type"},
                   {"id":"PublicationType", "name": "Publication Type"},
                   {"id":"Publisher", "name": "Publisher"},
                   {"id":"location", "name": "location"},
                   {"id":"geography", "name": "geography"},
                   {"id":"industry", "name": "industry"},
                   {"id":"Subject", "name": "Subject"},
                   {"id":"Section", "name": "Section"},
                   {"id":"Company", "name": "Company"},
                   {"id":"People", "name":"People"}
                  ]

    if not include_all:
        filter_opts = [x for x in filter_opts if x['id'].lower() not in ['location', 'geography', 'industry', 'subject', 'section', 'company', 'people']]

    return filter_opts

def get_filter_values(filter_type): #pylint: disable=too-many-branches
    '''
    Get the data for the given filter for the UI.
    This includes the data type, help text, and available options
    where applicable.
    '''

    vals = {}
    name = get_available_filters()
    found_filters = [x['name'] for x in name if x['id'] == filter_type]
    if len(found_filters) == 1:
        name = found_filters[0]
    else:
        name = filter_type

    if filter_type == 'Language':
        vals = {'name':name, 'type':'select',
                'help':'Filters the articles by the language they were written in',
                'choices':[
                    {'val':'English', 'name':'English'},
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
        vals = {'name':name, 'type':'select',
                'help':'Whether or not the news article is considered negative in either the personal or business context',
                'choices':[
                    {'val':'Personal', 'name':'Personal',},
                    {'val':'Business', 'name':'Business'}]}

    elif filter_type == 'GroupDuplicates':
        vals = {'name':name, 'type':'select',
                'help':'The degree to which duplicate search results are grouped into single items',
                'choices':[
                    {'val':'HighSimilarity', 'name':'High Similarity',},
                    {'val':'ModerateSimilarity', 'name':'Moderate Similarity'}]}

    elif filter_type == 'SearchType':
        vals = {'name':name, 'type':'select',
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
        for source in sources.objects.all().filter(active=True):
            results.append({"val":source.source_id, "name":source.source_name})
        vals = {'name':'Source', 'type':'select',
                'help':'The content source that is searched',
                'choices':results}

    elif filter_type == 'Date':
        vals = {'name':'Date', "type":"date",
                'help':'The publication date',
                "choices":[
                    {"val":"gt", "name":"(&#62;) Greater than"},
                    {"val":"lt", "name":"(&#60;) Less than"},
                    {"val":"gte", "name":"(&#8805;) Greater than or equal to"},
                    {"val":"lte", "name":"(&#8804;) Less than or equal to"}]}

    elif filter_type == 'Location':
        vals = {"name": name, "help": "The location of the publication", "type":"text"}

    elif filter_type == 'Geography':
        vals = {"name": name, "help": "The location of the news article", "type":"text"}

    elif filter_type == 'Industry':
        vals = {"name": name, "help": "The industry associated with the news article", "type":"text"}

    elif filter_type == 'Subject':
        vals = {"name": name, "help": "The subject matter of the news article", "type":"text"}

    elif filter_type == 'Section':
        vals = {"name": name, "help": "The section of the news article", "type":"text"}

    elif filter_type == 'Company':
        vals = {"name": name, "help": "The company or companies associated with the news article", "type":"text"}

    elif filter_type == 'PublicationType':
        vals = {"name": name, "help": "The publication type associated with the news article", "type":"text"}

    elif filter_type == 'Publisher':
        vals = {"name": name, "help": "The publisher of the news article", "type":"text"}

    elif filter_type == 'People':
        vals = {"name": name, "help": "Well-known people referenced by the news article", "type":"text"}

    # Handle all of the plain text fields without help text
    else:
        vals = {"name": name, "type":"text"}

    return vals

def get_enum_namespace(filter_type):
    '''
    Retrieve the LexisNexis namespace that should be associated with a filter value
    when calling the API
    '''
    e_ns = ''
    # handle special case for post filter negative news type
    if filter_type in ['NegativeNewsType', 'NegativeNews']:
        e_ns = 'LexisNexis.ServicesApi.NegativeNewsType'
    if filter_type in ['Language', 'GroupDuplicates', 'SearchType']:
        e_ns = 'LexisNexis.ServicesApi.' + filter_type
    return e_ns

def get_format_type(filter_type):
    '''
    Retrieve the format that LexisNexis expects for the given filter when
    calling the API.
    '''
    f_type = 'text'
    if filter_type.lower() in ['publicationtype', 'location', 'company', 'people', 'geography', 'industry', 'subject', 'section']:
        f_type = 'base64'
    return f_type
