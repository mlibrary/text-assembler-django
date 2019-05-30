from django import template
from django.conf import settings
import datetime 

register = template.Library()

@register.simple_tag
def app_name():
    return settings.APP_NAME

@register.filter(expects_localtime=True)
def parse_iso(value):
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

@register.simple_tag
def seconds_to_dhms(time):
    seconds_to_minute   = 60
    seconds_to_hour     = 60 * seconds_to_minute
    seconds_to_day      = 24 * seconds_to_hour

    days    =   time // seconds_to_day
    time    %=  seconds_to_day

    hours   =   time // seconds_to_hour
    time    %=  seconds_to_hour

    minutes =   time // seconds_to_minute
    time    %=  seconds_to_minute

    seconds = time

    if days == 0 and hours == 0 and minutes == 0:
        return "%d seconds" % (seconds)
    if days == 0 and hours == 0:
        return "%d minutes, %d seconds" % (minutes, seconds)
    if days == 0:
        return "%d hours, %d minutes, %d seconds" % (hours, minutes, seconds)

    return "%d days, %d hours, %d minutes, %d seconds" % (days, hours, minutes, seconds)
