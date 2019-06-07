Text Assembler
--------------



Install & Setup
---------------
sudo aptitude install python3
sudo apt install python3-pip
sudo pip3 install Django
sudo aptitude install libapache2-mod-wsgi-py3
python3.6 -m venv ta_env
source ta_env/bin/activate
pip install -r requirements.txt
deactivate
vim /etc/apache2/envvars
```
export LANG='en_US.UTF-8'
export LC_ALL='en_US.UTF-8'
```

Copy all of the .example files (find . -name '*.example') and make necessary changes.

Running commands from cron with virtualenv
ta_env/bin/python manage.py update_sources

Installing the Text Assembler service to process the queue:
```
cp init.d/textassemblerd /etc/init.d/
cp init.d/textassemblerzipd /etc/init.d/
systemctl daemon-reload
systemctl enable textassemblerd
systemctl start textassemblerd
systemctl enable textassemblerzipd
systemctl start textassemblerzipd
```
TODO -- make sure no more than once instance of the service is running at a time

Need Gluster version to match version on gluster share (gluster --version)
```
sudo add-apt-repository ppa:gluster/glusterfs-5
sudo apt-get update
sudo aptitude install glusterfs-client
```

cifs mount 
```
sudo apt install cifs-utils
```

Notes
--------------


TODO
-------
* Authentication
* Send the 'save' options back to the form in the event of failure to repopulate the form
    * what should the screen show when the save is sucessful? cleared form?
* Contact LN about multiple values not allowed in Language and Source fields for search
* Show time remaining until next search available for when we run out of them for UI searches
* If the API returns an error, distinguish that in the error message so users know it was from LN 
  and not Text Assembler
* handle failed searches in My Searches page
* Lint (pylint3 --max-line-length=160 --load-plugins=pylint_django --extension-pkg-whitelist=lxml)
* Unit Tests
* Accessibility scan

Nice to Have
-------------
* Sortable My Searches grid
* email settings, email domain to notify users. ex: EMAIL_DOMAIN = msu.edu, will email to [user]@msu.edu
    * if not set, then emails will not be sent to users
* Display / calculate the estimated completion time of searches (search page and my searches page)
