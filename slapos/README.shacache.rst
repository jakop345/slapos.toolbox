shacache
========

The network cache server is a NoSQL storage with a REST API.


How does it works
-----------------

::

                          _______________
                         /               \
                         |               |
                  ------>| NETWORKCACHED |
                  |  ----|               |<-----
                  |  |   \_______________/     |
        GET /key  |  |                         |
                  |  | File                    | PUT / <- data
                __|__v______             ______|_____
               |            |           |            |
               |   Client   |           |   Client   |
               |____________|           |____________|


Basically, the networkcached archives the files through HTTP PUT method.
When a client want to download the file it just need to provide the key
value and the server will send a response with the file data.

::

  API:
   PUT / : 
     parameter: file uploaded 
     Used to upload/modify an entry

   GET /<key>
     Return raw content
     Raise HTTP error (404) if key does not exist


Installation
------------

::

  $ python2.6 setup.py install

Now it is time to create the 'networkcached.conf' file in /etc/networkcached.conf
directory, using your preferred text editor (gedit, kate, vim.).
Follow text shall be put in this file::

  [networkcached]
  host = 127.0.0.1
  port = 5001
  cache_base_folder = /var/cache/networkcached/

Run the server::

  # networkcached networkcached.conf


Setup Develoment Environment
----------------------------

::

  $ mkdir -p ~/networkcached/downloads
  $ cd ~/networkcached

Now it is time to create 'buildout.cfg' file in ~/networkcached directory,
using your preferred text editor (gedit, kate, vim.).
Follow text shall be put in this file::

  [buildout]
  extensions = mr.developer
  auto-checkout = slapos.tool.networkcached
  download-cache = /nexedi/buildout-networkcached/downloads
  eggs-directory = /nexedi/buildout-networkcached/eggs

  parts =
   networkcached

  [sources]
  slapos.tool.networkcached = svn https://svn.erp5.org/repos/vifib/trunk/utils/slapos.tool.networkcached

  [networkcached]
  recipe = zc.recipe.egg
  eggs = 
    slapos.tool.networkcached

Now you bootstrap the buildout::

  $ python -S -c 'import urllib;print urllib.urlopen(\
       "http://svn.zope.org/*checkout*/zc.buildout/trunk/bootstrap/bootstrap.py"\
       ).read()' | python -S -

Run the buildout::

  $ bin/buildout -v

Now it is time to create the 'networkcached.conf' file in ~/networkcached
directory, using your preferred text editor (gedit, kate, vim.).
Follow text shall be put in this file::

  [networkcached]
  host = 127.0.0.1
  port = 5001
  cache_base_folder = ~/networkcached/networkcached-database

Now you can start your networkcached server:
$ bin/networkcached networkcached.conf
or 
$ bin/networkcached -d networkcached-database -a 127.0.0.1 -p 5002
