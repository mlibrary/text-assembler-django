'''
Handles all web requests for the application
'''
from django.shortcuts import render, redirect



""" ------------------------------
    About Page
    ------------------------------
""" # pylint: disable=pointless-string-statement
def about(request):
    '''
    Render the About page
    '''

    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    return render(request, 'textassembler_web/about.html', {})
