'''
Process completed searches to compress results
'''
import logging
import signal
import time
import os
import zipfile
import shutil
from django.core.management.base import BaseCommand
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
        self.retry = False
        self.searches = None
        super().__init__()

    def handle(self, *args, **options): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.cur_search = None
        self.retry = False

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web', 'searches')

        logging.info("Starting compression processing.")
        while not self.terminate:
            time.sleep(1) # take a quick break!
            try:
                # check that there are items in the queue to process
                # that have completed downloading results and haven't already completed compression
                try:
                    queue = self.searches.objects.filter(
                        date_completed__isnull=False, date_completed_compression__isnull=True, failed_date__isnull=True).order_by('-update_date')
                    if queue:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except Exception as ex: # pylint: disable=broad-except
                    log_error(f"Compression Processor failed to retrieve the compress queue. {ex}")
                    if not self.retry:
                        time.sleep(10) # wait 10 seconds and re-try
                        self.retry = True
                        continue
                    else:
                        self.terminate = True


                # verify the storage location is accessibly
                if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                    log_error(f"Compression Processor failed due to storage location being inaccessible or not writable. {settings.STORAGE_LOCATION}")
                    # wait 5 minutes, if the storage is still not available, then terminate
                    time.sleep(60*5)
                    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or \
                        not os.path.isdir(settings.STORAGE_LOCATION):
                        log_error(f"Stopping. Compression Processor failed due to {settings.STORAGE_LOCATION} being inaccessible or not writable.")
                        self.terminate = True
                        continue

                # mark the search record as started compression
                self.cur_search.update_date = timezone.now()
                self.cur_search.date_started_compression = timezone.now()

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
                        logging.info(f"Adding file to zip: {fln}. {fln.replace(zippath,'')}")
                        zipf.write(fln, fln.replace(zippath, ""))

                # this method also works but we can't easily track progress for large zips
                #shutil.make_archive(os.path.join(zippath, zipname),"zip", zippath)

                logging.info(f"Completed compression of search {self.cur_search.search_id}")

                #  remove non-compressed files
                logging.info(f"Started cleanup of non-compressed files for search {self.cur_search.search_id}")
                for root, dirs, files in os.walk(zippath):
                    for dirn in dirs:
                        logging.debug(f"Deleting directory: {os.path.join(root, dirn)}")
                        shutil.rmtree(os.path.join(root, dirn))

                logging.info(f"Completed cleanup of non-compressed files for search {self.cur_search.search_id}")
                #  send email notification
                send_user_notification(self.cur_search.userid, self.cur_search.query, self.cur_search.date_submitted, self.cur_search.num_results_downloaded)
                self.cur_search.user_notified = True

                # update the search record
                self.cur_search.update_date = timezone.now()
                self.cur_search.date_completed_compression = timezone.now()

                # save the search record
                self.cur_search.save()


            except Exception as exp: # pylint: disable=broad-except
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                log_error(f"An unexpected error occured while compressing the completed search queue. {create_error_message(exp, os.path.basename(__file__))}")
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped compression processing.")


    def sig_term(self, _, __):
        '''
        Handle user interuption
        '''
        self.terminate = True
