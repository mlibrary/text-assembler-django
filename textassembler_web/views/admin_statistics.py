'''
Handles all web requests for the statistics page
'''
from django.shortcuts import render, redirect
from textassembler_web.utilities import get_is_admin



def admin_statistics(request):
    '''
    Render the statistics page
    '''
    # Verify that the user is logged in and an admin
    if not request.session.get('userid', False) or not get_is_admin(request.session['userid']):
        return redirect('/login')


    return render(request, 'textassembler_web/statistics.html', {})
