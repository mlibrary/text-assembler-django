from django.core.management.base import BaseCommand, CommandError
from textassembler_web.utilities import log_error, create_error_message
from django.apps import apps
from django.conf import settings
import logging
import signal
import time
import os
from django.utils import timezone
import sys
import shutil
import datetime
from django.db.models import Q

class Command(BaseCommand):
    '''
    Delete searches that are old from the system and the database.
    '''
    help = "Process searches pending deletion."

    def handle(self, *args, **options):
        '''
        Handles the command when run from the command line.
        '''
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.cur_search = None
        self.retry = False

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web','searches')
    
        logging.info("Starting deletion processing. Removing searches more than {0} months old".format(settings.NUM_MONTHS_KEEP_SEARCHES))
        while not self.terminate:
            time.sleep(1) # take a quick break!
            try: 
                # check that there are items in the queue to be deleted based on date completed/failed
                try:
                    # delete searches completed/failed before this date
                    delete_date = timezone.now() -  datetime.timedelta(days=settings.NUM_MONTHS_KEEP_SEARCHES * 30)
                    queue = self.searches.objects.filter(Q(date_completed_compression__lte=delete_date)|Q(failed_date__lte=delete_date)).order_by('-update_date')
                    if len(queue) > 0:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except Exception as ex:
                    log_error("Deletion Processor failed to retrieve the pending deletion queue. {0}".format(ex))
                    if not self.retry:
                        time.sleep(10) # wait 10 seconds and re-try
                        self.retry = True
                        continue
                    else:
                        self.terminate = True
                    
                
                # verify the storage location is accessibly
                if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):   
                    log_error("Deletion Processor failed due to storage location being inaccessible or not writable. {0}".format(settings.STORAGE_LOCATION))
                    # wait 5 minutes, if the storage is still not available, then terminate
                    time.sleep(60*5)
                    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                        log_error("Stopping. Deletion Processor failed due to storage location being inaccessible or not writable. {0}".format(settings.STORAGE_LOCATION))
                        self.terminate = True
                        continue

                #  remove the files`
                logging.info("Started removal of files for search {0}".format(self.cur_search.search_id))
                save_location = os.path.join(settings.STORAGE_LOCATION,str(self.cur_search.search_id))
                zip_path = self.find_zip_file(self.cur_search.search_id)

                if os.path.isdir(save_location):
                    try:
                        shutil.rmtree(save_location)
                    except Exception as e1:
                        log_error("Could not delete files for search {0}. {1}".format(self.cur_search.search_id,e1), search)
                if zip_path != None and os.path.exists(zip_path):
                    try:
                        os.remove(zip_path)
                    except Exception as e2:
                        log_error("Could not delete the zipped file for search {0}. {1}".format(self.cur_search.search_id, e2), search)
                if os.path.isdir(save_location):
                    try:
                        shutil.rmdir(save_location)
                    except Exception as e3:
                        log_error("Could not delete root directory for search {0}. {1}".format(self.cur_search.search_id,e3), search)
                logging.info("Completed deletion of files for search {0}".format(self.cur_search.search_id))

                # delete the search record
                self.cur_search.delete()

            
            except Exception as e:
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error("An unexpected error occured while deleting old searches. {0}".format(create_error_message(e, os.path.basename(__file__))))
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped compression processing.")

    def find_zip_file(self, search_id):
        '''
        For the given search ID, it will locate the full path for the zip file
        '''
        filepath = os.path.join(settings.STORAGE_LOCATION,str(search_id))
        for root, dirs, files in os.walk(filepath):
            for name in files:
                if name.endswith("zip"):
                    return os.path.join(root,name)
        return None

    def sig_term(self, sig, frame):
        '''
        Handles user termination of the process.
        '''
        self.terminate = True
