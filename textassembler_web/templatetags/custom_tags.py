"""
Retrieves information to use in templates
"""
import datetime
from django import template
from django.conf import settings
from ..utilities import seconds_to_dhms_string # pylint: disable=relative-beyond-top-level

register = template.Library()

@register.simple_tag
def app_name():
    '''
    Get the application name from the config file
    '''
    return settings.APP_NAME

@register.simple_tag
def max_results_allowed():
    '''
    Get the max allowed results for non-admins from the config file
    '''
    return format(settings.MAX_RESULTS_ALLOWED, ',d')

@register.simple_tag
def is_over_max(value):
    '''
    Returns true or false if the value is over the max
    '''
    return int(value) >= settings.MAX_RESULTS_ALLOWED

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
