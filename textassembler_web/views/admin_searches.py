'''
Handles all requests to the admin page
'''
from django.shortcuts import render, redirect
from django.conf import settings
from textassembler_web.utilities import build_search_info, get_is_admin
from textassembler_web.models import searches

def admin_searches(request):
    '''
    Render the admin page
    '''
    # Verify that the user is logged in and an admin
    if not request.session.get('userid', False) or not get_is_admin(request.session['userid']):
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
