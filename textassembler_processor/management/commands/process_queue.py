"""
Processes the search queue to download results from LexisNexis
"""
import time
import logging
import signal
import os
import json
from datetime import datetime
from requests.exceptions import ReadTimeout
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
        self.retry_counts = {"storage":0, "database":0, "api":0, "auth":0, "filesystem":0}
        self.api = None
        self.set_formats = None
        self.set_filters = None
        self.created_files = [] # track the files that have been created before a DB save occurs

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')
        self.filters = apps.get_model('textassembler_web', 'filters')
        self.download_formats = apps.get_model('textassembler_web', 'download_formats')
        self.available_formats = apps.get_model('textassembler_web', 'available_formats')

        super().__init__()

    def handle(self, *args, **options): # (we need the if-statements to process the continues) pylint: disable=too-many-branches
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
                (queue, cont) = self.get_queue()
                if cont or not queue:
                    continue

                # verify the storage location is accessibly
                cont = self.check_storage()
                if cont:
                    continue

                # Update / validate authentication with the API
                cont = self.authenticate_api()
                if cont:
                    continue

                # wait until we can download
                self.wait_for_download()
                if self.terminate:
                    continue

                # continue loop if there are no downloads remaining
                #   (this could happen if some other search sneaks in on the UI
                #   before this process wakes)
                if not self.api.check_can_download(True):
                    continue

                # get the next item from the queue
                ## we are doing this again in case the search has been deleted
                ## while waiting for the API to be available
                (queue, cont) = self.get_queue()
                if cont or not queue:
                    continue
                self.cur_search = queue[0]

                logging.info(f"Downloading items for search: {self.cur_search.search_id}. Skip Value: {self.cur_search.skip_value}.")

                # check if this is a new search and set the start time
                cont = self.set_start_time()
                if cont or not queue:
                    continue

                # download next 10 items for the current search
                start_time = time.time()
                ## retrieve relavent search fields
                self.set_search_filters()

                ## call the download function with the parameters
                (results, cont) = self.get_next_results()
                if cont:
                    continue

                if "error_message" in results:
                    cont = self.handle_results_error(results)
                    if cont:
                        continue

                ## save the results to the server
                (cont, brk) = self.save_results(results)
                if brk:
                    break
                if cont:
                    continue

                ## save the results to the database
                self.update_search_with_results(results, start_time)

            except Exception as exp: # pylint: disable=broad-except
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error((f"An unexpected error occurred while processing the queue ",
                           f"(search id={'N/A' if self.cur_search is None else self.cur_search.search_id}.",
                           f" {create_error_message(exp, os.path.basename(__file__))}"))
                self.terminate = True # stop the service since something is horribly wrong

        # any cleanup after terminate
        remove_files(self.created_files, "After terminate flag is processed.") # remove any created files since the error since the DB will not reflect these
        logging.info("Stopped queue processing.")

    def sig_term(self, _, __):
        '''
        Handles command termination
        '''
        self.terminate = True

    def update_search_with_results(self, results, start_time):
        '''
        If there were no errors, update the search in the database
        with the run results for that set of downloads.
        '''
        try:
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

                self.created_files = []
                self.retry_counts["database"] = 0
        except OperationalError as ex:
            # remove any created files since the error since the DB will not reflect these
            remove_files(self.created_files, "After OperationalErrorr updating the search record in the DB.")
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error((f"Stopping. Queue Processor failed due to a database connectivity issue.",
                           f"(search id={'N/A' if self.cur_search is None else self.cur_search.search_id}.",
                           f" {create_error_message(ex, os.path.basename(__file__))}"))
                self.terminate = True

    def save_results(self, results):
        '''
        Save the results to the server
        Return:
            cont (bool): If the loop should continue
            brk (bool): If the loop should break
        '''
        # remove any created files since the error since the DB will not reflect these
        remove_files(self.created_files, "Before saving next batch of files")
        save_location = os.path.join(settings.STORAGE_LOCATION, str(self.cur_search.search_id))

        for result in results["value"]:
            if self.terminate:
                return (False, True)
            if "Document" not in result or "Content" not in result["Document"] or "ResultId" not in result:
                log_error(f"WARNING: Could not parse result value from search for ID: {self.cur_search.search_id}.", json.dumps(result))
                return (True, False)
            full_text = result["Document"]["Content"]
            file_name = result["ResultId"]
            try:
                for fmt in self.set_formats:
                    save_path = os.path.join(save_location, fmt.format_id.format_name)
                    if not os.path.exists(save_location):
                        os.mkdir(save_location)
                    if not os.path.exists(save_path):
                        os.mkdir(save_path)
                    unique_timestamp = datetime.now().strftime('%d%H%M%S%f')
                    if fmt.format_id.format_name == "HTML":
                        self.save_html(save_path, file_name, full_text, unique_timestamp)
                    elif fmt.format_id.format_name == "TXT":
                        self.save_txt(save_path, file_name, full_text, unique_timestamp)
                    elif fmt.format_id.format_name == "TXT Only":
                        self.save_txt_only(save_path, file_name, full_text, unique_timestamp)
                self.retry_counts["filesystem"] = 0
            except OSError as ex:
                if self.retry_counts["filesystem"] <= settings.NUM_PROCESSOR_RETRIES:
                    logging.error((f"Failed to save downloaded results to the server for search {self.cur_search.search_id}. ",
                                   f"{create_error_message(ex, os.path.basename(__file__))}"))
                    self.retry_counts["filesystem"] = self.retry_counts["filesystem"] + 1
                else:
                    self.terminate = True
                    self.error = True
                # remove any created files since the error since the DB will not reflect these
                remove_files(self.created_files, "After OSError saving the files.")
                return (True, False)
        return (False, False)

    def save_html(self, save_path, file_name, full_text, unique_timestamp):
        '''
        Save the full_text as an HTML
        '''
        file_path = os.path.join(save_path, file_name)
        if os.path.isfile(os.path.join(save_path, file_name + ".html")):
            logging.debug(f"Search: {self.cur_search.search_id}. File path already exists for {os.path.join(save_path, file_name + '.html')}")
            file_path = file_path  + f"_{unique_timestamp}.html"
        else:
            file_path = file_path + ".html"
        with open(file_path, 'w') as flh:
            flh.write(full_text)
            self.created_files.append(file_path)

    def save_txt(self, save_path, file_name, full_text, unique_timestamp):
        '''
        Save the full_text as a txt
        '''
        file_path = os.path.join(save_path, file_name)
        if os.path.isfile(os.path.join(save_path, file_name + ".txt")):
            logging.debug(f"Search: {self.cur_search.search_id}. File path already exists for {os.path.join(save_path, file_name + '.txt')}")
            file_path = file_path  + f"_{unique_timestamp}.txt"
        else:
            file_path = file_path + ".txt"
        with open(file_path, 'w') as flh:
            flh.write(full_text)
            self.created_files.append(file_path)

    def save_txt_only(self, save_path, file_name, full_text, unique_timestamp):
        '''
        Convert the full_text to strip html characters and save as a txt
        '''
        try:
            cleaned_full_text = remove_html(full_text)
        except Exception as exp: # pylint: disable=broad-except
            log_error((f"Unable to create TXT Only output for search {self.cur_search.search_id}, "
                       f"filename {file_name}. Error. {create_error_message(exp, os.path.basename(__file__))}"))
            cleaned_full_text = full_text ## write the original text to the file instead

        file_path = os.path.join(save_path, file_name)
        if os.path.isfile(os.path.join(save_path, file_name + ".txt")):
            logging.debug(f"Search: {self.cur_search.search_id}. File path already exists for {os.path.join(save_path, file_name + '.txt')}")
            file_path = file_path  + f"_{unique_timestamp}.txt"
        else:
            file_path = file_path + ".txt"
        with open(file_path, 'w') as flh:
            flh.write(cleaned_full_text)
            self.created_files.append(file_path)

    def handle_results_error(self, results):
        '''
        handles error messages in the results
        Returns:
            cont (bool): If the loop should continue
        '''
        if "error_message" not in results:
            return False
        # Check for throttle limit error from API, this should not happen, but just to make sure search
        # doesn't fail due to misconfigured throttle settings
        if "response_code" in results and results["response_code"] == 429:
            log_error((f"An error occurred processing search id: {self.cur_search.search_id}. "
                       f"Misconfigured throttle limits. {results['error_message']}"))
            return True

        # Check for gateway timeout, to not add to retry count
        if "response_code" in results and results["response_code"] == 504:
            logging.error(f"A gateway timeout occured processing search {self.cur_search.search_id}.")
            return True

        send_email = False
        log_error(f"An error occurred processing search id: {self.cur_search.search_id}. {results['error_message']}", self.cur_search)
        self.cur_search.retry_count = self.cur_search.retry_count + 1
        self.cur_search.error_message = results["error_message"]

        if self.cur_search.retry_count > settings.LN_MAX_RETRY:
            self.cur_search.failed_date = timezone.now()
            if not self.cur_search.user_notified and settings.NOTIF_EMAIL_DOMAIN:
                self.cur_search.user_notified = True
                send_email = True
        try:
            self.cur_search.save()
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error(f"Failed to update the search failed status in the database.")
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error(f"Stopping. Failed to set the failed search status in the database for {self.cur_search.search_id}. {ex}")
                self.terminate = True
            return True

        #  send email notification after we're able to save to the database
        if send_email:
            send_user_notification(self.cur_search.userid, self.cur_search.query, self.cur_search.date_submitted, 0, True)
        return True

    def get_next_results(self):
        '''
        Get the next set of results from the API
        Returns:
            results (list): Results from the API for the cur_search
            cont (bool): If the loop should continue
        '''
        try:
            results = self.api.download(self.cur_search.query, \
                self.set_filters, settings.LN_DOWNLOAD_PER_CALL, \
                self.cur_search.skip_value)
            self.retry_counts["api"] = 0
            return (results, False)
        except ReadTimeout as rte:
            if self.retry_counts["api"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error((f"Failed to download the results from the API due to a ReadTimeout.",
                               f"If this continues, consider raising the TIMEOUT_SECONDS ",
                               f"(current: {settings.LN_TIMEOUT}) configuration."))
                # Wait before continuing processing to avoid re-triggering the error immediately
                time.sleep(settings.LN_WAIT_TIME)
            else:
                log_error((f"Stopping processing. Failed {self.retry_counts['api']} attempt(s) to downloaded ",
                           f"results from the API for search {self.cur_search.search_id} due to API timeout. ",
                           f"{create_error_message(rte, os.path.basename(__file__))}"))
                self.error = True
                self.terminate = True
            self.retry_counts["api"] = self.retry_counts["api"] + 1
        except Exception as exp: # pylint: disable=broad-except
            if self.retry_counts["api"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error((f"Failed to downloaded results from the API ",
                               f"for {self.cur_search.search_id}. ",
                               f"{create_error_message(exp, os.path.basename(__file__))}"))
                # Try one more time before stopping processing (in event of connection reset)
                time.sleep(settings.LN_WAIT_TIME)
            else:
                log_error((f"Stopping processing. Failed second attempt to downloaded ",
                           f"results from the API for search {self.cur_search.search_id}. ",
                           f"{create_error_message(exp, os.path.basename(__file__))}"))
                self.error = True
                self.terminate = True
            self.retry_counts["api"] = self.retry_counts["api"] + 1
        return (None, True) # not adding to retry count since it wasn't a problem with the search

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
            while not self.api.check_can_download(True) and not self.terminate:
                try:
                    time.sleep(10)
                    self.retry_counts["database"] = 0
                except OperationalError as ex:
                    if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                        logging.warning(f"Queue Processor failed to check download status. Will try again in {settings.DB_WAIT_TIME} seconds. {ex}")
                        time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                        self.retry_counts["database"] = self.retry_counts["database"] + 1
                    else:
                        log_error(f"Stopping. Queue Processor failed to check the download status. {ex}")
                        self.terminate = True
                    continue
            logging.info("Resuming processing")

    def get_queue(self):
        '''
        Get the search queue from the database
        Returns:
            queue (list): Search queue to be processed
            continue (bool): If you need to continue the loop
        '''
        try:
            # check that there are items in the queue to process
            queue = self.searches.objects.filter(date_completed__isnull=True, failed_date__isnull=True, deleted=False).order_by('update_date')
            self.retry_counts["database"] = 0
            if not queue:
                return (None, True) # nothing to process
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.warning(f"Queue Processor failed to retrieve the search queue. Will try again in {settings.DB_WAIT_TIME} seconds. {ex}")
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error(f"Stopping. Queue Processor failed to retrieve the search queue. {ex}")
                self.terminate = True
            return (None, True)
        return (queue, False)

    def check_storage(self):
        '''
        Check to see if the storage location is available
        Returns:
            continue (bool): If you need to continue the loop
        '''
        if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
            if self.retry_counts["storage"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error(f"Queue Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                # wait and retry, if the storage is still not available, then terminate
                time.sleep(settings.STORAGE_WAIT_TIME)
                self.retry_counts["storage"] = self.retry_counts["storage"] + 1
            else:
                log_error(f"Stopping. Queue Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                self.terminate = True
                self.error = True
            return True
        self.retry_counts["storage"] = 0
        return False

    def authenticate_api(self):
        '''
        Authenticate against the API
        Returns:
            continue (bool): If you need to continue the loop
        '''
        response = self.api.authenticate()
        if response != "":
            if self.retry_counts["auth"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error(f"Queue Processor failed to authenticate against LexisNexis API. Response: {response}")
                # wait and retry, if the storage is still not available, then terminate
                time.sleep(settings.STORAGE_WAIT_TIME)
                self.retry_counts["auth"] = self.retry_counts["auth"] + 1
            else:
                log_error(f"Stopping. Queue Processor failed to authenticate against LexisNexis API. Response: {response}")
                self.terminate = True
                self.error = True
            return True
        self.retry_counts["auth"] = 0
        return False

    def set_start_time(self):
        '''
        Set the start time for the search to now
        Returns:
            continue (bool): If you need to continue the loop
        '''
        if self.cur_search.date_started:
            return False
        self.cur_search.date_started = timezone.now()

        try:
            self.cur_search.save()
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error(f"Failed to update the start time in the database.")
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error(f"Stopping. Failed to set the start time in the database for {self.cur_search.search_id}. {ex}")
                self.terminate = True
            return True
        return False

    def set_search_filters(self):
        '''
        Set the filters for the search to use in the API call
        '''
        all_filters = self.filters.objects.filter(search_id=self.cur_search)
        self.set_formats = self.download_formats.objects.filter(search_id=self.cur_search)
        self.set_filters = {}
        for fltr in all_filters:
            if fltr.filter_name not in self.set_filters:
                self.set_filters[fltr.filter_name] = []
            self.set_filters[fltr.filter_name].append(fltr.filter_value)


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

def remove_files(files_to_remove=None, message=""):
    '''
    Removes the list of files from the filesystem
    Params:
        files_to_remove (array): list of full filepaths to delete
        message (string): message to print before removing files
    '''
    if not files_to_remove:
        return # nothing to remove

    logging.warning(f"Removing {len(files_to_remove)} from the server. {message}")
    for file_to_remove in files_to_remove:
        if os.path.isfile(file_to_remove):
            logging.warning("Deleting {file_to_remove}.")
            try:
                os.remove(file_to_remove)
            except OSError as ose:
                log_error(f"Failed to delete {file_to_remove} from the server. {create_error_message(ose, os.path.basename(__file__))}")
