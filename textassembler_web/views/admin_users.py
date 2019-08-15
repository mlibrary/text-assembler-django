'''
Handles all web requests for the users page
'''
from django.shortcuts import render, redirect
from textassembler_web.models import administrative_users



def admin_users(request):
    '''
    Render the users page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    # Verify that the user is an admin
    admin_user = administrative_users.objects.all().filter(userid=request.session['userid'])
    if not admin_user:
        return redirect('/login')

    return render(request, 'textassembler_web/users.html', {})
