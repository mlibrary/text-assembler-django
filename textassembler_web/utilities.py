"""
Utility functions for the Web interface
"""

import logging
import re
import traceback
import sys
import math
import smtplib
import socket
import datetime
from email.message import EmailMessage
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from .models import searches, filters, download_formats, available_formats, administrative_users, api_limits, CallTypeChoice

def log_error(error_message, json_data=None):
    '''
    Print the error and data to the log and send it to the system
    administrator as well.
    '''
    # Print both the error and and POST data to the error log
    logging.error(error_message)
    if json_data != None:
        logging.error(json_data)

    if not settings.MAINTAINER_EMAILS:
        return

    # Check for empty parameter in config
    if len(settings.MAINTAINER_EMAILS) == 1 and settings.MAINTAINER_EMAILS[0] == "":
        return

    # Validate the emails provided
    for email in settings.MAINTAINER_EMAILS:
        if not email:
            continue
        match = re.match(r'^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
        if match is None:
            logging.error(f"Could not send email, one or more of the emails provided for MAINTAINER_EMAILS was not valid. {email}")
            return

    # Email system administrators the error as well
    message = f"""
    <h1>Error:</h1>
    <p>{error_message}</p>

    <h1>POST Data:</h1>
    <p>{json_data}</p>
    """

    try:
        msg = EmailMessage()
        msg.set_content(message, subtype='html')
        msg['Subject'] = 'Text Assembler Error'
        msg['From'] = "root@" + socket.getfqdn()
        msg['To'] = settings.MAINTAINER_EMAILS

        slib = smtplib.SMTP('localhost')
        slib.send_message(msg)
        slib.quit()
    except smtplib.SMTPException as ex:
        logging.error(f"Error: unable to send email to maintainers. {ex}")

def send_user_notification(userid, search_query, date_queued, num_results, failed=False):
    '''
    Sends an email notification to the specified user indicating that their search
    has completed processing.
    '''
    # Check for empty parameter in config
    if not settings.NOTIF_EMAIL_DOMAIN or settings.NOTIF_EMAIL_DOMAIN == "":
        return

    if not userid or userid == "":
        return

    if settings.BCC_MAINTAINERS_ON_NOTIF:
        # Validate the emails provided
        for email in settings.MAINTAINER_EMAILS:
            if not email:
                continue
            match = re.match(r'^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
            if match is None:
                logging.error(f"Could not send email, one or more of the emails provided for MAINTAINER_EMAILS was not valid. {email}")
                return

    user_email = userid + "@" + settings.NOTIF_EMAIL_DOMAIN
    match = re.match(r'^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', user_email)
    if match is None:
        logging.error(f"Could not send email, one or more of the emails provided for userid {userid} was not valid. {user_email}")
        return


    # Email system administrators the error as well
    message = f"""
    <h1>Search Completed Processing</h1>
    <p>Search Term: {search_query}</p>
    <p>Status: {'Success' if not failed else 'Failed'}</p>
    <p>Number of Results: {num_results if not failed else 'N/A'}</p>
    <p>Date Submitted: {date_queued.strftime('%B %m, %Y')}</p>
    <p>Please visit {settings.PREFERRED_HOST_URL} to view your search.</p>
    """

    try:
        msg = EmailMessage()
        msg.set_content(message, subtype='html')
        msg['Subject'] = 'Text Assembler - Search Completed Processing'
        msg['From'] = "root@" + socket.getfqdn()
        msg['To'] = user_email
        msg['Bcc'] = settings.MAINTAINER_EMAILS

        slib = smtplib.SMTP('localhost')
        slib.send_message(msg)
        slib.quit()
    except smtplib.SMTPException as ex:
        logging.error(f"Error: unable to send notification email. {ex}")


def seconds_to_dhms_string(time):
    '''
    Convert seconds to a readable datetime string
    '''
    seconds_to_minute = 60
    seconds_to_hour = 60 * seconds_to_minute
    seconds_to_day = 24 * seconds_to_hour

    days = time // seconds_to_day
    time %= seconds_to_day

    hours = time // seconds_to_hour
    time %= seconds_to_hour

    minutes = time // seconds_to_minute
    time %= seconds_to_minute

    seconds = time

    if days == 0 and hours == 0 and minutes == 0:
        return f"{seconds} seconds"
    if days == 0 and hours == 0:
        return f"{minutes} minutes, {seconds} seconds"
    if days == 0:
        return f"{hours} hours, {minutes} minutes, {seconds} seconds"

    return f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"

def create_error_message(ex, source_file=""):
    '''
    Creates the stack-trace message for logging purposes. Takes the source file to print to
    the error message if provided.
    '''
    return f"{type(ex).__name__} on line {sys.exc_info()[-1].tb_lineno}{' in ' + source_file if source_file else ''}:  {ex}\n{traceback.format_exc()}"

def est_days_to_complete_search(num_results_in_search):
    '''
    Calculates the number of days it would take to complete a search given the number of results it has.
    It uses the max number of downloads allowed per day as the cap since we can download faster than the cap.
    It will compare against the number of items currently in the queue that are sharing those downloads.
    '''
    # validate trottle settings
    limits = None
    if not settings.DOWNLOADS_PER_MINUTE or not settings.DOWNLOADS_PER_HOUR or \
        not settings.DOWNLOADS_PER_DAY:
        try:
            limits = api_limits.objects.get(limit_type=CallTypeChoice.DWL)
        except ObjectDoesNotExist:
            log_error("API download limits are not properly configured. Run: manage.py update_limits")
    else:
        limits = api_limits(
            limit_type=CallTypeChoice.DWL,
            limit_per_minute=settings.DOWNLOADS_PER_MINUTE,
            limit_per_hour=settings.DOWNLOADS_PER_HOUR,
            limit_per_day=settings.DOWNLOADS_PER_DAY)

    queue_cnt = searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True).count()
    queue_cnt = 1 if queue_cnt == 0 else queue_cnt

    return math.ceil(int(num_results_in_search) / ((int(limits.limit_per_day) * int(settings.LN_DOWNLOAD_PER_CALL)) / int(queue_cnt)))

def build_search_info(search_obj):
    '''
    Add additional information to each search result object for the page to use when rendering
    '''
    # Build progress data
    search_obj.filters = filters.objects.filter(search_id=search_obj.search_id)
    formats = download_formats.objects.filter(search_id=search_obj.search_id)
    search_obj.download_formats = []

    for fmt in formats:
        search_obj.download_formats.append(available_formats.objects.get(format_id=fmt.format_id.format_id))

    # determine the status
    search_obj.status = "Queued"
    if search_obj.date_started != None:
        search_obj.status = "In Progress"
    if search_obj.date_started_compression != None:
        search_obj.status = "Preparing Results for Download"
    if search_obj.date_completed_compression != None:
        search_obj.status = "Completed"
    if search_obj.failed_date != None:
        search_obj.status = "Failed"

    # set date the search_obj is set to be deleted on
    if search_obj.status == "Completed":
        search_obj.delete_date = search_obj.date_completed_compression + datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)
    if search_obj.status == "Failed":
        search_obj.delete_date = search_obj.failed_date + datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)

    if (search_obj.status == "Queued" or search_obj.status == "In Progress") and search_obj.num_results_in_search and search_obj.num_results_in_search > 0:
        search_obj.est_days_to_complete = est_days_to_complete_search(search_obj.num_results_in_search - search_obj.num_results_downloaded)

    # calculate percent complete
    if search_obj.num_results_in_search is None or search_obj.num_results_in_search == 0:
        search_obj.percent_complete = 0
    else:
        search_obj.percent_complete = round((search_obj.num_results_downloaded / search_obj.num_results_in_search) * 100, 0)

    # Clear out the error message from the display if the status is not Failed
    if search_obj.status != "Failed":
        search_obj.error_message = ""

    return search_obj

def get_is_admin(userid):
    '''
    Determine if the user is a system admin or not
    '''
    return bool(administrative_users.objects.all().filter(userid=userid))
