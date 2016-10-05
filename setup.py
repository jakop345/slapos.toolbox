from setuptools import setup, find_packages
import glob
import os

version = '0.60'
name = 'slapos.toolbox'
long_description = open("README.rst").read() + "\n"

for f in sorted(glob.glob(os.path.join('slapos', 'README.*.rst'))):
  long_description += '\n' + open(f).read() + '\n'

long_description += open("CHANGES.txt").read() + "\n"

# Provide a way to install additional requirements
additional_install_requires = []
try:
  import argparse
except ImportError:
  additional_install_requires.append('argparse')

setup(name=name,
      version=version,
      description="SlapOS toolbox.",
      long_description=long_description,
      classifiers=[
          "Programming Language :: Python",
        ],
      keywords='slapos toolbox',
      license='GPLv3',
      namespace_packages=['slapos'],
      packages=find_packages(),
      include_package_data=True,
      install_requires=[
        'Flask', # needed by servers
        'atomize', # needed by pubsub
        'feedparser', # needed by pubsub
        'apache_libcloud>=0.4.0', # needed by cloudmgr
        'lockfile', # used by equeue
        'lxml', # needed for xml parsing
        'paramiko', # needed by cloudmgr
        'psutil', # needed for playing with processes in portable way
        'setuptools', # namespaces
        'slapos.core', # as it provides library for slap
        'xml_marshaller', # needed to dump information
        'GitPython', #needed for git manipulation into slaprunner
        'passlib',
        'netifaces',
        'erp5.util',
        'PyRSS2Gen',
        'dnspython',
      ] + additional_install_requires,
      extras_require = {
        'lampconfigure':  ["mysqlclient"], #needed for MySQL Database access
        'zodbpack': ['ZODB3'], # needed to play with ZODB
        'flask_auth' : ["Flask-Auth"],
        'networkbench' : ['pycurl'], 
        'check_web_page_http_cache_hit' : ['pycurl'], # needed for check_web_page_http_cache_hit module
      },
      tests_require = [
        'mock',
      ],
      zip_safe=False, # proxy depends on Flask, which has issues with
                      # accessing templates
      entry_points={
        'console_scripts': [
          'agent = slapos.agent.agent:main',
          'check-web-page-http-cache-hit = slapos.promise.check_web_page_http_cache_hit:main',
          'check-feed-as-promise = slapos.checkfeedaspromise:main',
          'clouddestroy = slapos.cloudmgr.destroy:main',
          'cloudgetprivatekey = slapos.cloudmgr.getprivatekey:main',
          'cloudgetpubliciplist = slapos.cloudmgr.getpubliciplist:main',
          'cloudlist = slapos.cloudmgr.list:main',
          'cloudmgr = slapos.cloudmgr.cloudmgr:main',
          'cloudstart = slapos.cloudmgr.start:main',
          'cloudstop = slapos.cloudmgr.stop:main',
          'equeue = slapos.equeue:main',
          'generatefeed = slapos.generatefeed:main',
          'htpasswd = slapos.htpasswd:main',
          'is-local-tcp-port-opened = slapos.promise.is_local_tcp_port_opened:main',
          'is-process-older-than-dependency-set = slapos.promise.is_process_older_than_dependency_set:main',
          'killpidfromfile = slapos.systool:killpidfromfile', # BBB
          'monitor.bootstrap = slapos.monitor.monitor:main',
          'monitor.collect = slapos.monitor.collect:main',
          'monitor.runpromise = slapos.monitor.runpromise:main',
          'monitor.genstatus = slapos.monitor.globalstate:main',
          'monitor.genrss = slapos.monitor.status2rss:main',
          'monitor.configwrite = slapos.monitor.monitor_config_write:main',
          'runResiliencyUnitTestTestNode = slapos.resiliencytest:runUnitTest',
          'runResiliencyScalabilityTestNode = slapos.resiliencytest:runResiliencyTest',
          'runStandaloneResiliencyTest = slapos.resiliencytest:runStandaloneResiliencyTest',
          'lampconfigure = slapos.lamp:run [lampconfigure]',
          'onetimedownload = slapos.onetimedownload:main',
          'onetimeupload = slapos.onetimeupload:main',
          'pubsubnotifier = slapos.pubsub.notifier:main',
          'pubsubserver = slapos.pubsub:main',
          'qemu-qmp-client = slapos.qemuqmpclient:main',
          'rdiffbackup.genstatrss = slapos.resilient.rdiffBackupStat2RSS:main',
          'slapos-kill = slapos.systool:kill',
          'slaprunnertest = slapos.runner.runnertest:main',
          'slaprunnerteststandalone = slapos.runner.runnertest:runStandaloneUnitTest',
          'zodbpack = slapos.zodbpack:run [zodbpack]',
          'networkbench = slapos.networkbench:main',
          'cachechecker = slapos.cachechecker:web_checker_utility'
        ]
      },
      test_suite='slapos.test',
    )
