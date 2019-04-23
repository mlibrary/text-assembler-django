"""
WSGI config for textassembler project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'textassembler.settings')

import sys
path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if path not in sys.path:
    sys.path.append(path)


application = get_wsgi_application()
