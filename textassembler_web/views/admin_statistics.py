'''
Handles all web requests for the statistics page
'''
from django.shortcuts import render, redirect



def admin_statistics(request):
    '''
    Render the statistics page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    return render(request, 'textassembler_web/statistics.html', {})
