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

