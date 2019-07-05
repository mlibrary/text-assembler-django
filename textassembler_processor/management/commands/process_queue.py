"""
Processes the search queue to download results from LexisNexis
"""
import time
import logging
import signal
import os
import sys
import json
from django.core.management.base import BaseCommand
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from textassembler_web.ln_api import LN_API
from textassembler_web.utilities import log_error, create_error_message, send_user_notification
from bs4 import BeautifulSoup

class Command(BaseCommand):
    '''
    Process the search queue downloading results from LexisNexis
    '''
    help = "Process the search queue downloading results from LexisNexis"

    def handle(self, *args, **options):
        '''
        Handles the command to process the queue
        '''
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.error = False
        self.cur_search = None
        self.retry = False

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')
        self.filters = apps.get_model('textassembler_web', 'filters')
        self.download_formats = apps.get_model('textassembler_web', 'download_formats')
        self.available_formats = apps.get_model('textassembler_web', 'available_formats')

        logging.info("Starting queue processing.")
        self.api = LN_API()
        while not self.terminate:
            time.sleep(1) # take a quick break to free up CPU usage
            try:
                try:
                    # check that there are items in the queue to process
                    queue = self.searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True).order_by('-update_date')
                    if not queue:
                        self.retry = False
                        continue # nothing to process
                except Exception as ex:
                    log_error("Queue Processor failed to retrieve the search queue. {0}".format(ex))
                    if not self.retry:
                        time.sleep(10) # wait 10 seconds and re-try
                        self.retry = True
                        continue
                    else:
                        self.terminate = True

                # verify the storage location is accessibly
                if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                    log_error("Queue Processor failed due to storage location being inaccessible or not writable. {0}".format(settings.STORAGE_LOCATION))
                    # wait 30 seconds, if the storage is still not available, then terminate
                    time.sleep(30)
                    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                        log_error("Stopping. Queue Processor failed due to storage location being " +\
                            "inaccessible or not writable. {0}".format(settings.STORAGE_LOCATION))
                        self.terminate = True
                        self.error = True
                        continue

                # Update / validate authentication with the API
                response = self.api.authenticate()
                if response != "":
                    log_error("Queue Processor failed to authenticate against LexisNexis API. Response: {0}".format(response))
                    # wait 5 minutes, if the storage is still not able to authenticate, then terminate
                    time.sleep(60*5)
                    response = self.api.authenticate()
                    if response != "":
                        log_error("Stopping. Queue Processor failed to authenticate against LexisNexis API. Response: {0}".format(response))
                        self.terminate = True
                        self.error = True
                        continue
                    continue

                # wait until we can download
                self.wait_for_download()

                # continue loop if there are no downloads remaining
                #   (this could happen if some other search sneaks in before this
                #   process wakes)
                if not self.api.check_can_download():
                    continue

                # get the next item from the queue
                ## we are doing this again in case the search has been deleted
                ## while waiting for the API to be available
                try:
                    queue = self.searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True).order_by('-update_date')
                    if queue:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except OperationalError as ex:
                    log_error("Queue Processor failed to retrieve the search queue. {0}".format(ex))
                    if not self.retry:
                        time.sleep(10) # wait 10 seconds and re-try
                        self.retry = True
                        continue
                    else:
                        self.terminate = True

                logging.info("Downloading items for search: {0}. Skip Value: {1}.".format(self.cur_search.search_id, self.cur_search.skip_value))

                # check if this is a new search and set the start time
                if self.cur_search.date_started is None:
                    self.cur_search.date_started = timezone.now()
                    self.cur_search.save()

                # download next 10 items for the current search
                start_time = time.time()
                ## retrieve relavent search fields
                all_filters = self.filters.objects.filter(search_id=self.cur_search)
                self.set_formats = self.download_formats.objects.filter(search_id=self.cur_search)
                self.set_filters = {}
                for f in all_filters:
                    if f.filter_name not in self.set_filters:
                        self.set_filters[f.filter_name] = []
                    self.set_filters[f.filter_name].append(f.filter_value)

                ## call the download function with the parameters
                results = self.api.download(self.cur_search.query, \
                    self.set_filters, settings.LN_DOWNLOAD_PER_CALL, \
                    self.cur_search.skip_value)

                if "error_message" in results:
                    log_error("An error occured processing search id: {0}. {1}".format(self.cur_search.search_id, results["error_message"]), self.cur_search)
                    self.cur_search.retry_count = self.cur_search.retry_count + 1
                    self.cur_search.error_message = results["error_message"]
                    if self.cur_search.retry_count > settings.LN_MAX_RETRY:
                        self.cur_search.failed_date = timezone.now()
                        if not self.cur_search.user_notified and settings.NOTIF_EMAIL_DOMAIN:
                            #  send email notification
                            send_user_notification(self.cur_search.userid, self.cur_search.query, self.cur_search.date_submitted, 0, True)  
                            self.cur_search.user_notified = True
                    self.cur_search.save()
                    continue

                ## save the results to the server
                save_location = os.path.join(settings.STORAGE_LOCATION, str(self.cur_search.search_id))
                for result in results["value"]:
                    if self.terminate:
                        break
                    if "Document" not in result or "Content" not in result["Document"] or "ResultId" not in result:
                        log_error("WARNING: Could not parse result value from search for ID: {0}.".format(self.cur_search.search_id), json.dumps(result))
                        continue
                    full_text = result["Document"]["Content"]
                    file_name = result["ResultId"]
                    try:
                        for f in self.set_formats:
                            save_path = os.path.join(save_location, f.format_id.format_name)
                            if not os.path.exists(save_location):
                                os.mkdir(save_location)
                            if not os.path.exists(save_path):
                                os.mkdir(save_path)
                            if f.format_id.format_name == "HTML":
                                with open(os.path.join(save_path, file_name + ".html"), 'w') as fl:
                                    fl.write(full_text)
                            elif f.format_id.format_name == "TXT":
                                with open(os.path.join(save_path, file_name + ".txt"), 'w') as fl:
                                    fl.write(full_text)
                            elif f.format_id.format_name == "TXT Only":
                                try:
                                    cleaned_full_text = self.remove_html(full_text)
                                except Exception as ex:
                                    log_error("Unable to create TXT Only output for search {0}, filename {1}. Error. {2}".format(self.cur_search.search_id, file_name, create_error_message(ex, os.path.basename(__file__))))
                                    cleaned_full_text = full_text ## write the original text to the file instead
                                with open(os.path.join(save_path, file_name + "_ONLY_TXT.txt"), 'w') as fl:
                                    fl.write(cleaned_full_text)
                    except Exception as ex:
                        log_error("Failed to save downloaded results to the server. {0}".format(create_error_message(ex, os.path.basename(__file__))))
                        self.terminate = True
                        self.error = True
                        continue # not adding to retry count since it wasn't a problem with the search

                if not self.error:
                    # not including self.terminate since we would want to cleanly save
                    # the record before terminating the service. We only want to skip this
                    # step if the termination was due to a failure

                    ## update the search in the database
                    logging.info("Finished saving next {0} results for search: {1}".format(settings.LN_DOWNLOAD_PER_CALL, self.cur_search.search_id))
                    self.cur_search.skip_value = self.cur_search.skip_value + settings.LN_DOWNLOAD_PER_CALL
                    self.cur_search.update_date = timezone.now()
                    self.cur_search.run_time_seconds = self.cur_search.run_time_seconds + int(round(time.time() - start_time, 0))
                    self.cur_search.num_results_in_search = results['@odata.count']
                    self.cur_search.num_results_downloaded = self.cur_search.num_results_downloaded + len(results["value"])
                    ## check if the search is complete
                    if self.cur_search.num_results_downloaded >= self.cur_search.num_results_in_search:
                        logging.info("Completed downloading all results for search: {0}".format(self.cur_search.search_id))
                        self.cur_search.date_completed = timezone.now()

                    ## save the search record
                    self.cur_search.save()


            except Exception as e:
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error("An unexpected error occured while processing the queue. {0}".format(create_error_message(e, os.path.basename(__file__))))
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped queue processing.")

    def sig_term(self, sig, frame):
        '''
        Handles command termination
        '''
        self.terminate = True

    def remove_html(self, text):
        output = []

        bs = BeautifulSoup(text, "html.parser")

        headline = bs.h1.string if bs.h1 is not None and bs.h1.string is not None else ""
        # check another place for headline
        if not headline:
            headline = bs.find('nitf:hedline').text if bs.find('nitf:hedline') is not None else ""

        title = bs.title.string if bs.title is not None and bs.title.string is not None else ""

        # write the title and headline
        output.append(title)
        if title != headline: # prevent duplicate output to file
            output.append(headline)
    
        text = bs.find('bodytext').text if bs.find('bodytext') is not None else ""
        output.append(text)
        full_output = "\n\n".join(output)

        return full_output

    def wait_for_download(self):
        '''
        Will wait for an open download window before returning, checking periodically
        '''

        wait_time = round(self.api.get_time_until_next_download(), 0)
        if wait_time > 0:
            logging.info("No downloads remaining. Must wait {0} seconds until next available download window is available.".format(wait_time))
            # Check if we can download every 10 seconds instead of waiting the full wait_time to
            # be able to handle sig_term triggering (i.e. we don't want to sleep for an hour before
            # a kill command is processed)
            while not self.api.check_can_download():
                time.sleep(10)
            logging.info("Resuming processing")
