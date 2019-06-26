"""
Class to handle OAuth client authentication
"""
from requests_oauthlib import OAuth2Session

class OAUTH_CLIENT:
    '''
    OAuth client using the requests_oauthlib library
    https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html
    '''

    def __init__(self, client_id, client_secret, redirect_url, auth_url, token_url, profile_url):
        '''
        Initialize the object with OAuth variables
        '''
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_url = redirect_url
        self.auth_url = auth_url
        self.token_url = token_url
        self.profile_url = profile_url

        self.state = None
        self.authorization_url = None
        self.access_token = None

    def init_auth_url(self):
        '''
        Redirect users to the app's OAuth provider
        '''
        app_auth = OAuth2Session(self.client_id)
        authorization_url, state = app_auth.authorization_url(self.auth_url)

        self.state = state # State is used to prevent CSRF
        self.authorization_url = authorization_url

    def get_auth_url(self):
        '''
        Get the OAuth authorization URL
        '''
        return self.authorization_url

    def set_state(self, state):
        '''
        Set the OAuth state
        '''
        self.state = state

    def get_state(self):
        '''
        Get the OAuth state
        '''
        return self.state

    def set_access_token(self, token):
        '''
        Set the access token
        '''
        self.access_token = token

    def get_access_token(self, code):
        '''
        Get the access token, retrieving it from the OAuth provider if necessary
        '''
        if self.access_token is None and code is not None:
            app_auth = OAuth2Session(client_id=self.client_id, state=self.state, redirect_uri=self.redirect_url)

            self.access_token = app_auth.fetch_token(self.token_url, client_secret=self.client_secret, \
                authorization_response=self.redirect_url + "?code=" + code + \
                "&state=" + self.state + "&redirect_uri=" + self.redirect_url, \
                include_client_id=True)

        return self.access_token

    def fetch(self):
        '''
        Fetch the user profile data from the OAuth provider
        '''
        app_auth = OAuth2Session(self.client_id, token=dict(self.access_token))
        results = app_auth.get(self.profile_url + \
            "?access_token=" + self.access_token['access_token'])

        return results.json()
