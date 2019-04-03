"""
Search the LexisNexis API
"""
import logging
import requests
import json
from django.conf import settings
import datetime

class Search:
    def __init__(self):
        self.access_token = None
        self.expiration_time = None

        self.api_url = settings.LN_API_URL
        if not self.api_url.endswith("/"):
            self.api_url += "/"

        self.authenticate()

    def authenticate(self):
        # Do not get a new token since the current one is still valid
        if self.access_token is not None and self.expiration_time is not None and datetime.datetime.now() <= self.expiration_time:
            return 

        data = {'grant_type': 'client_credentials',
            'scope': settings.LN_SCOPE}

        access_token_response = requests.post(settings.LN_TOKEN_URL, 
            data=data, verify=True, 
            auth=(settings.LN_CLIENT_ID, settings.LN_CLIENT_SECRET))

        if access_token_response.status_code == requests.codes.ok:
            tokens = access_token_response.json()
            self.access_token = tokens['access_token']
            self.expiration_time = datetime.datetime.now() + datetime.timedelta(seconds=int(tokens['expires_in']))

        else:
            pass # TODO handle bad request/response

    def api_call(self, req_type='GET', resource='News', params = {}):
        self.authenticate()
        headers = {"Authorization": "Bearer " + self.access_token}
        url = self.api_url + resource
    
        if req_type == "GET":
            resp = requests.get(url, params=params, headers=headers)
        if req_type == "POST":
            resp = requests.post(url, params=params, headers=headers)

        if resp.status_code == requests.codes.ok:
            return resp.json()

        else:
            pass
            # TODO -- handle failure


    def search(self, term = ""):
        params = {"$search":term}
        return self.api_call(resource='News', params=params)

