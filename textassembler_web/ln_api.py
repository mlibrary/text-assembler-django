"""
Search the LexisNexis API
"""
import logging
import base64
import datetime
import requests
from django.conf import settings
from django.apps import apps
from django.utils import timezone
from .utilities import log_error, seconds_to_dhms_string
from .filters import get_enum_namespace, get_format_type

class LNAPI:
    '''
    API for Lexis Nexis
    '''

    def __init__(self):
        '''
        Initialize the object and authenticate against the API
        '''
        self.api_log = apps.get_model('textassembler_processor', 'api_log')
        self.access_token = None
        self.expiration_time = None

        self.requests_per_min = None
        self.requests_per_hour = None
        self.requests_per_day = None

        self.api_url = settings.LN_API_URL
        if not self.api_url.endswith("/"):
            self.api_url += "/"

        self.authenticate()

    def authenticate(self):
        '''
        Authenticate against the LexisNexis API to obtain an access token, if we already have one
        that has not expired, do nothing.
        '''

        # Do not get a new token since the current one is still valid
        if self.access_token is not None and self.expiration_time is not None and timezone.now() <= self.expiration_time:
            return ""

        logging.info("Obtaining new access token")
        data = {'grant_type': 'client_credentials',
                'scope': settings.LN_SCOPE}

        access_token_response = requests.post(settings.LN_TOKEN_URL, \
            data=data, verify=True, \
            auth=(settings.LN_CLIENT_ID, settings.LN_CLIENT_SECRET), \
            timeout=settings.LN_TIMEOUT)

        if access_token_response.status_code == requests.codes.ok: #pylint: disable=no-member
            tokens = access_token_response.json()
            self.access_token = tokens['access_token']
            self.expiration_time = timezone.now() + datetime.timedelta(seconds=int(tokens['expires_in']))
        else:
            results = access_token_response.json()
            log_error(f"Error occurred obtaining access token. Return code: {access_token_response.status_code}. Response:", results)
            error = "An unexpected error occurred."
            if "error" in results and "message" in results["error"]:
                error = results["error"]["message"]
            return error
        return ""


    def refresh_throttle_data(self, display=False):
        '''
        Get the current throttle data from the database
        '''

        # Get the current number of searches and downloads per the current min/hr/day

        self.requests_per_min = self.api_log.objects.filter(request_date__gte=timezone.now() - datetime.timedelta(minutes=1))
        self.requests_per_hour = self.api_log.objects.filter(request_date__gte=timezone.now()- datetime.timedelta(hours=1))
        self.requests_per_day = self.api_log.objects.filter(request_date__gte=timezone.now() - datetime.timedelta(days=1))

        # validate trottle settings
        if not settings.SEARCHES_PER_MINUTE or not settings.SEARCHES_PER_HOUR or \
            not settings.SEARCHES_PER_DAY:
            log_error("API search limits are not properly configured")
        if not settings.DOWNLOADS_PER_MINUTE or not settings.DOWNLOADS_PER_HOUR or \
            not settings.DOWNLOADS_PER_DAY:
            log_error("API download limits are not properly configured")

        if not settings.WEEKDAY_START_TIME or not settings.WEEKDAY_END_TIME or \
            not settings.WEEKEND_START_TIME or not settings.WEEKEND_START_TIME:
            log_error("API processing start and end times not properly configured")

        # Compare against the limits for min/hr/day
        if display:
            logging.debug((f"Current search limits: {self.requests_per_min.count()}/min, "
                           f"{self.requests_per_hour.count()}/hr, {self.requests_per_day.count()}/day "
                           f"out of {settings.SEARCHES_PER_MINUTE}/min, {settings.SEARCHES_PER_HOUR}/hr, {settings.SEARCHES_PER_DAY}/day"))

            logging.debug((f"Current download limits: {self.requests_per_min.filter(is_download=True).count()}/min,"
                           f" {self.requests_per_hour.filter(is_download=True).count()}/hr, {self.requests_per_day.filter(is_download=True).count()}/day"
                           f" out of {settings.DOWNLOADS_PER_MINUTE}/min, {settings.DOWNLOADS_PER_HOUR}/hr, {settings.DOWNLOADS_PER_DAY}/day"))

    def check_can_search(self):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more

        returns: bool can_search
        '''

        self.refresh_throttle_data(True)

        if self.requests_per_min.count() < settings.SEARCHES_PER_MINUTE \
            and self.requests_per_hour.count() < settings.SEARCHES_PER_HOUR and \
            self.requests_per_day.count() < settings.SEARCHES_PER_DAY:
            return True

        return False

    def check_can_download(self, processing=False):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more

        returns: (bool) can_download
        '''

        self.refresh_throttle_data(True)

        #  check that we are within the valid processing time window
        if processing:
            # determine if it is currently a weekend or weekday
            is_weekday = datetime.datetime.today().weekday() < 5
            now = datetime.datetime.now()

            if is_weekday:
                start_time = datetime.datetime.now().replace(hour=settings.WEEKDAY_START_TIME.hour,\
                    minute=settings.WEEKDAY_START_TIME.minute,second=0,microsecond=0)
                end_time = datetime.datetime.now().replace(hour=settings.WEEKDAY_END_TIME.hour,\
                    minute=settings.WEEKDAY_END_TIME.minute,second=0,microsecond=0)

                end_is_next_day = settings.WEEKDAY_END_TIME < settings.WEEKDAY_START_TIME
            else:
                start_time = datetime.datetime.now().replace(hour=settings.WEEKEND_START_TIME.hour,\
                    minute=settings.WEEKEND_START_TIME.minute,second=0,microsecond=0)
                end_time = datetime.datetime.now().replace(hour=settings.WEEKEND_END_TIME.hour,\
                    minute=settings.WEEKEND_END_TIME.minute,second=0,microsecond=0)

                end_is_next_day = settings.WEEKEND_END_TIME < settings.WEEKEND_START_TIME
                
            if end_is_next_day:
                end_time = end_time + datetime.timedelta(days=1)
            
            if now < start_time or now > end_time:
                message = (
                    f"Not during the valid processing window. "
                    f"Start time: {start_time.strftime('%A %I:%M%p')} "
                    f"End time: {end_time.strftime('%A %I:%M%p')}")
                logging.debug(message)
                return False

        if self.requests_per_min.filter(is_download=True).count() < settings.DOWNLOADS_PER_MINUTE \
            and self.requests_per_hour.filter(is_download=True).count() < settings.DOWNLOADS_PER_HOUR \
            and self.requests_per_day.filter(is_download=True).count() < settings.DOWNLOADS_PER_DAY:
            return True

        return False

    def get_time_until_next_search(self):
        '''
        Gets the number of seconds until we can perform the next search
        '''

        self.refresh_throttle_data()

        # Available now
        if self.requests_per_min.count() < settings.SEARCHES_PER_MINUTE  \
            and self.requests_per_hour.count() < settings.SEARCHES_PER_HOUR \
            and self.requests_per_day.count() < settings.SEARCHES_PER_DAY:
            return 0

        # Calculate
        if self.requests_per_day.count() >= settings.SEARCHES_PER_DAY:
            return ((timezone.now() + datetime.timedelta(days=1)) - timezone.now()).total_seconds()
        if self.requests_per_hour.count() >= settings.SEARCHES_PER_HOUR:
            return ((timezone.now() + datetime.timedelta(hours=1)) - timezone.now()).total_seconds()
        if self.requests_per_min.count() >= settings.SEARCHES_PER_MINUTE:
            return ((timezone.now() + datetime.timedelta(minutes=1)) - timezone.now()).total_seconds()

        return 0

    def get_time_until_next_download(self):
        '''
        Gets the number of seconds until we can perform the next download.
        Does not account for run window
        '''

        self.refresh_throttle_data()
        seconds = 0
        seconds_window = 0

        # Available now
        if self.check_can_download(True):
            return 0

        # Calculate
        if self.requests_per_day.filter(is_download=True).count() >= settings.DOWNLOADS_PER_DAY:
            seconds = ((timezone.now() + datetime.timedelta(days=1)) - timezone.now()).total_seconds()
        if self.requests_per_hour.filter(is_download=True).count() >= settings.DOWNLOADS_PER_HOUR:
            seconds = ((timezone.now() + datetime.timedelta(hours=1)) - timezone.now()).total_seconds()
        if self.requests_per_min.filter(is_download=True).count() >= settings.DOWNLOADS_PER_MINUTE:
            seconds = ((timezone.now() + datetime.timedelta(minutes=1)) - timezone.now()).total_seconds()


        is_weekday = datetime.datetime.today().weekday() < 5

        if is_weekday:
            start_date = datetime.datetime.combine(datetime.date.today(), settings.WEEKDAY_START_TIME)
        else:
            start_date = datetime.datetime.combine(datetime.date.today(), settings.WEEKEND_START_TIME)
        delta = start_date  - datetime.datetime.now()
        seconds_window = delta.total_seconds()


        if seconds > seconds_window:
            return seconds
        return seconds_window

    def api_call(self, req_type='GET', resource='News', params=None):
        '''
        Calls the API given the request type, resource, and parameters. Returns the response
        '''

        is_download = True if "$expand" in params else False

        # Make sure we are within the API throttling limits
        if is_download and not self.check_can_download():
            time = seconds_to_dhms_string(self.get_time_until_next_download())
            return {"error_message":f"There are no LexisNexis downloads remaining for the current min/hour/day. Next available in {time}"}

        if not self.check_can_search():
            time = seconds_to_dhms_string(self.get_time_until_next_search())
            return {"error_message":f"There are no LexisNexis searches remaining for the current min/hour/day. Next available in {time}"}

        error_message = self.authenticate()
        if error_message:
            return {"error_message": error_message}

        headers = {"Authorization": "Bearer " + self.access_token}
        url = self.api_url + resource

        if req_type == "GET":
            resp = requests.get(url, params=params, headers=headers, timeout=settings.LN_TIMEOUT)
        if req_type == "POST":
            resp = requests.post(url, params=params, headers=headers, timeout=settings.LN_TIMEOUT)

        # Log the API call
        result_count = resp.json()["@odata.count"] if resp.status_code == requests.codes.ok and "@odata.count" in resp.json().keys() else 0  #pylint: disable=no-member
        self.api_log.objects.create(
            request_url=resp.url,
            request_type=req_type,
            response_code=resp.status_code,
            num_results=result_count,
            is_download=is_download)

        results = resp.json()
        if resp.status_code == requests.codes.ok:   #pylint: disable=no-member
            return results

        else:
            error_message = "An unexpected API error occurred."
            full_error_message = f"Call to {resp.url} failed with code {resp.status_code}. Response: "
            log_error(full_error_message, results)
            if "error" in results and "message" in results:
                error_message = f"Error: {results['error']}. Message: {results['message']}"
            elif "ErrorDescription" in results:
                error_message = f"Error: {results['ErrorDescription']}."
            return {"error_message": error_message,
                    "response_code": resp.status_code}


    def search(self, term="", set_filters=None):
        '''
        Search the API given the search term and filters.
        @return API results
        '''
        filters = convert_filters_to_query_string(set_filters)

        # Always provide the $exand=PostFilters so we can provide them to the UI
        params = {"$search":term, "$expand": "PostFilters"}

        if filters:
            params['$filter'] = filters

        return self.api_call(resource='News', params=params)

    def download(self, term="", set_filters=None, download_cnt=10, skip=0):
        '''
        Download the full-text results from the API given the search term and filters.
        @return API results with full text
        '''
        filters = convert_filters_to_query_string(set_filters)

        # Always provide the $exand=Document so we get the full text result
        params = {"$search":term, "$expand": "Document", "$top": download_cnt, "$skip": skip}

        if filters:
            params['$filter'] = filters

        return self.api_call(resource='News', params=params)

def convert_filters_to_query_string(set_filters=None): # pylint: disable=too-many-branches
    '''
    Processes the filters and turns them into parameters for the API.
    Filters from the same field will be treated as AND
    Filters from different fields will be treated with OR
    '''
    filters = ""

    logging.debug("-- Set Filters --")
    logging.debug(set_filters)

    for key, values in set_filters.items():
        namespace = get_enum_namespace(key)

        values = encode_if_needed(key, values)

        if filters != '':
            filters += " and "

        # Handle dates separately since they have 2 values (start date and end date)
        if key == 'Date':
            if len(values[0]) > 3: # the values are stored together
                tmp = []
                for val in values:
                    tmp.append(val.split(" ")[0])
                    tmp.append(val.split(" ")[1])
                values = tmp
            filters += " ("
            for i in range(0, len(values), 2):
                filters += key.replace('_', '/') + " " + values[i] + " " + values[i+1] + " and "
            filters = filters[:-5] # remove the last AND
            filters += ")"

        else:
            if len(values) == 1:
                # The API expects strings to have single quotes around the values
                if isinstance(values[0], int) or string_is_int(values[0]):
                    filters += key.replace('_', '/') + " eq " + namespace + str(values[0]) + " "
                else:
                    filters += key.replace('_', '/') + " eq " + namespace + "'" + values[0] + "' "
            else:
                filters += " ("
                for value in values:
                    # The API expects strings to have single quotes around the values
                    if isinstance(value, int) or string_is_int(value):
                        filters += key.replace('_', '/') + " eq " + namespace + str(value) + " or "
                    else:
                        filters += key.replace('_', '/') + " eq " + namespace + "'" + value + "' or "
                filters = filters[:-4] # remove the last OR
                filters += ")"

    return filters


def encode_if_needed(field, values=None):
    '''
    Convert the value(s) to base64 if the filter expects it
    '''
    fmt = get_format_type(field)

    if fmt == 'base64':
        # need to put this in a temp variable first to avoid updating the original variable when returned
        # this caused a problem for full text results since the 2nd call would double encode the values
        tmp = [base64.b64encode(val.encode('utf-8')).decode("utf-8").replace("=", "") for val in values]
        values = tmp
    return values

def string_is_int(s_val):
    '''
    Check if the string contains an integer since isinstance will return
    false for strings with an integer.
    '''

    try:
        int(s_val)
        return True
    except ValueError:
        return False
