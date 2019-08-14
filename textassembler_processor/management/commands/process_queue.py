"""
Processes the search queue to download results from LexisNexis
"""
import time
import logging
import signal
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup # pylint: disable=import-error
from django.core.management.base import BaseCommand
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from django.db import OperationalError
from textassembler_web.ln_api import LNAPI
from textassembler_web.utilities import log_error, create_error_message, send_user_notification

class Command(BaseCommand): # pylint: disable=too-many-instance-attributes
    '''
    Process the search queue downloading results from LexisNexis
    '''
    help = "Process the search queue downloading results from LexisNexis"

    def __init__(self):
        self.terminate = False
        self.error = False
        self.cur_search = None
        self.retry = False
        self.api = None
        self.set_formats = None
        self.set_filters = None

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')
        self.filters = apps.get_model('textassembler_web', 'filters')
        self.download_formats = apps.get_model('textassembler_web', 'download_formats')
        self.available_formats = apps.get_model('textassembler_web', 'available_formats')

        super().__init__()

    def handle(self, *args, **options): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        '''
        Handles the command to process the queue
        '''
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)


        logging.info("Starting queue processing.")
        self.api = LNAPI()
        while not self.terminate:
            time.sleep(1) # take a quick break to free up CPU usage
            try:
                try:
                    # check that there are items in the queue to process
                    queue = self.searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True, deleted=False).order_by('-update_date')
                    if not queue:
                        self.retry = False
                        continue # nothing to process
                except OperationalError as ex:
                    if not self.retry:
                        time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                        self.retry = True
                        continue
                    else:
                        log_error(f"Stopping. Queue Processor failed to retrieve the search queue. {ex}")
                        self.terminate = True
                        continue

                # verify the storage location is accessibly
                if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                    log_error(f"Queue Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                    # wait and retry, if the storage is still not available, then terminate
                    time.sleep(settings.STORAGE_WAIT_TIME)
                    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                        log_error(f"Stopping. Queue Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                        self.terminate = True
                        self.error = True
                        continue

                # Update / validate authentication with the API
                response = self.api.authenticate()
                if response != "":
                    log_error(f"Queue Processor failed to authenticate against LexisNexis API. Response: {response}")
                    # wait and retry, if the storage is still not available, then terminate
                    time.sleep(settings.STORAGE_WAIT_TIME)
                    response = self.api.authenticate()
                    if response != "":
                        log_error(f"Stopping. Queue Processor failed to authenticate against LexisNexis API. Response: {response}")
                        self.terminate = True
                        self.error = True
                        continue
                    continue

                # wait until we can download
                self.wait_for_download()

                # continue loop if there are no downloads remaining
                #   (this could happen if some other search sneaks in before this
                #   process wakes)
                if not self.api.check_can_download(True):
                    continue

                # get the next item from the queue
                ## we are doing this again in case the search has been deleted
                ## while waiting for the API to be available
                try:
                    queue = self.searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True, deleted=False).order_by('-update_date')
                    if queue:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except OperationalError as ex:
                    if not self.retry:
                        time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                        self.retry = True
                        continue
                    else:
                        log_error(f"Stopping. Queue Processor failed to retrieve the search queue. {ex}")
                        self.terminate = True
                        continue

                logging.info(f"Downloading items for search: {self.cur_search.search_id}. Skip Value: {self.cur_search.skip_value}.")

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
                for fltr in all_filters:
                    if fltr.filter_name not in self.set_filters:
                        self.set_filters[fltr.filter_name] = []
                    self.set_filters[fltr.filter_name].append(fltr.filter_value)

                ## call the download function with the parameters
                try:
                    results = self.api.download(self.cur_search.query, \
                        self.set_filters, settings.LN_DOWNLOAD_PER_CALL, \
                        self.cur_search.skip_value)
                except Exception as exp: # pylint: disable=broad-except
                    logging.error((f"Failed to downloaded results from the API ",
                                   f"for {self.cur_search.search_id}. ",
                                   f"{create_error_message(exp, os.path.basename(__file__))}"))
                    # Try one more time before stopping processing (in event of connection reset)
                    time.sleep(settings.LN_WAIT_TIME)
                    try:
                        results = self.api.download(self.cur_search.query, \
                            self.set_filters, settings.LN_DOWNLOAD_PER_CALL, \
                            self.cur_search.skip_value)
                    except Exception as exp1: # pylint: disable=broad-except
                        log_error((f"Stopping processing. Failed second attempt to downloaded ",
                                   f"results from the API for search {self.cur_search.search_id}. ",
                                   f"{create_error_message(exp1, os.path.basename(__file__))}"))
                        self.error = True
                        self.terminate = True
                        continue # not adding to retry count since it wasn't a problem with the search

                if "error_message" in results:
                    send_email = False
                    log_error(f"An error occurred processing search id: {self.cur_search.search_id}. {results['error_message']}", self.cur_search)
                    self.cur_search.retry_count = self.cur_search.retry_count + 1
                    self.cur_search.error_message = results["error_message"]
                    if self.cur_search.retry_count > settings.LN_MAX_RETRY:
                        self.cur_search.failed_date = timezone.now()
                        if not self.cur_search.user_notified and settings.NOTIF_EMAIL_DOMAIN:
                            self.cur_search.user_notified = True
                            send_email = True
                    self.cur_search.save()
                    #  send email notification after we're able to save to the database
                    if send_email:
                        send_user_notification(self.cur_search.userid, self.cur_search.query, self.cur_search.date_submitted, 0, True)
                    continue

                ## save the results to the server
                save_location = os.path.join(settings.STORAGE_LOCATION, str(self.cur_search.search_id))
                for result in results["value"]:
                    if self.terminate:
                        break
                    if "Document" not in result or "Content" not in result["Document"] or "ResultId" not in result:
                        log_error(f"WARNING: Could not parse result value from search for ID: {self.cur_search.search_id}.", json.dumps(result))
                        continue
                    full_text = result["Document"]["Content"]
                    file_name = result["ResultId"]
                    try:
                        for fmt in self.set_formats:
                            save_path = os.path.join(save_location, fmt.format_id.format_name)
                            if not os.path.exists(save_location):
                                os.mkdir(save_location)
                            if not os.path.exists(save_path):
                                os.mkdir(save_path)
                            file_path = os.path.join(save_path, file_name)
                            unique_timestamp = datetime.now().strftime('%d%H%M%S%f')
                            if fmt.format_id.format_name == "HTML":
                                if os.path.isfile(os.path.join(save_path, file_name + ".html")):
                                    logging.warning(f"Search: {self.cur_search.search_id}. File path already exists for {file_path + '.html'}")
                                    file_path = file_path + f"_{unique_timestamp}.html"
                                else:
                                    file_path = file_path + ".html"
                                with open(file_path, 'w') as flh:
                                    flh.write(full_text)
                            elif fmt.format_id.format_name == "TXT":
                                if os.path.isfile(os.path.join(save_path, file_name + ".txt")):
                                    logging.warning(f"Search: {self.cur_search.search_id}. File path already exists for {file_path + '.txt'}")
                                    file_path = file_path + f"_{unique_timestamp}.txt"
                                else:
                                    file_path = file_path + ".txt"
                                with open(file_path, 'w') as flh:
                                    flh.write(full_text)
                            elif fmt.format_id.format_name == "TXT Only":
                                try:
                                    cleaned_full_text = remove_html(full_text)
                                except Exception as exp: # pylint: disable=broad-except
                                    log_error((f"Unable to create TXT Only output for search {self.cur_search.search_id}, "
                                               f"filename {file_name}. Error. {create_error_message(exp, os.path.basename(__file__))}"))
                                    cleaned_full_text = full_text ## write the original text to the file instead
                                if os.path.isfile(os.path.join(save_path, file_name + ".txt")):
                                    logging.warning(f"Search: {self.cur_search.search_id}. File path already exists for {file_path + '.txt'}")
                                    file_path = file_path + f"_{unique_timestamp}.txt"
                                else:
                                    file_path = file_path + ".txt"
                                with open(file_path, 'w') as flh:
                                    flh.write(cleaned_full_text)
                    except OSError as ex:
                        log_error(f"Failed to save downloaded results to the server. {create_error_message(ex, os.path.basename(__file__))}")
                        self.terminate = True
                        self.error = True
                        continue # not adding to retry count since it wasn't a problem with the search

                if not self.error:
                    # not including self.terminate since we would want to cleanly save
                    # the record before terminating the service. We only want to skip this
                    # step if the termination was due to a failure

                    ## update the search in the database
                    logging.info(f"Finished saving next {settings.LN_DOWNLOAD_PER_CALL} results for search: {self.cur_search.search_id}")
                    self.cur_search.skip_value = self.cur_search.skip_value + settings.LN_DOWNLOAD_PER_CALL
                    self.cur_search.update_date = timezone.now()
                    self.cur_search.run_time_seconds = self.cur_search.run_time_seconds + int(round(time.time() - start_time, 0))
                    self.cur_search.num_results_in_search = results['@odata.count']
                    self.cur_search.num_results_downloaded = self.cur_search.num_results_downloaded + len(results["value"])
                    ## check if the search is complete
                    if self.cur_search.num_results_downloaded >= self.cur_search.num_results_in_search:
                        logging.info(f"Completed downloading all results for search: {self.cur_search.search_id}")
                        self.cur_search.date_completed = timezone.now()

                    ## save the search record
                    self.cur_search.save()

                    self.retry = False

            except OperationalError as ex:
                if not self.retry:
                    time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                    self.retry = True
                    continue
                else:
                    log_error((f"Stopping. Queue Processor failed due to a database connectivity issue.",
                               f"(search id={'N/A' if self.cur_search is None else self.cur_search.search_id}.",
                               f" {create_error_message(ex, os.path.basename(__file__))}"))
                    self.terminate = True
            except Exception as exp: # pylint: disable=broad-except
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error((f"An unexpected error occurred while processing the queue ",
                           f"(search id={'N/A' if self.cur_search is None else self.cur_search.search_id}.",
                           f" {create_error_message(exp, os.path.basename(__file__))}"))
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped queue processing.")

    def sig_term(self, _, __):
        '''
        Handles command termination
        '''
        self.terminate = True


    def wait_for_download(self):
        '''
        Will wait for an open download window before returning, checking periodically
        '''

        wait_time = round(self.api.get_time_until_next_download(), 0)
        if wait_time > 0:
            logging.info(f"No downloads remaining. Must wait {wait_time} seconds until next available download window is available.")
            # Check if we can download every 10 seconds instead of waiting the full wait_time to
            # be able to handle sig_term triggering (i.e. we don't want to sleep for an hour before
            # a kill command is processed)
            while not self.api.check_can_download(True):
                time.sleep(10)
            logging.info("Resuming processing")

def remove_html(text):
    '''
    Strip HTML from a given text
    '''
    output = []

    bsp = BeautifulSoup(text, "html.parser")

    headline = bsp.h1.string if bsp.h1 is not None and bsp.h1.string is not None else ""
    # check another place for headline
    if not headline:
        headline = bsp.find('nitf:hedline').text if bsp.find('nitf:hedline') is not None else ""

    title = bsp.title.string if bsp.title is not None and bsp.title.string is not None else ""

    # write the title and headline
    output.append(title)
    if title != headline: # prevent duplicate output to file
        output.append(headline)

    text = bsp.find('bodytext').text if bsp.find('bodytext') is not None else ""
    output.append(text)
    full_output = "\n\n".join(output)

    return full_output
