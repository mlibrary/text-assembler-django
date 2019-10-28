'''
Process completed searches to compress results
'''
import logging
import signal
import time
import os
import zipfile
import shutil
import re
from django.core.management.base import BaseCommand
from django.db import OperationalError
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from textassembler_web.utilities import log_error, create_error_message, send_user_notification

class Command(BaseCommand):
    '''
    Compress completed searches
    '''
    help = "Process the completed search queue compressing the results"

    def __init__(self):
        self.terminate = False
        self.cur_search = None
        self.searches = None
        self.retry_counts = {"storage":0, "database":0, "filesystem":0}

        super().__init__()

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.cur_search = None

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')

        logging.info("Starting compression processing.")
        while not self.terminate:
            time.sleep(1) # take a quick break!
            try:
                (queue, cont) = self.get_queue()
                if cont or not queue or self.terminate:
                    continue

                # verify the storage location is accessibly
                cont = self.check_storage()
                if cont or self.terminate:
                    continue

                # get the next item from the queue
                ## we are doing this again in case the search has been deleted
                ## while waiting for the API to be available
                (queue, cont) = self.get_queue()
                if cont or not queue or self.terminate:
                    continue
                self.cur_search = queue[0]

                # mark the search record as started compression
                cont = self.set_start_time()
                if cont or not queue or self.terminate:
                    continue

                cont = self.compress_search()
                if cont or self.terminate:
                    continue

                ## save the results to the database
                (cont, send_email) = self.update_search_with_results()
                if cont or self.terminate:
                    continue

                #  send email notification
                #   sending this after the DB save in case that fails for some reason
                #   this is to prevent users from receiving multiple notifications
                if send_email:
                    send_user_notification(self.cur_search.userid, self.cur_search.query,
                                           self.cur_search.date_submitted, self.cur_search.num_results_downloaded)

            except Exception as exp: # pylint: disable=broad-except
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error((f"Stopping. An unexpected error occurred while compressing the completed search queue. "
                           f"{create_error_message(exp, os.path.basename(__file__))}"))
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped compression processing.")

    def get_queue(self):
        '''
        Check if there are items in the queueu to process that have
        completed downloading their results and haven't already
        completed compression.
        Returns:
            queue (list): Items to be processed
            cont (bool): If the loop should continue or not
        '''
        # check that there are items in the queue to process
        # that have completed downloading results and haven't already completed compression
        try:
            queue = self.searches.objects.filter(
                date_completed__isnull=False, date_completed_compression__isnull=True, failed_date__isnull=True, deleted=False).order_by('-update_date')
            self.retry_counts["database"] = 0
            if not queue:
                return (None, True)
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.warning(f"Compression Processor failed to retrieve the compress queue. Will try again in {settings.DB_WAIT_TIME} seconds. {ex}")
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
                logging.error(f"Compression Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                # wait and retry, if the storage is still not available, then terminate
                time.sleep(settings.STORAGE_WAIT_TIME)
                self.retry_counts["storage"] = self.retry_counts["storage"] + 1
            else:
                log_error(f"Stopping. Compression Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                self.terminate = True
            return True
        self.retry_counts["storage"] = 0
        return False

    def set_start_time(self):
        '''
        Set the start time for the compression to now
        Returns:
            continue (bool): If you need to continue the loop
        '''
        self.cur_search.update_date = timezone.now()
        self.cur_search.date_started_compression = timezone.now()
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

    def compress_search(self):
        '''
        Compresses the search results
        Returns:
            cont (bool): If the loop should continue
        '''
        try:
            # compress the files for the search
            zippath = os.path.join(settings.STORAGE_LOCATION, str(self.cur_search.search_id))
            zipname = settings.APP_NAME.replace(" ", "") + "_" + self.cur_search.date_submitted.strftime("%Y%m%d_%H%M%S")
            logging.info(f"Starting compression of search {self.cur_search.search_id}.")
            files_to_compress = []
            for root, dirs, files in os.walk(zippath):
                for fln in files:
                    files_to_compress.append(os.path.join(root, fln))
            with zipfile.ZipFile(os.path.join(zippath, zipname + ".zip"), 'w', zipfile.ZIP_DEFLATED) as zipf:
                for fln in files_to_compress:
                    target_name = re.sub(zippath+r'/\d+/\d+/\d+/', '', fln)
                    logging.info(f"Adding file to zip: {fln}. Target Name: {target_name}")
                    zipf.write(fln, target_name)

            logging.info(f"Completed compression of search {self.cur_search.search_id}")

            #  remove non-compressed files
            logging.info(f"Started cleanup of non-compressed files for search {self.cur_search.search_id}")
            for root, dirs, files in os.walk(zippath):
                for dirn in dirs:
                    logging.debug(f"Deleting directory: {os.path.join(root, dirn)}")
                    shutil.rmtree(os.path.join(root, dirn))

            logging.info(f"Completed cleanup of non-compressed files for search {self.cur_search.search_id}")
            self.retry_counts["filesystem"] = 0
        except OSError as ex:
            if self.retry_counts["filesystem"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error(f"Failed to compress the search: {self.cur_search.search_id}. {ex}")
                self.retry_counts["filesystem"] = self.retry_counts["filesystem"] + 1
            else:
                log_error(f"Stopping. Failed to compress the search for {self.cur_search.search_id}. {create_error_message(ex, os.path.basename(__file__))}")
                self.terminate = True
            return True
        return False

    def update_search_with_results(self):
        '''
        Save the compression with the final results
        Returns:
            cont (bool): If the loop should continue
            send_email (bool): If an email should be sent to the user
        '''
        try:
            self.cur_search.update_date = timezone.now()
            self.cur_search.date_completed_compression = timezone.now()
            if not self.cur_search.user_notified and settings.NOTIF_EMAIL_DOMAIN:
                self.cur_search.user_notified = True
                send_email = True
            else:
                send_email = False
            self.cur_search.save()
            self.retry_counts["database"] = 0
            return (False, send_email)
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error((f"Stopping. Compression Processor failed due to a database connectivity issue.",
                           f"(search id={'N/A' if self.cur_search is None else self.cur_search.search_id}.",
                           f" {create_error_message(ex, os.path.basename(__file__))}"))
                self.terminate = True
            return (True, False)

    def sig_term(self, _, __):
        '''
        Handle user interuption
        '''
        self.terminate = True
