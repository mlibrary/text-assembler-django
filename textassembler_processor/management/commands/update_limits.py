'''
Update the API throttle limits
'''
import logging
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import OperationalError
from django.core.exceptions import ObjectDoesNotExist
from textassembler_web.ln_api import LNAPI
from textassembler_web.utilities import log_error
from textassembler_web.models import CallTypeChoice

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

        # Make an API call to 'sources' to get the limits and update it in the DB
        self.update_limits(CallTypeChoice.SRC)

        # Make an API call to 'download' to get the limits and update it in the DB
        self.update_limits(CallTypeChoice.DWL)

        # Make an API call to 'search' to get the limits and update it in the DB
        self.update_limits(CallTypeChoice.SRH)

        logging.info(f"Completed refresh of LexisNexis throttle limits.")

    def update_limits(self, limit_type=CallTypeChoice.SRH):
        '''
        Call the API to get the current limits and save them to the database
        '''
        results = self.api.api_get_rate_limit(limit_type.value)
        if 'error_message' in results:
            log_error(f"Failed to get the limits for '{limit_type}'. {results['error_message']}")
        limits = str(results['X-RateLimit-Limit']).split('/')
        if len(limits) != 3:
            log_error(f"Limits returned for '{limit_type}' do not match expected format. {results['X-RateLimit-Limit']}")
        else:
            self.update_db_limits(limit_type, limits[0], limits[1], limits[2])

    def update_db_limits(self, limit_type=CallTypeChoice.SRH, per_minute=0, per_hour=0, per_day=0):
        '''
        Update the record in the database
        '''
        # Get the current record for that limit
        try:
            record = self.limits.objects.get(limit_type=limit_type)
        except ObjectDoesNotExist:
            record = self.limits(limit_type=limit_type)

        # Update the values and save
        record.per_minute = per_minute
        record.per_hour = per_hour
        record.per_day = per_day

        try:
            record.save()
            logging.info(f"Updated limits for {limit_type} to: {per_minute}/minute, {per_hour}/hour, {per_day}/day")
        except OperationalError as exc:
            log_error(f"Unable to save the new limits to the database for {limit_type}. Error: {exc}")
            return
