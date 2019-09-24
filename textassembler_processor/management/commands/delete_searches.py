'''
Processes pending deletions
'''
import logging
import signal
import time
import os
import shutil
import datetime
from django.core.management.base import BaseCommand
from django.db import OperationalError
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from textassembler_web.utilities import log_error, create_error_message

class Command(BaseCommand):
    '''
    Delete searches that are old from the system and the database.
    '''
    help = "Process searches pending deletion."

    def __init__(self):
        self.terminate = False
        self.cur_search = None
        self.searches = None
        self.retry_counts = {"storage":0, "database":0, "filesystem":0}

        super().__init__()

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        '''
        Handles the command when run from the command line.
        '''
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.cur_search = None

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')

        logging.info(f"Starting deletion processing. Removing searches more than {settings.NUM_MONTHS_KEEP_SEARCHES} months old or marked as deleted")
        while not self.terminate:
            time.sleep(1) # take a quick break!
            try:
                # check that there are items in the queue to be deleted based on date completed/failed
                (queue, cont) = self.get_queue()
                if cont or not queue or self.terminate:
                    continue


                # verify the storage location is accessibly
                cont = self.check_storage()
                if cont or self.terminate:
                    continue

                # check that there are items in the queue to be deleted based on date completed/failed
                # we need to recheck this in case it changed while waiting for the storage
                # location to become accessible
                (queue, cont) = self.get_queue()
                if cont or not queue or self.terminate:
                    continue
                self.cur_search = queue[0]

                #  remove the files
                self.delete_search_files()

                # delete the search record
                cont = self.delete_search_record()
                if cont or not queue or self.terminate:
                    continue

            except Exception as exp: #pylint: disable=broad-except
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error((f"An unexpected error occurred while deleting old searches. "
                           f"{create_error_message(exp, os.path.basename(__file__))}"))
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped compression processing.")

    def get_queue(self):
        '''
        Get the searches to be deleted
        Returns:
            queue (list): Items to be deleted
            cont (bool): If the loop should continue or not
        '''
        try:
            # delete searches completed/failed before this date
            delete_date = timezone.now() -  datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)
            queue = self.searches.objects.filter(
                Q(date_completed_compression__lte=delete_date)|Q(failed_date__lte=delete_date)|Q(deleted=True)).order_by('-update_date')
            self.retry_counts["database"] = 0
            if queue:
                return (queue, False)
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.warning(f"Deletion Processor failed to retrieve the deletion queue. Will try again in {settings.DB_WAIT_TIME} seconds. {ex}")
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error(f"Stopping. Deletion Processor failed to retrieve the pending deletion queue. {ex}")
                self.terminate = True
        return (None, True)

    def check_storage(self):
        '''
        Check to see if the storage location is available
        Returns:
            continue (bool): If you need to continue the loop
        '''
        if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
            if self.retry_counts["storage"] <= settings.NUM_PROCESSOR_RETRIES:
                logging.error(f"Deletion Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                # wait and retry, if the storage is still not available, then terminate
                time.sleep(settings.STORAGE_WAIT_TIME)
                self.retry_counts["storage"] = self.retry_counts["storage"] + 1
            else:
                log_error(f"Stopping. Deletion Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                self.terminate = True
            return True
        self.retry_counts["storage"] = 0
        return False

    def delete_search_files(self):
        '''
        Delete the files on the storage location for the current search
        '''
        logging.info(f"Started removal of files for search {self.cur_search.search_id}")
        save_location = os.path.join(settings.STORAGE_LOCATION, str(self.cur_search.search_id))
        zip_path = find_zip_file(self.cur_search.search_id)

        if os.path.isdir(save_location):
            try:
                shutil.rmtree(save_location)
            except OSError as ex1:
                log_error(f"Could not delete files for search {self.cur_search.search_id}. {ex1}", self.cur_search)
        if zip_path != None and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError as ex2:
                log_error(f"Could not delete the zipped file for search {self.cur_search.search_id}. {ex2}", self.cur_search)
        if os.path.isdir(save_location):
            try:
                os.rmdir(save_location)
            except OSError as ex3:
                log_error(f"Could not delete root directory for search {self.cur_search.search_id}. {ex3}", self.cur_search)
        logging.info(f"Completed deletion of files for search {self.cur_search.search_id}")

    def delete_search_record(self):
        '''
        Delete the search record  from the database
        Returns:
            cont (bool): If the loop should continue
        '''
        try:
            self.cur_search.delete()
            self.retry_counts["database"] = 0
            return False
        except OperationalError as ex:
            if self.retry_counts["database"] <= settings.NUM_PROCESSOR_RETRIES:
                time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                self.retry_counts["database"] = self.retry_counts["database"] + 1
            else:
                log_error((f"Stopping. Deletion Processor failed due to a database connectivity issue.",
                           f"(search id={'N/A' if self.cur_search is None else self.cur_search.search_id}.",
                           f" {create_error_message(ex, os.path.basename(__file__))}"))
                self.terminate = True
            return True

    def sig_term(self, _, __):
        '''
        Handles user termination of the process.
        '''
        self.terminate = True

def find_zip_file(search_id):
    '''
    For the given search ID, it will locate the full path for the zip file
    '''
    filepath = os.path.join(settings.STORAGE_LOCATION, str(search_id))
    for root, _, files in os.walk(filepath):
        for name in files:
            if name.endswith("zip"):
                return os.path.join(root, name)
    return None
