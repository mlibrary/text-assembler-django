"""
Search the LexisNexis API
"""
import logging
import base64
import datetime
import json
import requests
from django.conf import settings
from django.apps import apps
from django.utils import timezone
from django.db import OperationalError
from .utilities import log_error
from .filters import get_enum_namespace, get_format_type
from .models import api_limits, CallTypeChoice

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

    def check_when_available(self, limit_type='search'): # pylint:disable=too-many-return-statements, no-self-use
        '''
        Note: Disabling too many return statements since it keeps the code more readable
        Note: Disabling no self use because other classes use it and it makes more
        sence and class function that importing it as a utility separately

        Check how many seconds until the given service API is available to call
        returns: datetime when it is available again
        '''
        service = CallTypeChoice.SRH
        if limit_type == 'download':
            service = CallTypeChoice.DWL
        if limit_type == 'sources':
            service = CallTypeChoice.SRC

        limits = api_limits.objects.get(limit_type=service)
        (in_run_window, start_time) = is_in_run_window()

        # If it is for sources or search, or within the run window for downloads: check if available now
        if limit_type != 'download' or in_run_window:
            if limits.remaining_per_minute > 0 and limits.remaining_per_hour > 0 and limits.remaining_per_day > 0:
                return timezone.now()
            if limits.remaining_per_day == 0 and limits.reset_on_day < timezone.now():
                return timezone.now()
            if limits.remaining_per_hour == 0 and limits.reset_on_hour < timezone.now():
                return timezone.now()
            if limits.remaining_per_minute == 0 and limits.reset_on_minute < timezone.now():
                return timezone.now()
        # Else calculate time remaining to wait
        start_time = timezone.make_aware(start_time) if not timezone.is_aware(start_time) else start_time
        all_dates = [limits.reset_on_day, limits.reset_on_hour, limits.reset_on_minute, start_time]
        if limit_type == 'download':
            return max(all_dates)
        if limits.remaining_per_day == 0:
            return limits.reset_on_day
        if limits.remaining_per_hour == 0:
            return limits.reset_on_hour
        if limits.remaining_per_minute == 0:
            return limits.reset_on_minute

        # Failsafe, should never get to this point
        return timezone.now()

    def api_update_rate_limit(self, limit_type='search'):
        '''
        Calls the API, but returns only the header information to parse for the limit
        Returns: X-RateLimit-Limit
        '''
        error_message = self.authenticate()
        if error_message:
            return {"error_message": error_message}

        headers = {"Authorization": "Bearer " + self.access_token}
        resp = None

        # Call the API
        if limit_type.lower() == 'search':
            url = self.api_url + "News"
            resp = requests.get(url, params=None, headers=headers, timeout=settings.LN_TIMEOUT)

        elif limit_type.lower() == 'download':
            url = self.api_url + "News"
            resp = requests.get(url, params={"$expand": "Document"}, headers=headers, timeout=settings.LN_TIMEOUT)

        elif limit_type.lower() == 'sources':
            url = self.api_url + "Sources"
            resp = requests.get(url, params=None, headers=headers, timeout=settings.LN_TIMEOUT)

        # Log the API call
        self.api_log.objects.create(
            request_url=resp.url,
            request_type="GET",
            response_code=resp.status_code,
            num_results=0,
            is_download=True if limit_type.lower() == 'download' else False)

        # Update the limits
        update_limits(limit_type, resp.headers)

        return None

    def api_call(self, req_type='GET', resource='News', params=None):
        '''
        Calls the API given the request type, resource, and parameters. Returns the response
        '''

        is_download = True if "$expand" in params and params['$expand'] == "Document" else False
        service = 'search'
        service = 'download' if is_download else service
        service = 'sources' if resource == 'Sources' else service

        # Make sure we are within the API throttling limits
        avail_time = self.check_when_available(service)
        if avail_time > timezone.now():
            return {"error_message":f"There are no LexisNexis {service} remaining for the current min/hour/day. Next available at {avail_time}"}

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

        results = None
        try:
            results = resp.json()
        except json.decoder.JSONDecodeError:
            results = "[Could not parse response]"

        # Check response code
        if resp.status_code == requests.codes.ok: # pylint: disable=no-member
            update_limits(service, resp.headers)
            return results
        else:
            error_message = "An unexpected API error occurred."
            full_error_message = f"Call to {resp.url} failed with code {resp.status_code}. Response: "
            if settings.EMAIL_MAINTAINERS_ON_API_ERROR:
                log_error(full_error_message, results)
            else:
                logging.error(full_error_message)
                logging.error(results)
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

    def download(self, term="", set_filters=None, sort_order="Date", download_cnt=50, skip=0): # pylint: disable=too-many-arguments
        '''
        Download the full-text results from the API given the search term and filters.
        @return API results with full text
        '''
        filters = convert_filters_to_query_string(set_filters)

        # Always provide the $exand=Document so we get the full text result
        params = {"$search":term, "$expand": "Document", "$top": download_cnt, "$skip": skip}

        if filters:
            params['$filter'] = filters
        if sort_order:
            params["$orderby"] = sort_order

        return self.api_call(resource='News', params=params)

def is_in_run_window():
    '''
    Calculate the datetime run window for the download processor
    returns: (bool, datetime) if we are in the run window or not and when the start time is
    '''
    # determine if it is currently a weekend or weekday
    is_weekday = datetime.datetime.today().weekday() < 5
    now = datetime.datetime.now()

    if is_weekday:
        start_time = datetime.datetime.now().replace(hour=settings.WEEKDAY_START_TIME.hour,\
            minute=settings.WEEKDAY_START_TIME.minute, second=0, microsecond=0)
        end_time = datetime.datetime.now().replace(hour=settings.WEEKDAY_END_TIME.hour,\
            minute=settings.WEEKDAY_END_TIME.minute, second=0, microsecond=0)

        end_is_next_day = settings.WEEKDAY_END_TIME < settings.WEEKDAY_START_TIME
    else:
        start_time = datetime.datetime.now().replace(hour=settings.WEEKEND_START_TIME.hour,\
            minute=settings.WEEKEND_START_TIME.minute, second=0, microsecond=0)
        end_time = datetime.datetime.now().replace(hour=settings.WEEKEND_END_TIME.hour,\
            minute=settings.WEEKEND_END_TIME.minute, second=0, microsecond=0)

        end_is_next_day = settings.WEEKEND_END_TIME < settings.WEEKEND_START_TIME

    if end_is_next_day:
        end_time = end_time + datetime.timedelta(days=1)

    # Add in allowance for checking the previous day's run window since if the time just changed over
    # then it would still be within that window instead of the next day's
    not_todays = now < start_time or now > end_time
    not_yesterdays = now < (start_time - datetime.timedelta(days=1)) or now > (end_time - datetime.timedelta(days=1))
    not_all_day = start_time != end_time

    if not_todays and not_yesterdays and not_all_day:
        message = (
            f"Not during the valid processing window. "
            f"Start time: {(start_time-datetime.timedelta(days=1)).strftime('%A %I:%M%p')} "
            f"End time: {(end_time-datetime.timedelta(days=1)).strftime('%A %I:%M%p')} "
            f"or "
            f"Start time: {start_time.strftime('%A %I:%M%p')} "
            f"End time: {end_time.strftime('%A %I:%M%p')}")
        logging.debug(message)
        return (False, start_time)
    return (True, timezone.make_aware(start_time))

def update_limits(service, headers):
    '''
    Updates the limits in the database
    '''
    limit_type = CallTypeChoice.SRH
    if service == 'download':
        limit_type = CallTypeChoice.DWL
    if service == 'sources':
        limit_type = CallTypeChoice.SRC

    # Update the DB with the current rate limits remaining
    limits = api_limits.objects.get(limit_type=limit_type)
    if headers and 'X-RateLimit-Limit' in headers:
        vals = str(headers['X-RateLimit-Limit']).split('/')
        limits.limits_per_minute = int(vals[0])
        limits.limits_per_hour = int(vals[1])
        limits.limits_per_day = int(vals[2])
    if headers and 'X-RateLimit-Reset' in headers:
        vals = str(headers['X-RateLimit-Reset']).split('/')
        limits.reset_on_minute = timezone.make_aware(datetime.datetime.fromtimestamp(int(vals[0])))
        limits.reset_on_hour = timezone.make_aware(datetime.datetime.fromtimestamp(int(vals[1])))
        limits.reset_on_day = timezone.make_aware(datetime.datetime.fromtimestamp(int(vals[2])))
    if headers and 'X-RateLimit-Remaining' in headers:
        vals = str(headers['X-RateLimit-Remaining']).split('/')
        limits.remaining_per_minute = int(vals[0])
        limits.remaining_per_hour = int(vals[1])
        limits.remaining_per_day = int(vals[2])

    # Save to the database
    try:
        limits.save()
        logging.debug(f"Updated limits for {service}.")
    except OperationalError as exc:
        log_error(f"Unable to save the new limits to the database for {service}. Error: {exc}")
        return

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
