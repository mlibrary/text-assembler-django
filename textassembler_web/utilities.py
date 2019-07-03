"""
Utility functions for the Web interface
"""

import logging
import datetime
from django.conf import settings
from django.apps import apps 
from .models import searches
import smtplib
import socket
from email.message import EmailMessage
import re
import traceback
import sys
import os
import math

def log_error(error_message, json_data = None):
    # Print both the error and and POST data to the error log
    logging.error(error_message)
    if json_data != None:
        logging.error(json_data)

    if len(settings.MAINTAINER_EMAILS) == 0:
        return

    # Check for empty parameter in config
    if len(settings.MAINTAINER_EMAILS) == 1 and settings.MAINTAINER_EMAILS[0] == "":
        return

    # Validate the emails provided
    for email in settings.MAINTAINER_EMAILS:
        if len(email) == 0:
            continue
        match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
        if match == None:
            logging.error("Could not send email, one or more of the emails provided for MAINTAINER_EMAILS was not valid. " + email)
            return

    # Email system administrators the error as well
    sender = "root@" + socket.getfqdn()
    receivers = settings.MAINTAINER_EMAILS

    message = """
    <h1>Error:</h1>
    <p>{}</p>

    <h1>POST Data:</h1>
    <p>{}</p>
    """.format(error_message, json_data)

    try:
        msg = EmailMessage()
        msg.set_content(message, subtype='html')
        msg['Subject'] = 'Text Assembler Error'
        msg['From'] = "root@" + socket.getfqdn()
        msg['To'] = settings.MAINTAINER_EMAILS

        s = smtplib.SMTP('localhost')
        s.send_message(msg)
        s.quit()
    except Exception as e:
       logging.error("Error: unable to send email to maintainers. " + e)

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
        return "%d seconds" % (seconds)
    if days == 0 and hours == 0:
        return "%d minutes, %d seconds" % (minutes, seconds)
    if days == 0:
        return "%d hours, %d minutes, %d seconds" % (hours, minutes, seconds)

    return "%d days, %d hours, %d minutes, %d seconds" % (days, hours, minutes, seconds)

def create_error_message(e, source_file = ""):
    '''
    Creates the stack-trace message for logging purposes. Takes the source file to print to
    the error message if provided.
    '''
    return "{0} on line {1}{2}:  {3}\n{4}".format(type(e).__name__, \
        sys.exc_info()[-1].tb_lineno, (" in " + source_file if source_file else ""), \
        e, traceback.format_exc())

def estimate_days_to_complete_search(num_results_in_search):
    '''
    Calculates the number of days it would take to complete a search given the number of results it has.
    It uses the max number of downloads allowed per day as the cap since we can download faster than the cap.
    It will compare against the number of items currently in the queue that are sharing those downloads.
    '''
    limits = apps.get_model('textassembler_processor', 'limits')

    throttles = limits.objects.all()
    if throttles.count() == 0:
        log_error("No record exists in the database containing the throttling limitations!")
    if throttles.count() > 1:
        log_error("More than one record exists in the database for the throttling limitations!")

    throttles = throttles[0]
    queue_cnt = searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True).count()
    queue_cnt = 1 if queue_cnt == 0 else queue_cnt

    return math.ceil(int(num_results_in_search) / (int(throttles.downloads_per_day) / int(queue_cnt)))
