"""
Search the LexisNexis API
"""
import logging
import requests
import json
from django.conf import settings
import datetime
from django.apps import apps
from django.utils import timezone
from .utilities import log_error

class Search:
    
    def __init__(self):
        self.limits = apps.get_model('textassembler_processor','limits')
        self.api_log = apps.get_model('textassembler_processor','api_log')
        self.access_token = None
        self.expiration_time = None

        self.api_url = settings.LN_API_URL
        if not self.api_url.endswith("/"):
            self.api_url += "/"

        self.authenticate()

    def authenticate(self):
        # Do not get a new token since the current one is still valid 
        if self.access_token is not None and self.expiration_time is not None and timezone.now() <= self.expiration_time:
            return 

        logging.info("Obtaining new access token")
        data = {'grant_type': 'client_credentials',
            'scope': settings.LN_SCOPE}

        access_token_response = requests.post(settings.LN_TOKEN_URL, 
            data=data, verify=True, 
            auth=(settings.LN_CLIENT_ID, settings.LN_CLIENT_SECRET))

        if access_token_response.status_code == requests.codes.ok:
            tokens = access_token_response.json()
            self.access_token = tokens['access_token']
            self.expiration_time = timezone.now() + datetime.timedelta(seconds=int(tokens['expires_in']))

        else:
            results = access_token_response.json()
            log_error("Error occured obtaining access token. Return code: {0}. Response:".format(access_token_response.status_code), results)
            if "error" in results and "message" in results["error"]:
                return results["error"]["message"]
            else:
                return "An unexpected error occured."

        return ""


    def refresh_throttle_data(self):
        # Get the current number of searches and downloads per the current min/hr/day

        self.requests_per_min = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(minutes=1))
        self.requests_per_hour = self.api_log.objects.filter(request_date__gte = timezone.now()- datetime.timedelta(hours=1))
        self.requests_per_day = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(days=1))

        # Compare against the limits for min/hr/day
        throttles = self.limits.objects.all()
        if throttles.count() == 0:
            log_error("No record exists in the database containing the throttling limitations!")
            return False
        if throttles.count() > 1:
            log_error("More than one record exists in the database for the throttling limitations!")

        self.throttles = throttles[0]

        logging.info("Current limits: {0}/min, {1}/hr, {2}/day out of {3}/min, {4}/hr, {5}/day".format(
            self.requests_per_min.count(), self.requests_per_hour.count(), self.requests_per_day.count(),
            self.throttles.searches_per_minute, self.throttles.searches_per_hour, self.throttles.searches_per_day))

    def check_can_search(self):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more

        returns: bool can_search
        '''

        self.refresh_throttle_data()

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

        self.refresh_throttle_data()

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

    def api_call(self, req_type='GET', resource='News', params = {}):
        '''
        Calls the API given the request type, resource, and parameters. Returns the response
        '''

        is_download = True if "$expand" in params else False

        # Make sure we are within the API throttling limits
        if is_download and not self.check_can_download():
            # We are out of downloads for the timeframe
            return {"error_message":"There are no downloads remaining for the current min/hour/day"}

        if not self.check_can_search():
            # We are out of searches for the timeframe
            return {"error_message":"There are no searches remaining for the current min/hour/day"}

        error_message = self.authenticate()
        if error_message:
            return {"error_message": error_message}

        headers = {"Authorization": "Bearer " + self.access_token}
        url = self.api_url + resource
    
        if req_type == "GET":
            resp = requests.get(url, params=params, headers=headers)
        if req_type == "POST":
            resp = requests.post(url, params=params, headers=headers)

        # Log the API call
        result_count =  resp.json()["@odata.count"] if resp.status_code == requests.codes.ok and "@odata.count" in resp.json().keys() else 0
        self.api_log.objects.create(
            request_url = url,
            request_type = req_type,
            response_code = resp.status_code,
            num_results = result_count,
            is_download = is_download)

        results = resp.json()
        if resp.status_code == requests.codes.ok:
            return results

        else:
            log_error("Call to {0} failed with code {1}. Response: ".format(url, resp.status_code), results)
            if "error" in results and "message" in results["error"]:
                return {"error_message":results["error"]["message"]}
            else:
                return {"error_message": "An unexpected error occured."}


    def search(self, term = "", set_filters = {}):
        '''
        Processes the filters and turns them into parameters for the API.
        Filters from the same field will be treated as AND
        Filters from different fields will be treated with OR
        '''
        from .filters import Filters
        
        filters = ""
        filter_data = Filters()

        for key, values in set_filters.items():
            namespace = filter_data.getEnumNamespace(key)

            if filters != '':
                filters += " and "

            # Handle dates separately
            if key == 'Date':
                for i in range(0,len(values),2):
                    filters += key.replace('_','/') + " " + values[i] + " " + values[i+1] + " and "
                filters = filters[:-5]

            else:
                if len(values) == 1:
                    filters += key.replace('_','/') + " eq " + namespace + "'" + values[0] + "' "
                else:
                    for value in values:
                        filters += key.replace('_','/') + " eq " + namespace + "'" + value + "' or "
                    filters = filters[:-4] # remove the last OR

        print(filters)

        params = {"$search":term, "$expand": "PostFilters"}
        if len(filters) > 0:
            params['$filter'] = filters

        return self.api_call(resource='News', params=params)

