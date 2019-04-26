from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag
def app_name():
    return settings.APP_NAME
