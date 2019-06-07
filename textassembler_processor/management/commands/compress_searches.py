from django.core.management.base import BaseCommand, CommandError
from textassembler_web.utilities import log_error
from django.apps import apps
from django.conf import settings
import logging
import signal
import time
import os
import zipfile
from django.utils import timezone
import traceback
import sys
import shutil

class Command(BaseCommand):
    help = "Process the completed search queue compressing the results"

    def handle(self, *args, **options):
        signal.signal(signal.SIGINT, self.sig_term)
        signal.signal(signal.SIGTERM, self.sig_term)

        self.terminate = False
        self.cur_search = None
        self.retry = False

        # Grab the necessary models
        self.searches = apps.get_model('textassembler_web','searches')
    
        logging.info("Starting compression processing.")
        while not self.terminate:
            time.sleep(1) # take a quick break!
            try: 
                # check that there are items in the queue to process
                # that have completed downloading results and haven't already completed compression
                try:
                    queue = self.searches.objects.filter(date_completed__isnull=False, date_completed_compression__isnull=True, failed_date__isnull=True).order_by('-update_date')
                    if len(queue) > 0:
                        self.cur_search = queue[0]
                        self.retry = False
                    else:
                        self.retry = False
                        continue # nothing to process
                except OperationalError as ex:
                    log_error("Compression Processor failed to retrieve the compress queue. {0}".format(ex))
                    if not self.retry:
                        time.sleep(10) # wait 10 seconds and re-try
                        self.retry = True
                        continue
                    else:
                        self.terminate = True
                    
                
                # verify the storage location is accessibly
                if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):   
                    log_error("Compression Processor failed due to storage location being inaccessible or not writable. {0}".format(settings.STORAGE_LOCATION))
                    # wait 5 minutes, if the storage is still not available, then terminate
                    time.sleep(60*5)
                    if not os.access(settings.STORAGE_LOCATION, os.W_OK) or not os.path.isdir(settings.STORAGE_LOCATION):
                        log_error("Stopping. Compression Processor failed due to storage location being inaccessible or not writable. {0}".format(settings.STORAGE_LOCATION))
                        self.terminate = True
                        continue

                # mark the search record as started compression
                self.cur_search.update_date = timezone.now()
                self.cur_search.date_started_compression = timezone.now()

                # compress the files for the search
                zippath = os.path.join(settings.STORAGE_LOCATION,str(self.cur_search.search_id))
                zipname = settings.APP_NAME.replace(" ","") + "_" + self.cur_search.date_submitted.strftime("%Y%m%d_%H%M%S")
                logging.info("Starting compression of search {0}.".format(self.cur_search.search_id))
                files_to_compress = []
                for root, dirs, files in os.walk(zippath):
                    for f in files:
                        files_to_compress.append(os.path.join(root,f))
                with zipfile.ZipFile(os.path.join(zippath, zipname + ".zip"), 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f in files_to_compress:
                        logging.info("Adding file to zip: {0}. {1}".format(f, f.replace(zippath,"")))
                        zipf.write(f, f.replace(zippath,""))
               
                # this method also works but we can't easily track progress for large zips
                #shutil.make_archive(os.path.join(zippath, zipname),"zip", zippath)

                logging.info("Completed compression of search {0}".format(self.cur_search.search_id))

                #  remove non-compressed files
                logging.info("Started cleanup of non-compressed files for search {0}".format(self.cur_search.search_id))
                for root, dirs, files in os.walk(zippath):
                    for d in dirs:
                        logging.debug("Deleting directory: {0}".format(os.path.join(root,d)))
                        shutil.rmtree(os.path.join(root,d))

                logging.info("Completed cleanup of non-compressed files for search {0}".format(self.cur_search.search_id))
                # TODO - notify the user, set user_notified

                # update the search record
                self.cur_search.update_date = timezone.now()
                self.cur_search.date_completed_compression = timezone.now()

                # save the search record
                self.cur_search.save()

            
            except Exception as e:
                # This scenario shouldn't happen, but handling it just in case
                # so that the service won't quit on-error
                error = "{0} on line {1} of {2}: {3}\n{4}".format(type(e).__name__, sys.exc_info()[-1].tb_lineno, os.path.basename(__file__), e, traceback.format_exc())
                log_error("An unexpected error occured while compressing the completed search queue. {0}".format(error))
                self.terminate = True # stop the service since something is horribly wrong
                continue

        # any cleanup after terminate
        logging.info("Stopped compression processing.")


    def sig_term(self, sig, frame):
        self.terminate = True
