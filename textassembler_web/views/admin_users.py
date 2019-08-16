'''
Handles all web requests for the users page
'''
from django.shortcuts import render, redirect
from textassembler_web.models import administrative_users
from textassembler_web.utilities import get_is_admin



def admin_users(request):
    '''
    Render the users page
    '''

    # Verify that the user is logged in and an admin
    if not request.session.get('userid', False) or not get_is_admin(request.session['userid']):
        return redirect('/login')

    response = {}
    response["headings"] = ["User", "Action"]

    if "error_message" in request.session:
        response["error_message"] = request.session["error_message"]
        request.session["error_message"] = "" # clear it out so it won't show on refresh

    response["users"] = administrative_users.objects.all().order_by('userid')


    return render(request, 'textassembler_web/users.html', response)
