"""
Utility functions for the Web interface
"""

import logging
from django.conf import settings
import smtplib
import socket
from email.message import EmailMessage
import re

def log_error(error_message, json_data = None):
    # Print both the error and and POST data to the error log
    logging.error(error_message)
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
