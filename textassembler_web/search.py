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

        print("Obtaining new access token")
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
            pass # TODO handle bad request/response

    def check_can_search(self):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more

        returns: bool can_search
        '''

        # Get the current number of searches and downloads per the current min/hr/day

        requests_per_min = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(minutes=1))
        requests_per_hour = self.api_log.objects.filter(request_date__gte = timezone.now()- datetime.timedelta(hours=1))
        requests_per_day = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(days=1))

        # Compare against the limits for min/hr/day
        throttles = self.limits.objects.all()
        if throttles.count() != 1:
            pass # TODO handle/raise error for the record not existing, or too many existing

        throttles = throttles[0]

        if requests_per_min.count() < throttles.searches_per_minute and requests_per_hour.count() < throttles.searches_per_hour and \
            requests_per_day.count() < throttles.searches_per_day:
            return True

        logging.info("Current limits: {0}/min, {1}/hr, {2}/day out of {3}/min, {4}/hr, {5}/day".format(
            requests_per_min.count(),requests_per_hour.count(),requests_per_day.count(),
            throttles.searches_per_minute,throttles.searches_per_hour,throttles.searches_per_day))

        return False

    def check_can_download(self):
        '''
        Checks the remaining searches available per min/hr/day to see if we are able to do any more
        
        returns: (bool,bool) can_search, can_download
        '''

        # Get the current number of searches and downloads per the current min/hr/day
        
        requests_per_min = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(minutes=1))
        requests_per_hour = self.api_log.objects.filter(request_date__gte = timezone.now()- datetime.timedelta(hours=1))
        requests_per_day = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(days=1))


        # Compare against the limits for min/hr/day
        throttles = self.limits.objects.all()
        if throttles.count() != 1:
            pass # TODO handle/raise error for the record not existing, or too many existing

        throttles = throttles[0]

        if requests_per_min.filter(is_download=True).count() < throttles.downloads_per_minute \
            and requests_per_hour.filter(is_download=True).count() < throttles.downloads_per_hour \
            and requests_per_day.filter(is_download=True).count() < throttles.downloads_per_day:
            return True
        
        logging.info("Current limits: {0}/min, {1}/hr, {2}/day out of {3}/min, {4}/hr, {5}/day".format(
            requests_per_min.count(),requests_per_hour.count(),requests_per_day.count(),
            throttles.searches_per_minute,throttles.searches_per_hour,throttles.searches_per_day))

        return False 

    def get_time_until_next_search(self):
        '''
        Gets the number of seconds until we can perform the next search
        '''

        # Get the current number of searches and downloads per the current min/hr/day
        requests_per_min = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(minutes=1))
        requests_per_hour = self.api_log.objects.filter(request_date__gte = timezone.now()- datetime.timedelta(hours=1))
        requests_per_day = self.api_log.objects.filter(request_date__gte = timezone.now() - datetime.timedelta(days=1))


        # Compare against the limits for min/hr/day
        throttles = self.limits.objects.all()
        if throttles.count() != 1:
            pass # TODO handle/raise error for the record not existing, or too many existing

        throttles = throttles.first()
        # Available now
        if requests_per_min.count() < throttles.searches_per_minute and requests_per_hour.count() < throttles.searches_per_hour \
            and requests_per_day.count() < throttles.searches_per_day:
            return 0

        logging.info("Current limits: {0}/min, {1}/hr, {2}/day out of {3}/min, {4}/hr, {5}/day".format(
            requests_per_min.count(),requests_per_hour.count(),requests_per_day.count(),
            throttles.searches_per_minute,throttles.searches_per_hour,throttles.searches_per_day))

        if requests_per_day.count() >= throttles.searches_per_day:
            return ((timezone.now() + datetime.timedelta(days=1)) - timezone.now()).total_seconds()
        if requests_per_hour.count() >= throttles.searches_per_hour:
            return ((timezone.now() + datetime.timedelta(hours=1)) - timezone.now()).total_seconds()
        if requests_per_min.count() >= throttles.searches_per_minute:
            return ((timezone.now() + datetime.timedelta(minutes=1)) - timezone.now()).total_seconds()

    def api_call(self, req_type='GET', resource='News', params = {}):
        '''
        Calls the API given the request type, resource, and parameters. Returns the response
        '''

        is_download = True if "$expand" in params else False

        # Make sure we are within the API throttling limits
        if is_download and not check_can_download():
            # We are out of downloads for the timeframe
            return {"error_message":"There are no downloads remaining for the current min/hour/day"}

        if not self.check_can_search():
            # We are out of searches for the timeframe
            return {"error_message":"There are no searches remaining for the current min/hour/day"}

        self.authenticate()
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
            logging.error("Call to {0} failed with code {1}. Response: ".format(url, resp.status_code))
            logging.error(results)
            if "error" in results and "message" in results["error"]:
                return {"error_message":results["error"]["message"]}
            else:
                return {"error_message": "An unexpected error occured."}


    def search(self, term = ""):
        params = {"$search":term}
        return self.api_call(resource='News', params=params)

