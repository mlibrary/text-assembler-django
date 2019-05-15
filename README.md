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

Notes
--------------


UI TODO
-------
* Authentication
* Send the 'save' options back to the form in the event of failure to repopulate the form
    * what should the screen show when the save is sucessful? cleared form?
* Fix issue with filters where if there are multiple filter fields and multiple values for the
  same field, it fails.
    * Ex: 1 lang filter and 2 year filters will fail, but 2 year filters alone is fine.
    * see TODO in filters.py for error details
