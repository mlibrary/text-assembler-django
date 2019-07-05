from django.core.management.base import BaseCommand, CommandError
from textassembler_web.ln_api import LN_API
from django.apps import apps
from django.db import transaction
import time
import logging

class Command(BaseCommand):
    help = "Update the available search sources from LexisNexis"

    def add_arguments(self, parser):
        # Optional argument for skip value to pick up where you left off in event of failure
        parser.add_argument('-s', '--skip', type=int, help='Skip value to start with (Default = 0)')


    def handle(self, *args, **options):
        self.sources = apps.get_model('textassembler_web','sources')

        # Process command line argument
        skip = int(options['skip']) if options['skip'] else 0
       
        total = 0 

        logging.info("Starting refresh of LexisNexis searchable sources. Skip value = {0}".format(skip))

        # Get all the sources
        self.api = LN_API()

        self.wait_for_search(self.api)
        sources = self.api.api_call(resource="Sources", params={"$top":100, "$skip":skip})

        # check for errors
        if "error_message" in sources:
            logging.error("Error occured refreshing the sources. Message: ".format(sources["error_message"]))
            return

        total = int(sources['@odata.count'])
        logging.info("Found {0} sources.".format(total))
        if "value" in sources and len(sources["value"]) > 0:
            logging.info("Processing results {0} - {1}, out of {2} results.".format(skip, skip+100, total))
            for source in sources["value"]:
                # make sure it's not already in there
                if self.sources.objects.all().filter(source_id=source["Id"], source_name=source['Name'][0:250], active=False).count() == 0:
                    # add it as inactive
                    self.sources.objects.create(source_id=source["Id"], source_name=source['Name'][0:250])
            while skip < total:
                skip += 100
                time.sleep(1) # take a brief break to free up CPU usage
                self.wait_for_search(self.api)
                sources = self.api.api_call(resource="Sources",params={"$top":100, "$skip":skip})
                if "error_message" in sources:
                    if "response_code" in sources and sources["response_code"] == 429:
                        logging.error("Went over throttling limit! will recalculate next available window.", sources)
                        continue
                    else:
                        logging.error("Error occured refreshing the sources. Message: ".format(sources["error_message"]))
                        return
                if sources is not None and "value" in sources and len(sources["value"]) > 0:
                    total = int(sources['@odata.count'])
                    logging.info("Processing results {0} - {1}, out of {2} results.".format(skip, skip+100, total))
                    for source in sources["value"]:
                        # make sure it's not already in there
                        if self.sources.objects.all().filter(source_id=source["Id"], source_name=source['Name'][0:250], active=False).count() == 0:
                            # add it as inactive
                            self.sources.objects.create(source_id=source["Id"], source_name=source['Name'][0:250])
                else:
                    break

        # Start a transaction to remove the current sources then add the new ones
        logging.info("Updating the database to activate the {0} new sources.".format(total))
        with transaction.atomic():
            #  delete all currently active records
            self.sources.objects.all().filter(active=True).delete()

            #  mark all remaining records as active
            records = self.sources.objects.all().update(active=True)

        logging.info("Completed refresh of sources. {0} found.".format(total))

    def wait_for_search(self, api):
        wait_time = api.get_time_until_next_search()
        if wait_time > 0:
            logging.info("No searches remaining. Must wait {0} seconds until next available searching is available.".format(wait_time))
            # Check if we can download every 10 seconds instead of waiting the full wait_time to
            # be able to handle sig_term triggering (i.e. we don't want to sleep for an hour before
            # a kill command is processed)
            while not self.api.check_can_search():
                time.sleep(10)
            logging.info("Resuming processing")

