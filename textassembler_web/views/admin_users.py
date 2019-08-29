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


def add_admin_user(request):
    '''
    Add the given users as an administrator
    '''
    # Verify that the user is logged in and an admin
    if not request.session.get('userid', False) or not get_is_admin(request.session['userid']):
        return redirect('/login')

    # Clear past error messages
    request.session["error_message"] = ""

    # Parse the userid to add
    if "userid" in request.POST:
        userid = request.POST["userid"]

    # Validate the userid meets minimum requirements
    if not userid:
        request.session["error_message"] = "the User ID must be at least 1 character long."

    # Make sure the user is not already marked as an administrator
    admin_record = administrative_users.objects.all().filter(userid=userid)
    if admin_record:
        request.session["error_message"] = "The User ID provided is already in the system as an administrator."

    # Add the user to the administrator table
    if request.session["error_message"] == "":
        administrative_users.objects.create(userid=userid)

    # Refresh the page
    return redirect(admin_users)

def delete_admin_user(request, userid):
    '''
    delete the given user from the administrators table
    '''
    # Verify that the user is logged in and an admin
    if not request.session.get('userid', False) or not get_is_admin(request.session['userid']):
        return redirect('/login')

    # Clear past error messages
    request.session["error_message"] = ""

    # Validate that the user is not the current user
    if userid == request.session['userid']:
        request.session["error_message"] = "Can not remove the currently logged in user as an administrator."

    # Check if the user is in the administrators table
    admin_record = administrative_users.objects.all().filter(userid=userid)
    if not admin_record:
        request.session["error_message"] = "The User ID provided was not found in the database! If this persists, please contact a system administrator."

    # If they are, delete the record
    if request.session["error_message"] == "":
        admin_record.delete()

    # Refresh the page
    return redirect(admin_users)
