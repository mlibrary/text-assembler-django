"""
Retrieves information to use in templates
"""
import datetime
from django import template
from ..utilities import seconds_to_dhms_string
from django.conf import settings

register = template.Library()

@register.simple_tag
def app_name():
    '''
    Get the application name from the config file
    '''
    return settings.APP_NAME

@register.filter(expects_localtime=True)
def parse_iso(value):
    '''
    Convert the ISO timestamp to a readable datetime
    '''
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

@register.simple_tag
def seconds_to_dhms(time):
    '''
    Convert seconds to a readable datetime string
    '''
    return seconds_to_dhms_string(time)
