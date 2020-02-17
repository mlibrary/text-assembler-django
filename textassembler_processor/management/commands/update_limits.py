'''
Update the API throttle limits
'''
import logging
from django.core.management.base import BaseCommand
from django.apps import apps
from textassembler_web.ln_api import LNAPI

class Command(BaseCommand):
    '''
    Update the throttle limits
    '''
    help = "Update the available search limitations from LexisNexis"

    def __init__(self):
        self.api = None
        self.limits = None
        super().__init__()

    def handle(self, *args, **options):
        logging.info(f"Starting refresh of LexisNexis throttle limits.")
        self.limits = apps.get_model('textassembler_web', 'api_limits')
        self.api = LNAPI()

        self.api.api_update_rate_limit('sources')
        self.api.api_update_rate_limit('download')
        self.api.api_update_rate_limit('search')

        logging.info(f"Completed refresh of LexisNexis throttle limits.")
