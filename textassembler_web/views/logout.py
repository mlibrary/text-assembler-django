"""
Handles the logout requests for the application
"""
from django.shortcuts import redirect
from django.conf import settings


def logout(request):
    '''
    Handles logout requests
    '''
    # Clear the session
    request.session['userid'] = None
    request.session['access_token'] = None
    request.session['state'] = None

    # Redirect to OAuth logout page
    return redirect(settings.APP_LOGOUT_URL)
