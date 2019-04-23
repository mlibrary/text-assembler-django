from django.core.management.base import BaseCommand, CommandError
from textassembler_web.search import Search
from django.apps import apps
from django.db import transaction
import time
import logging

class Command(BaseCommand):
    help = "Update the available search sources from LexisNexis"

    def handle(self, *args, **options):
        self.sources = apps.get_model('textassembler_web','sources')
        logging.info("Starting refresh of LexisNexis searchable sources.")

        # Get all the sources
        self.api = Search()
        skip = 0

        self.wait_for_search(self.api)
        sources = self.api.api_call(resource="Sources", params={"$top":100})

        # check for errors
        if "error_message" in sources:
            logging.error("Error occured refreshing the sources. Message: ".format(sources["error_message"]))
            return

        results = []
        logging.info("Found {0} sources.".format(sources['@odata.count']))
        if "value" in sources and len(sources["value"]) > 0:
            logging.info("Processing results {0} - {1}".format(0,100))
            for source in sources["value"]:
                results.append({'id':source["Id"],'name':source['Name']})
            while skip < int(sources["@odata.count"]):
                self.wait_for_search(self.api)
                sources = self.api.api_call(resource="Sources",params={"$top":100, "$skip":skip})
                if "error_message" in sources:
                    logging.error("Error occured refreshing the sources. Message: ".format(sources["error_message"]))
                    return
                if sources is not None and "value" in sources and len(sources["value"]) > 0:
                    logging.info("Processing results {0} - {1}".format(skip,skip+100))
                    for source in sources["value"]:
                        results.append({'id':source["Id"],'name':source['Name']})
                else:
                    break
                skip += 100


        # Start a transaction to remove the current sources then add the new ones
        logging.info("Updating the database with the {0} sources.".format(len(results)))
        with transaction.atomic():
            self.sources.objects.all().delete()

            for result in results:
                self.sources.objects.create(source_id=result['id'], source_name=result['name'][0:250])

        logging.info("Completed refresh of sources. {0} found.".format(len(results)))

    def wait_for_search(self, api):
        wait_time = api.get_time_until_next_search()
        if wait_time > 0:
            logging.info("No searches remaining. Must wait {0} seconds until next available searching is available.".format(wait_time))
            time.sleep(wait_time + 1)
            logging.info("Resuming processing after sleep for {0} seconds.".format(wait_time))

