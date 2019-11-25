"""
Handles the login requests to the application
"""
import logging
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from textassembler_web.utilities import get_is_admin

def login(request):
    '''
    Handles login requests
    '''
    # Check if bypass mode is enabled
    if settings.AUTH_BYPASS:
        request.session['userid'] = settings.AUTH_BYPASS_USER
        request.session['is_admin'] = get_is_admin(request.session['userid'])
        logging.debug(f"Auth bypass mode is enabled. Logging in as {request.session['userid']}")
        return redirect('/search')

    # If they are already logged in, send users to search page
    if request.session.get('userid', False):
        request.session['is_admin'] = get_is_admin(request.session['userid'])
        logging.debug(f"User already logged in: {request.session['userid']}")
        return redirect('/search')

    # Check if the logon was successful already
    if request.META.get('REMOTE_USER', False):
        logging.debug("Found signed-in Cosign user")
        request.session['userid'] = request.META['REMOTE_USER']
        request.session['is_admin'] = get_is_admin(request.session['userid'])
        return redirect('/search')
    else:
        logging.debug("Authenticating the user")
        return redirect("/login")

    # Send users to the search page on sucessful login
    return redirect('/search')
