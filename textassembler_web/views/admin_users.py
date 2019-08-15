'''
Handles all web requests for the users page
'''
from django.shortcuts import render, redirect



def admin_users(request):
    '''
    Render the users page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    return render(request, 'textassembler_web/users.html', {})
