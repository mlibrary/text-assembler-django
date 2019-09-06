'''
Update the searchable sources available in the interface
'''
import time
import logging
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from textassembler_web.ln_api import LNAPI

class Command(BaseCommand):
    '''
    Update the search sources
    '''
    help = "Update the available search sources from LexisNexis"

    def __init__(self):
        self.sources = None
        self.api = None
        super().__init__()

    def add_arguments(self, parser):
        # Optional argument for skip value to pick up where you left off in event of failure
        parser.add_argument('-s', '--skip', type=int, help='Skip value to start with (Default = 0)')


    def handle(self, *args, **options):
        self.sources = apps.get_model('textassembler_web', 'sources')

        # Process command line argument
        skip = int(options['skip']) if options['skip'] else 0

        total = 0

        logging.info(f"Starting refresh of LexisNexis searchable sources. Skip value = {skip}")

        # Get all the sources
        self.api = LNAPI()

        self.wait_for_sources(self.api)
        sources = self.api.api_call(resource="Sources", params={"$top":100, "$skip":skip})

        # check for errors
        if "error_message" in sources:
            logging.error(f"Error occurred refreshing the sources. Message: {sources['error_message']}")
            return

        total = int(sources['@odata.count'])
        logging.info(f"Found {total} sources.")
        if "value" in sources and sources["value"]:
            logging.info(f"Processing results {skip} - {skip+100}, out of {total} results.")
            for source in sources["value"]:
                # make sure it's not already in there
                if self.sources.objects.all().filter(source_id=source["Id"], source_name=source['Name'][0:250], active=False).count() == 0:
                    # add it as inactive
                    self.sources.objects.create(source_id=source["Id"], source_name=source['Name'][0:250])
            while skip < total:
                skip += 100
                time.sleep(1) # take a brief break to free up CPU usage
                self.wait_for_sources(self.api)
                sources = self.api.api_call(resource="Sources", params={"$top":100, "$skip":skip})
                if "error_message" in sources:
                    if "response_code" in sources and sources["response_code"] == 429:
                        logging.error("Went over throttling limit! will recalculate next available window.")
                        continue
                    else:
                        logging.error(f"Error occurred refreshing the sources. Message: {sources['error_message']}")
                        return
                if sources is not None and "value" in sources and sources["value"]:
                    total = int(sources['@odata.count'])
                    logging.info(f"Processing results {skip} - {skip+100}, out of {total} results.")
                    for source in sources["value"]:
                        # make sure it's not already in there
                        if self.sources.objects.all().filter(source_id=source["Id"], source_name=source['Name'][0:250], active=False).count() == 0:
                            # add it as inactive
                            self.sources.objects.create(source_id=source["Id"], source_name=source['Name'][0:250])
                else:
                    break

        # Start a transaction to remove the current sources then add the new ones
        logging.info(f"Updating the database to activate the {total} new sources.")
        with transaction.atomic():
            #  delete all currently active records
            self.sources.objects.all().filter(active=True).delete()

            #  mark all remaining records as active
            self.sources.objects.all().update(active=True)

        logging.info(f"Completed refresh of sources. {total} found.")

    def wait_for_sources(self, api):
        '''
        Wait for the next available search window
        '''
        wait_time = api.get_time_until_next_sources()
        if wait_time > 0:
            logging.info(f"No sources calls remaining. Must wait {wait_time} seconds until next available call is available.")
            # Check if we can download every 10 seconds instead of waiting the full wait_time to
            # be able to handle sig_term triggering (i.e. we don't want to sleep for an hour before
            # a kill command is processed)
            while not self.api.check_can_sources():
                time.sleep(10)
            logging.info("Resuming processing")
