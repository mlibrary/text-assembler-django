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
TODO - set to add to crontab to start services on boot


Notes
--------------
* Run `pip freeze > requirements.txt` to update the pip packages required
* To lint, run `pylint3 --max-line-length=160 --load-plugins=pylint_django --extension-pkg-whitelist=lxml textassembler_web`

* Demo site: https://solutions.nexis.com/wsapi/demo-site

TODO
-------
* Add in code for cleaned TXT format option
* Contact LN about multiple values not allowed in Language and Source fields for search
* Finalize exact run limitation times and amounts

* Accessibility scan
* Write setup instructions
* Plan for migrating existing searches to new system (completed or in progress)

Nice to Have
-------------
* Unit Tests
* Lint
* Sortable My Searches grid
* Select sort order of results
* email settings, email domain to notify users. ex: EMAIL_DOMAIN = msu.edu, will email to [user]@msu.edu
    * if not set, then emails will not be sent to users
* Display / calculate the estimated completion time of searches (search page and my searches page)
