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
        self.retry = False
        self.searches = None
        super().__init__()

    def handle(self, *args, **options): # pylint: disable=too-many-branches, too-many-statements
        '''
        Handles the command when run from the command line.
        '''
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.cur_search = None
        self.retry = False

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')

        logging.info(f"Starting deletion processing. Removing searches more than {settings.NUM_MONTHS_KEEP_SEARCHES} months old or marked as deleted")
        while not self.terminate:
            time.sleep(1) # take a quick break!
            try:
                # check that there are items in the queue to be deleted based on date completed/failed
                try:
                    # delete searches completed/failed before this date
                    delete_date = timezone.now() -  datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)
                    queue = self.searches.objects.filter(
                        Q(date_completed_compression__lte=delete_date)|Q(failed_date__lte=delete_date)|Q(deleted=True)).order_by('-update_date')
                    if queue:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except Exception as ex: # pylint: disable=broad-except
                    if not self.retry:
                        time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                        self.retry = True
                        continue
                    else:
                        log_error(f"Stopping. Deletion Processor failed to retrieve the pending deletion queue. {ex}")
                        self.terminate = True
                        continue

                # verify the storage location is accessibly
                if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                    log_error(f"Deletion Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                    # wait and retry, if the storage is still not available, then terminate
                    time.sleep(settings.STORAGE_WAIT_TIME)
                    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                        log_error(f"Stopping. Deletion Processor failed due to {settings.STORAGE_LOCATION} being inaccessible or not writable.")
                        self.terminate = True
                        continue

                # check that there are items in the queue to be deleted based on date completed/failed
                # we need to recheck this in case it changed while waiting for the storage
                # location to become accessible
                try:
                    # delete searches completed/failed before this date
                    delete_date = timezone.now() -  datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)
                    queue = self.searches.objects.filter(
                        Q(date_completed_compression__lte=delete_date)|Q(failed_date__lte=delete_date)|Q(deleted=True)).order_by('-update_date')
                    if queue:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except Exception as ex: # pylint: disable=broad-except
                    logging.error(ex)
                    if not self.retry:
                        time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                        self.retry = True
                        continue
                    else:
                        log_error(f"Stopping. Deletion Processor failed to retrieve the pending deletion queue. {ex}")
                        self.terminate = True
                        continue

                #  remove the files`
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

                # delete the search record
                try:
                    self.cur_search.delete()
                except OperationalError as oexp:
                    time.sleep(settings.DB_WAIT_TIME) # wait and re-try (giving this more time in case db server is being rebooted)
                    try:
                        self.cur_search.delete()
                    except OperationalError as oexp:
                        log_error("Stopping. A database error occured while trying to delete the record to the database", oexp)
                        self.terminate = True
                        continue


            except Exception as exp: #pylint: disable=broad-except
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error(f"An unexpected error occurred while deleting old searches. {create_error_message(exp, os.path.basename(__file__))}")
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped compression processing.")

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
