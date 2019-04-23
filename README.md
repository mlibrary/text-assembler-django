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

Running commands from cron with virtualenv
ta_env/bin/python manage.py update_sources

Notes
--------------
* API return 429 when too many requests are being sent, and even gives information on limits remaining/used
    * still have checks locally to limit that, but can be a special handling
