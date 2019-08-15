'''
Handles all requests to the admin page
'''
from django.shortcuts import render, redirect
from django.conf import settings
from textassembler_web.utilities import build_search_info
from textassembler_web.models import searches, admin_users

def admin_searches(request):
    '''
    Render the admin page
    '''
    # Verify that the user is logged in
    if not request.session.get('userid', False):
        return redirect('/login')

    # Verify that the user is an admin
    admin_user = admin_users.objects.all().filter(userid=request.session['userid'])
    if not admin_user:
        return redirect('/login')

    response = {}
    response["headings"] = ["Date Submitted", "Query", "Progress"]

    if "error_message" in request.session:
        response["error_message"] = request.session["error_message"]
        request.session["error_message"] = "" # clear it out so it won't show on refresh

    all_user_searches = searches.objects.all().filter(deleted=False).order_by('-date_submitted')

    for search_obj in all_user_searches:
        search_obj = build_search_info(search_obj)

    response["searches"] = all_user_searches
    response["num_months_keep_searches"] = settings.NUM_MONTHS_KEEP_SEARCHES

    return render(request, 'textassembler_web/allsearches.html', response)
