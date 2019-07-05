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

class LN_API:
    '''
    API for Lexis Nexis
    '''

    def __init__(self):
        '''
        Initialize the object and authenticate against the API
        '''
        self.limits = apps.get_model('textassembler_processor', 'limits')
        self.api_log = apps.get_model('textassembler_processor', 'api_log')
        self.access_token = None
        self.expiration_time = None

        self.throttles = None
        self.requests_per_min = None
        self.requests_per_hour = None
        self.requests_per_day = None
        self.downloads_per_min = None
        self.downloads_per_hour = None
        self.downloads_per_day = None

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

        if access_token_response.status_code == requests.codes.ok:
            tokens = access_token_response.json()
            self.access_token = tokens['access_token']
            self.expiration_time = timezone.now() + datetime.timedelta(seconds=int(tokens['expires_in']))
            return ""
        else:
            results = access_token_response.json()
            log_error("Error occured obtaining access token. Return code: {0}. Response:".format(access_token_response.status_code), results)
            if "error" in results and "message" in results["error"]:
                return results["error"]["message"]
            else:
                return "An unexpected error occured."


    def refresh_throttle_data(self, display=False):
        '''
        Get the current throttle data from the database
        '''

        # Get the current number of searches and downloads per the current min/hr/day

        self.requests_per_min = self.api_log.objects.filter(request_date__gte=timezone.now() - datetime.timedelta(minutes=1))
        self.requests_per_hour = self.api_log.objects.filter(request_date__gte=timezone.now()- datetime.timedelta(hours=1))
        self.requests_per_day = self.api_log.objects.filter(request_date__gte=timezone.now() - datetime.timedelta(days=1))

        # Compare against the limits for min/hr/day
        throttles = self.limits.objects.all()
        if throttles.count() == 0:
            log_error("No record exists in the database containing the throttling limitations!")
        if throttles.count() > 1:
            log_error("More than one record exists in the database for the throttling limitations!")

        self.throttles = throttles[0]

        if display:
            logging.info("Current search limits: {0}/min, {1}/hr, {2}/day out of {3}/min, {4}/hr, {5}/day".format(
                self.requests_per_min.count(), self.requests_per_hour.count(), self.requests_per_day.count(),
                self.throttles.searches_per_minute, self.throttles.searches_per_hour, self.throttles.searches_per_day))

            logging.info("Current download limits: {0}/min, {1}/hr, {2}/day out of {3}/min, {4}/hr, {5}/day".format(
                self.requests_per_min.filter(is_download=True).count(),
                self.requests_per_hour.filter(is_download=True).count(),
                self.requests_per_day.filter(is_download=True).count(),
                self.throttles.downloads_per_minute, self.throttles.downloads_per_hour,
                self.throttles.downloads_per_day))

    def check_can_search(self):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more

        returns: bool can_search
        '''

        self.refresh_throttle_data(True)
    
        if self.requests_per_min.count() < self.throttles.searches_per_minute \
            and self.requests_per_hour.count() < self.throttles.searches_per_hour and \
            self.requests_per_day.count() < self.throttles.searches_per_day:
            return True

        return False

    def check_can_download(self):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more

        returns: (bool,bool) can_search, can_download
        '''

        self.refresh_throttle_data(True)

        if self.requests_per_min.filter(is_download=True).count() < self.throttles.downloads_per_minute \
            and self.requests_per_hour.filter(is_download=True).count() < self.throttles.downloads_per_hour \
            and self.requests_per_day.filter(is_download=True).count() < self.throttles.downloads_per_day:
            return True

        return False

    def get_time_until_next_search(self):
        '''
        Gets the number of seconds until we can perform the next search
        '''

        self.refresh_throttle_data()

        # Available now
        if self.requests_per_min.count() < self.throttles.searches_per_minute  \
            and self.requests_per_hour.count() < self.throttles.searches_per_hour \
            and self.requests_per_day.count() < self.throttles.searches_per_day:
            return 0

        # Calculate
        if self.requests_per_day.count() >= self.throttles.searches_per_day:
            return ((timezone.now() + datetime.timedelta(days=1)) - timezone.now()).total_seconds()
        if self.requests_per_hour.count() >= self.throttles.searches_per_hour:
            return ((timezone.now() + datetime.timedelta(hours=1)) - timezone.now()).total_seconds()
        if self.requests_per_min.count() >= self.throttles.searches_per_minute:
            return ((timezone.now() + datetime.timedelta(minutes=1)) - timezone.now()).total_seconds()

    def get_time_until_next_download(self):
        '''
        Gets the number of seconds until we can perform the next download
        '''

        self.refresh_throttle_data()

        # Available now
        if self.requests_per_min.filter(is_download=True).count() < self.throttles.downloads_per_minute  \
            and self.requests_per_hour.filter(is_download=True).count() < self.throttles.downloads_per_hour \
            and self.requests_per_day.filter(is_download=True).count() < self.throttles.downloads_per_day:
            return 0

        # Calculate
        if self.requests_per_day.filter(is_download=True).count() >= self.throttles.downloads_per_day:
            return ((timezone.now() + datetime.timedelta(days=1)) - timezone.now()).total_seconds()
        if self.requests_per_hour.filter(is_download=True).count() >= self.throttles.downloads_per_hour:
            return ((timezone.now() + datetime.timedelta(hours=1)) - timezone.now()).total_seconds()
        if self.requests_per_min.filter(is_download=True).count() >= self.throttles.downloads_per_minute:
            return ((timezone.now() + datetime.timedelta(minutes=1)) - timezone.now()).total_seconds()

    def api_call(self, req_type='GET', resource='News', params={}):
        '''
        Calls the API given the request type, resource, and parameters. Returns the response
        '''

        is_download = True if "$expand" in params else False

        # Make sure we are within the API throttling limits
        if is_download and not self.check_can_download():
            seconds = self.get_time_until_next_download()
            time = seconds_to_dhms_string(seconds)
            return {"error_message":"There are no LexisNexis downloads remaining for the current min/hour/day. Next available in {0}".format(time)}

        if not self.check_can_search():
            seconds = self.get_time_until_next_search()
            time = seconds_to_dhms_string(seconds)
            return {"error_message":"There are no LexisNexis searches remaining for the current min/hour/day. Next available in {0}".format(time)}

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
        result_count = resp.json()["@odata.count"] if resp.status_code == requests.codes.ok and "@odata.count" in resp.json().keys() else 0
        self.api_log.objects.create(
            request_url=resp.url,
            request_type=req_type,
            response_code=resp.status_code,
            num_results=result_count,
            is_download=is_download)

        results = resp.json()
        if resp.status_code == requests.codes.ok:
            return results

        else:
            log_error("Call to {0} failed with code {1}. Response: ".format(url, resp.status_code), results)
            if "error" in results and "message" in results:
                return {"error_message":"Error: {0}. Message: {1}".format(results["error"], results["message"]),
                        "response_code": resp.status_code}
            elif "ErrorDescription" in results:
                return {"error_message":"Error: {0}.".format(results["ErrorDescription"]), 
                        "response_code": resp.status_code}
            else:
                return {"error_message": "An unexpected API error occured.", 
                        "response_code": resp.status_code}


    def search(self, term="", set_filters={}):
        '''
        Search the API given the search term and filters.
        @return API results
        '''
        filters = self.convert_filters_to_query_string(set_filters)

        # Always provide the $exand=PostFilters so we can provide them to the UI
        params = {"$search":term, "$expand": "PostFilters"}

        if filters:
            params['$filter'] = filters

        return self.api_call(resource='News', params=params)

    def download(self, term="", set_filters={}, download_cnt=10, skip=0):
        '''
        Download the full-text results from the API given the search term and filters.
        @return API results with full text
        '''
        filters = self.convert_filters_to_query_string(set_filters)

        # Always provide the $exand=Document so we get the full text result
        params = {"$search":term, "$expand": "Document", "$top": download_cnt, "$skip": skip}

        if filters:
            params['$filter'] = filters

        return self.api_call(resource='News', params=params)

    def convert_filters_to_query_string(self, set_filters={}):
        '''
        Processes the filters and turns them into parameters for the API.
        Filters from the same field will be treated as AND
        Filters from different fields will be treated with OR
        '''
        from .filters import Filters

        filters = ""
        filter_data = Filters()

        logging.debug(set_filters)

        for key, values in set_filters.items():
            namespace = filter_data.getEnumNamespace(key)
            fmt = filter_data.getFormatType(key)

            # convert the value(s) to base64 if the filter expects it
            if fmt == 'base64':
                # need to put this in a temp variable first to avoid updating the original variable when returned
                # this caused a problem for full text results since the 2nd call would double encode the values
                tmp = [base64.b64encode(val.encode('utf-8')).decode("utf-8").replace("=", "") for val in values]
                values = tmp

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
                    logging.debug("===" + str(values[i]) + " " + str(values[i+1]) + "===")
                    filters += key.replace('_', '/') + " " + values[i] + " " + values[i+1] + " and "
                filters = filters[:-5] # remove the last AND
                filters += ")"

            else:
                if len(values) == 1:
                    # The API expects strings to have single quoates around the values
                    if isinstance(values[0], int) or self.string_is_int(values[0]):
                        filters += key.replace('_', '/') + " eq " + namespace + str(values[0]) + " "
                    else:
                        filters += key.replace('_', '/') + " eq " + namespace + "'" + values[0] + "' "
                else:
                    filters += " ("
                    for value in values:
                        # The API expects strings to have single quoates around the values
                        if isinstance(value, int) or self.string_is_int(value):
                            filters += key.replace('_', '/') + " eq " + namespace + str(value) + " or "
                        else:
                            filters += key.replace('_', '/') + " eq " + namespace + "'" + value + "' or "
                    filters = filters[:-4] # remove the last OR
                    filters += ")"

        return filters


    def string_is_int(self, s_val):
        '''
        Check if the string contains an integer since isinstance will return
        false for strings with an integer.
        '''

        try:
            int(s_val)
            return True
        except ValueError:
            return False
