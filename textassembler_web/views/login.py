"""
Handles the login requests to the application
"""
import logging
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from textassembler_web.oauth_client import OAuthClient

def login(request):
    '''
    Handles login requests
    '''
    # Check if bypass mode is enabled
    if settings.OAUTH_BYPASS:
        request.session['userid'] = settings.OAUTH_BYPASS_USER
        logging.debug(f"OAuth bypass mode is enabled. Logging in as {request.session['userid']}")
        return redirect('/search')

    # If they are already logged in, send users to search page
    if request.session.get('userid', False):
        logging.debug(f"User already logged in: {request.session['userid']}")
        return redirect('/search')

    # Initialize the OAuth client
    app_auth = OAuthClient(settings.APP_CLIENT_ID, settings.APP_CLIENT_SECRET, \
        settings.APP_REDIRECT_URL, settings.APP_AUTH_URL, \
        settings.APP_TOKEN_URL, settings.APP_PROFILE_URL)

    # Check if the logon was successful already
    if 'code' in request.GET and request.session.get('state', False):
        logging.debug("Getting OAuth access token from the code")
        app_auth.set_state(request.session['state'])
        request.session['access_token'] = app_auth.get_access_token(request.GET['code'])

    # Call the OAuth provider to authenticate
    if not request.session.get('access_token', False):
        logging.debug("Authenticating the user")
        app_auth.init_auth_url()
        request.session['state'] = app_auth.get_state() # save the state in the session to use later
        return redirect(app_auth.get_auth_url())

    # Retrieve user information after a successful logon
    if request.session.get('access_token', False) and not request.session.get('userid', False):
        logging.debug("Getting the authenticated user's userid")
        app_auth.set_access_token(request.session['access_token'])
        results = app_auth.fetch()
        request.session['userid'] = results['info'][settings.APP_USER_ID_FIELD]

    # Check if the userid is still not set
    if not request.session.get('userid', False):
        logging.warning("UserID was still not set after authentication against OAuth")
        return HttpResponse('Unable to log in. You must be an active MSU user to use this resource.')

    # Send users to the search page on sucessful login
    return redirect('/search')
