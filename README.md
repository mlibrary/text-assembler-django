Text Assembler
=============
This is a web-based application that makes use of the Lexis Nexis API for searching and downloading from their 
data set.

Contents
--------
* [Assumptions](#assumptions)
* [Install & Setup](#install-setup)
* [Applying Updates](#applying-updates)
* [WSK to API Transition](#wsk-to-api-transition)
* [Technical Overview](#technical-overview)

Assumptions
-----------
* This application uses OAuth2 for authentication. Some form of authentication is required to obtain a unique userid. 
This project does not include documentation for setting up an OAuth provider, just the code for using it as an 
OAuth client.
* This application was built on Ubuntu 18.04 and has not been tested on other versions or distributions.
* This application was built using MariaDB 10.2 and has not been tested on other versions or another DBMS.

Install & Setup
---------------
* Install the base software
```
sudo aptitude install python3
sudo apt install python3-pip
sudo pip3 install Django
sudo aptitude install libapache2-mod-wsgi-py3
```

* Checkout the code
```
mkdir /var/www/text-assembler
git clone git@gitlab.msu.edu:msu-libraries/public/text-assembler.git .
```

* Install dependencies
```
cd /var/www/text-assembler
python3.6 -m venv ta_env
source ta_env/bin/activate
pip install -r requirements.txt
deactivate
```
* Update environment variables in `/etc/apache2/envars`
```
export LANG='en_US.UTF-8'
export LC_ALL='en_US.UTF-8'
```
* Configure the application:  
Copy all of the `.example` files (find . -name '*.example') and make necessary changes.   
This will also involve creating a database and an application user, which will be parameters in the main config file.

* Run the database setup
```
cd /var/www/text-assembler
ta_env/bin/python manage.py migrate
```

* Configure Apache:   
Create a new Apache configuration file using the below as an example
```
<VirtualHost *:80>
        ServerName textassembler.lib.msu.edu
        Redirect "/" "https://textassembler.lib.msu.edu/"
</VirtualHost>
<VirtualHost *:443>
        ServerName textassembler.lib.msu.edu

        DocumentRoot /var/www/text-assembler

        SSLEngine on
        SSLCertificateFile /etc/ssl/private/textassembler.crt
        SSLCertificateKeyFile /etc/ssl/private/textassembler.key

        WSGIDaemonProcess textassembler.lib.msu.edu processes=2 threads=15 display-name=textassembler python-home=/var/www/text-assembler/ta_env
        WSGIProcessGroup textassembler.lib.msu.edu
        WSGIScriptAlias / /var/www/text-assembler/textassembler/wsgi.py

        <Directory /var/www/text-assembler/textassembler>
                SetHandler wsgi-script
                DirectoryIndex wsgi.py
                Options +ExecCGI
                Require all granted
        </Directory>

        Alias /static/ /var/www/text-assembler/textassembler_web/static/
        <Directory /var/www/text-assembler/textassembler_web/static>
                Options -Indexes
                Require all granted
        </Directory>

        ErrorLog ${APACHE_LOG_DIR}/textassembler-error.log
        CustomLog ${APACHE_LOG_DIR}/textassembler-access.log combined
</VirtualHost>
```

* Set up the services:  
Installing the Text Assembler service to process the queue, zip compression handler, and deletion handler.
```
cp etc/init.d/* /etc/init.d/
sudo chmod +x /etc/init.d/tassembler*
systemctl daemon-reload
systemctl enable tassemblerd
systemctl start tassemblerd
systemctl enable tassemblerzipd
systemctl start tassemblerzipd
systemctl enable tassemblerdeld
systemctl start tassemblerdeld
```

* Set up cron job to update Lexis Nexis sources on a regular basis (`/etc/crontab`)
```
@monthly    root        /var/www/text-assembler/ta_env/bin/python /var/www/text-assembler/manage.py update_sources
```

Applying Updates
----------------
As improvements are made to the application, they will be pushed to the primary branch of this Git repository.
In order to apply changes made, here are the steps you will need to follow:

* Pull the latest code from GitLab
* If any of the .example files changed, compare them with you files to determine if there are changes you need to add.
For example, if the `textassembler.cfg.example` file changes, you will want to compare them to add/remove/change the 
fields indicated so it is up-to-date.
* Run the database migrations to check for any changes: `/var/www/text-assembler/ta_env/bin/python /var/www/text-assembler/manage.py migrate`.
* Restart Apache and the Text Assembler daemons: 
```
systemctl restart apache2
systemctl restart tassemberd
systemctl restart tassemberzipd
systemctl restart tassemberdeld
```

WSK to API Transition
--------------------
This section includes steps for moving over in-progress searches running on a site 
using the existing Lexis Nexis WSK. If this does not apply to you, please skip 
over this section.

* In the existing system, mark the searches as completed so they stop processing.
* Add a README.txt to the top level directory of each of the searches stating 
something along these lines:
```
Processing for this search has been terminated due to the migration away from the LexisNexis WSK system 
on to the new API system. Due to differnces in the interaction with this system, it was not possible 
for the search to simply be restarted on the new system. As a result, these are the downloads that 
have already been obtained from the old WSK system. If you require further information for your 
research, please restart a new search on the new site (https://textassembler.lib.msu.edu).

For any technical questions, contact Megan Schanz (schanzme@msu.edu).

Completed downloading results between: [Start Date Range - Date completed processing up to]
```
* Make sure the Text Assembler processor is not running
```
systemctl stop tassemblerd
```
* Create a new record in the Text Assembler database for the search providng as many of the filters as you can
```
INSERT INTO textassembler_web_searches
() 
VALUES ();
INSERT INTO textassembler_web_searches 
(userid, date_submitted, update_date, query, date_completed, 
num_results_downloaded, num_results_in_search, skip_value, 
date_started_compression, date_completed_compression, 
user_notified, run_time_seconds, date_started, retry_count) 
VALUES
('userid','2019-02-20', NOW(), 'search query', NOW(), 
33840, 33840, 0,
NOW(), NOW(), 
1, 0, '2019-02-20',0);


# Using the search_id created from the previous insert to fill in 
# the following queries
INSERT INTO textassembler_web_filters
(search_id_id, filter_name, filter_value) 
VALUES
(1, 'Date', 'gt 2019-06-10');

INSERT INTO textassembler_web_download_formats
SELECT format_id_id, 1
FROM textassembler_web_available_formats
WHERE format_name = 'HTML';
```

* Compress any incomplete searches in the old system
* Move the searches to the new location with the new naming convention: [STORAGE_LOCATION]/[search_id]/[search_id].zip
* The Text Assembler processor can be restarted again

Technical Overview
------------------
This section breaks down what Text Assembler does behind the scenes.

### Web Application ([code](textassembler_web/views.py))
This is the interface that users interact with which allows them to preview searches to refine them, queue them for full 
download, and then allows the abilit to download their full text results when it has completed processing.

The on-demand searches on the Search page is limited by the number of searches we are allowed to do per minute/hour/day 
within the Lexis Nexis API (the exact numbers depend on your license agreement). If the PREVIEW_FORMAT is set to
FULL_TEXT, then it will also apply the minute/hour/day download limits (but not the time window limitations). When it 
does this, it will actually make 2 API calls because the first will be a regular search which will return the post filters 
for further user refinement and the second call will be a download call to get the full text results.

The My Searches page shows the searches that users have saved. They are given the option to delete searches (which works 
on in-progress searches to cancel them) and to download them once complete. Search results should be stored on a shared 
drive with a mount point on the server as these can take considerable amount of space until they are completed and compressed.

Estimates are given on the Searches and My Searches page to give users an idea of how long searches will potentially take. 
This is calculated based on the limitations we have on the API, given the assumption that we could always download faster than 
the limitations we have. So if we are limited to 1,000 downloads a day and there are 3 other searches in the queue with 
each 5,000 results... it would take a new search with 5,000 results 20 days to complete (5000 * 4 / 1000).

When searches are deleted, it will delete the record from the database as well as removing the files for it on the 
server. It will create a historical record in the `historical_searches` table of the database. This is used 
only for reporting purposes (i.e. to get the number of searches ran over the year, or the number of documents downloaded). 

### Queue Processor (tassemblerd, [code](textassembler_processor/management/commands/process_queue.py))
This is the daemon process that does the bulk of the work. It will continually run on the server checking if there are 
searches in the queue that need results downloaded for them still, and if there are, it will verify that we have available
downloads remaining with the Lexis Nexis API (by counting the number of calls we've made in our log table will all our API calls). 

Assuming we're able to download, it will retrieve the next 10 results for the search, save them to the server, and update the 
search position in the database (using the skip field). If the search is complete (based on the number of results field 
returned from the API), it will mark it as download completed so that the compression processor will pick it up to 
zip the results. 

If downloads were not available, it will wait for a period of time and then re-check again (using database 
calls). 

If there are no items in the queue, it will just wait until there are.


### Compression Processor (tassemblerzipd, [code](textassembler_processor/management/commands/compress_searches.py))
This is the daemon process that will continually check for searches that have had all of their results already downloaded 
and are just waiting for their files to be compressed for the user. 

It will loop continually checking for items to compress. When it find one, it will compress the files into a single zip, 
and then it will remove the original un-compressed files. If configured, it will email the user who initiated the 
search to notify them that it has completed.


### Deletion Processor (tassemblerdeld, [code](textassembler_processor/management/commands/delete_searches.py))
This is the daemon process that checks for searches that are old enough to be deleted. It bases this off of the date the 
compression was completed or the date the search failed (if it is a failed search). The number of months it waits 
before deleting items is set to 3 in the config file by default.

It will delete the files from the server and delete the search record from the database.
