# -*- coding: utf-8 -*-
# vim: set et sts=2:
# pylint: disable-msg=W0311,C0301,C0103,C0111,R0904

#############################################
# !!! Attention !!!
# You now have to comment the last line
# in __init__py, wich starts the functiun
# run() in order to start the tests,
# or it will NOT work
#############################################

import argparse
import ConfigParser
import datetime
import hashlib
import json
import os
import shutil
import sup_process
import StringIO
import time
import unittest

from slapos.runner.utils import (getProfilePath,
                                 getSession, isInstanceRunning,
                                 isSoftwareRunning, startProxy,
                                 isSoftwareReleaseReady,
                                 runSlapgridUntilSuccess, runInstanceWithLock,
                                 getBuildAndRunParams, saveBuildAndRunParams)
from slapos.runner import views
import slapos.slap
from slapos.htpasswd import  HtpasswdFile

import erp5.util.taskdistribution as taskdistribution


#Helpers
def loadJson(response):
  return json.loads(response.data)

def parseArguments():
  """
  Parse arguments for erp5testnode-backed test.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument('--test_result_path',
                      metavar='ERP5_TEST_RESULT_PATH',
                      help='ERP5 relative path of the test result')

  parser.add_argument('--revision',
                      metavar='REVISION',
                      help='Revision of the test_suite')

  parser.add_argument('--test_suite',
                      metavar='TEST_SUITE',
                      help='Name of the test suite')

  parser.add_argument('--test_suite_title',
                      metavar='TEST_SUITE',
                      help='The test suite title')

  parser.add_argument('--test_node_title',
                      metavar='NODE_TITLE',
                      help='Title of the testnode which is running this'
                            'launcher')

  parser.add_argument('--node_quantity', help='Number of parallel tests to run',
                      default=1, type=int)

  parser.add_argument('--master_url',
                      metavar='TEST_SUITE_MASTER_URL',
                      help='Url to connect to the ERP5 Master testsuite taskditributor')

  parser.add_argument('additional_arguments', nargs=argparse.REMAINDER)

  return parser.parse_args()


class Config:
  def __init__(self):
    self.runner_workdir = None
    self.software_root = None
    self.instance_root = None
    self.configuration_file_path = None

  def setConfig(self):
    """
    Set options given by parameters.
    """
    self.configuration_file_path = os.path.abspath(os.environ.get('RUNNER_CONFIG'))

    # Load configuration file
    configuration_parser = ConfigParser.SafeConfigParser()
    configuration_parser.read(self.configuration_file_path)
    # Merges the arguments and configuration

    for section in ("slaprunner", "slapos", "slapproxy", "slapformat",
                    "sshkeys_authority", "gitclient"):
      configuration_dict = dict(configuration_parser.items(section))
      for key in configuration_dict:
        if not getattr(self, key, None):
          setattr(self, key, configuration_dict[key])


class SlaprunnerTestCase(unittest.TestCase):

  def setUp(self):
    """Initialize slapos webrunner here"""
    views.app.config['TESTING'] = True
    self.users = ["slapuser", "slappwd", "slaprunner@nexedi.com", "SlapOS web runner"]
    self.updateUser = ["newslapuser", "newslappwd", "slaprunner@nexedi.com", "SlapOS web runner"]
    self.repo = 'https://lab.nexedi.com/nexedi/slapos.git'
    self.software = "workspace/slapos/software/"  # relative directory fo SR
    self.project = 'slapos'  # Default project name
    self.template = 'template.cfg'
    self.partitionPrefix = 'slappart'
    #create slaprunner configuration
    config = Config()
    config.setConfig()
    # We do not run tests if a user is already set (runner being used)
    if os.path.exists(os.path.join(config.etc_dir, '.users')):
      self.fail(msg="A user is already set, can not start tests")
    workdir = os.path.join(config.runner_workdir, 'project')
    software_link = os.path.join(config.runner_workdir, 'softwareLink')
    views.app.config.update(**config.__dict__)
    #update or create all runner base directory to test_dir

    if not os.path.exists(workdir):
      os.mkdir(workdir)
    if not os.path.exists(software_link):
      os.mkdir(software_link)
    views.app.config.update(
      software_log=config.software_root.rstrip('/') + '.log',
      instance_log=config.instance_root.rstrip('/') + '.log',
      workspace=workdir,
      software_link=software_link,
      instance_profile='instance.cfg',
      software_profile='software.cfg',
      SECRET_KEY="123456",
      PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=31),
      instance_monitoring_url = 'https://[' + config.ipv6_address + ']:9684',
    )
    self.app = views.app.test_client()
    self.app.config = views.app.config
    #Create password recover code
    parser = ConfigParser.ConfigParser()
    parser.read(self.app.config['knowledge0_cfg'])
    self.rcode = parser.get('public', 'recovery-code')
    #Create config.json
    json_file = os.path.join(views.app.config['etc_dir'], 'config.json')
    if not os.path.exists(json_file):
      params = {
        'run_instance' : True,
        'run_software' : True,
        'max_run_instance' : 3,
        'max_run_software' : 2
      }
      open(json_file, "w").write(json.dumps(params))

  def tearDown(self):
    """Remove all test data"""
    project = os.path.join(self.app.config['etc_dir'], '.project')
    users = os.path.join(self.app.config['etc_dir'], '.users')

    #reset tested parameters
    self.updateConfigParameter('autorun', False)
    self.updateConfigParameter('auto_deploy', True)

    if os.path.exists(users):
      os.unlink(users)
    if os.path.exists(project):
      os.unlink(project)
    if os.path.exists(self.app.config['workspace']):
      shutil.rmtree(self.app.config['workspace'])
    if os.path.exists(self.app.config['software_root']):
      shutil.rmtree(self.app.config['software_root'])
    if os.path.exists(self.app.config['instance_root']):
      shutil.rmtree(self.app.config['instance_root'])
    if os.path.exists(self.app.config['software_link']):
      shutil.rmtree(self.app.config['software_link'])
    #Stop process
    sup_process.killRunningProcess(self.app.config, 'slapproxy')
    sup_process.killRunningProcess(self.app.config, 'slapgrid-cp')
    sup_process.killRunningProcess(self.app.config, 'slapgrid-sr')

  def updateConfigParameter(self, parameter, value):
    config_parser = ConfigParser.SafeConfigParser()
    config_parser.read(os.getenv('RUNNER_CONFIG'))
    for section in config_parser.sections():
      if config_parser.has_option(section, parameter):
        config_parser.set(section, parameter, str(value))
    with open(os.getenv('RUNNER_CONFIG'), 'wb') as configfile:
      config_parser.write(configfile)

  def configAccount(self, username, password, email, name, rcode):
    """Helper for configAccount"""
    return self.app.post('/configAccount',
                         data=dict(
                           username=username,
                           password=password,
                           email=email,
                           name=name,
                           rcode=rcode
                         ),
                         follow_redirects=True)

  def setAccount(self):
    """Initialize user account and log user in"""
    response = loadJson(self.configAccount(self.users[0], self.users[1],
                  self.users[2], self.users[3], self.rcode))
    self.assertEqual(response['result'], "")

  def updateAccount(self, newaccount, rcode):
    """Helper for update user account data"""
    return self.app.post('/updateAccount',
                         data=dict(
                           username=newaccount[0],
                           password=newaccount[1],
                           email=newaccount[2],
                           name=newaccount[3],
                           rcode=rcode
                         ),
                         follow_redirects=True)

  def getCurrentSR(self):
   return getProfilePath(self.app.config['etc_dir'],
                              self.app.config['software_profile'])

  def proxyStatus(self, status=True):
    """Helper for testslapproxy status"""
    proxy = sup_process.isRunning(self.app.config, 'slapproxy')
    self.assertEqual(proxy, status)

  def setupProjectFolder(self):
    """Helper to create a project folder as for slapos.git"""
    base = os.path.join(self.app.config['workspace'], 'slapos')
    software = os.path.join(base, 'software')
    os.mkdir(base)
    os.mkdir(software)

  def setupTestSoftware(self):
    """Helper to setup Basic SR for testing purposes"""
    self.setupProjectFolder()
    base = os.path.join(self.app.config['workspace'], 'slapos')
    software = os.path.join(base, 'software')
    testSoftware = os.path.join(software, 'slaprunner-test')
    sr = "[buildout]\n\n"
    sr += "parts = command\n\nunzip = true\nnetworkcache-section = networkcache\n\n"
    sr += "find-links += http://www.nexedi.org/static/packages/source/slapos.buildout/\n\n"
    sr += "[networkcache]\ndownload-cache-url = http://www.shacache.org/shacache"
    sr += "\ndownload-dir-url = http://www.shacache.org/shadir\n\n"
    sr += "[command]\nrecipe = zc.recipe.egg\neggs = plone.recipe.command\n  zc.buildout\n\n"
    os.mkdir(testSoftware)
    open(os.path.join(testSoftware, self.app.config['software_profile']),
         'w').write(sr)
    md5 = hashlib.md5(os.path.join(self.app.config['workspace'],
                                   "slapos/software/slaprunner-test",
                                   self.app.config['software_profile'])
                      ).hexdigest()
    base = os.path.join(self.app.config['software_root'], md5)
    template = os.path.join(base, self.template)
    content = "[buildout]\n"
    content += "parts = \n  create-file\n\n"
    content += "eggs-directory = %s\n" % os.path.join(base, 'eggs')
    content += "develop-eggs-directory = %s\n\n" % os.path.join(base, 'develop-eggs')
    content += "[create-file]\nrecipe = plone.recipe.command\n"
    content += "filename = ${buildout:directory}/etc\n"
    content += "command = mkdir ${:filename} && echo 'simple file' > ${:filename}/testfile\n"
    os.mkdir(self.app.config['software_root'])
    os.mkdir(base)
    open(template, "w").write(content)

  def stopSlapproxy(self):
    """Kill slapproxy process"""
    pass

  def test_configAccount(self):
    """For the first lauch of slaprunner user need do create first account"""
    result = self.configAccount(self.users[0], self.users[1], self.users[2],
                  self.users[3], self.rcode)
    response = loadJson(result)
    self.assertEqual(response['code'], 1)
    account = getSession(self.app.config)
    self.assertEqual(account, self.users)

  def test_updateAccount(self):
    """test Update accound, this needs the user to log in"""
    self.setAccount()
    htpasswd = os.path.join(self.app.config['etc_dir'], '.htpasswd')
    assert self.users[0] in open(htpasswd).read()
    response = loadJson(self.updateAccount(self.updateUser, self.rcode))
    self.assertEqual(response['code'], 1)
    encode = HtpasswdFile(htpasswd, False)
    encode.update(self.updateUser[0], self.updateUser[1])
    assert self.updateUser[0] in open(htpasswd).read()

  def test_startStopProxy(self):
    """Test slapproxy"""
    startProxy(self.app.config)
    self.proxyStatus(True)

  def test_cloneProject(self):
    """Start scenario 1 for deploying SR: Clone a project from git repository"""
    self.setAccount()
    folder = 'workspace/' + self.project
    if os.path.exists(self.app.config['workspace'] + '/' + self.project):
      shutil.rmtree(self.app.config['workspace'] + '/' + self.project)
    data = {
      'repo': self.repo,
      'user': 'Slaprunner test',
      'email': 'slaprunner@nexedi.com',
      'name': folder
    }
    response = loadJson(self.app.post('/cloneRepository', data=data,
                    follow_redirects=True))
    self.assertEqual(response['result'], "")
    # Get realpath of create project
    path_data = dict(file=folder)
    response = loadJson(self.app.post('/getPath', data=path_data,
                    follow_redirects=True))
    self.assertEqual(response['code'], 1)
    realFolder = response['result'].split('#')[0]
    #Check git configuration
    config = open(os.path.join(realFolder, '.git/config')).read()
    assert "slaprunner@nexedi.com" in config and "Slaprunner test" in config

    # Checkout to slaprunner branch, this supposes that branch slaprunner exit
    response = loadJson(self.app.post('/newBranch',
                                      data=dict(
                                        project=folder,
                                        create='0',
                                        name='erp5'
                                      ),
                                      follow_redirects=True))
    self.assertEqual(response['result'], "")

  def test_createSR(self):
    """Scenario 2: Create a new software release"""
    self.setAccount()
    #setup project directory
    self.setupProjectFolder()
    newSoftware = os.path.join(self.software, 'slaprunner-test')
    response = loadJson(self.app.post('/createSoftware',
                                      data=dict(folder=newSoftware),
                                      follow_redirects=True))
    self.assertEqual(response['result'], "")
    currentSR = self.getCurrentSR()
    assert newSoftware in currentSR

  def test_openSR(self):
    """Scenario 3: Open software release"""
    self.test_cloneProject()
    software = os.path.join(self.software, 'helloworld')  # Drupal SR must exist in SR folder
    response = loadJson(self.app.post('/setCurrentProject',
                                      data=dict(path=software),
                                      follow_redirects=True))
    self.assertEqual(response['result'], "")
    currentSR = self.getCurrentSR()
    assert software in currentSR
    self.assertFalse(isInstanceRunning(self.app.config))
    self.assertFalse(isSoftwareRunning(self.app.config))

    # Slapproxy process is supposed to be started
    # newSoftware = os.path.join(self.software, 'slaprunner-test')
    self.proxyStatus(True)
    self.stopSlapproxy()

  def test_runSoftware(self):
    """Scenario 4: CReate empty SR and save software.cfg file
      then run slapgrid-sr
    """
    #Call config account
    #call create software Release
    self.test_createSR()
    newSoftware = self.getCurrentSR()
    softwareRelease = "[buildout]\n\nparts =\n  test-application\n"
    softwareRelease += "#Test download git web repos éè@: utf-8 caracters\n"
    softwareRelease += "[test-application]\nrecipe = hexagonit.recipe.download\n"
    softwareRelease += "url = https://lab.nexedi.com/nexedi/slapos.git\n"
    softwareRelease += "filename = slapos.git\n"
    softwareRelease += "download-only = true\n"
    response = loadJson(self.app.post('/saveFileContent',
                                      data=dict(file=newSoftware,
                                                content=softwareRelease),
                                      follow_redirects=True))
    self.assertEqual(response['result'], "")

    # Compile software and wait until slapgrid ends
    # this is supposed to use current SR
    while self.app.get('/isSRReady').data == "2":
      time.sleep(2)
    self.assertEqual(self.app.get('/isSRReady').data, "1")
    self.assertTrue(os.path.exists(self.app.config['software_root']))
    self.assertTrue(os.path.exists(self.app.config['software_log']))
    assert "test-application" in open(self.app.config['software_log']).read()
    sr_dir = os.listdir(self.app.config['software_root'])
    self.assertEqual(len(sr_dir), 1)
    createdFile = os.path.join(self.app.config['software_root'], sr_dir[0],
                              'parts', 'test-application', 'slapos.git')
    self.assertTrue(os.path.exists(createdFile))
    self.proxyStatus(True)
    self.stopSlapproxy()

  def test_updateInstanceParameter(self):
    """Scenarion 5: Update parameters of current sofware profile"""
    self.setAccount()
    self.setupTestSoftware()
    #Set current projet and run Slapgrid-cp
    software = os.path.join(self.software, 'slaprunner-test')
    response = loadJson(self.app.post('/setCurrentProject',
                                      data=dict(path=software),
                                      follow_redirects=True))
    self.assertEqual(response['result'], "")
    self.proxyStatus(True)
    #Send paramters for the instance
    parameterDict = dict(appname='slaprunnerTest', cacountry='France')
    parameterXml = '<?xml version="1.0" encoding="utf-8"?>\n<instance>'
    parameterXml += '<parameter id="appname">slaprunnerTest</parameter>\n'
    parameterXml += '<parameter id="cacountry">France</parameter>\n</instance>'
    software_type = 'production'
    response = loadJson(self.app.post('/saveParameterXml',
                                      data=dict(parameter=parameterXml,
                                                software_type=software_type),
                                      follow_redirects=True))
    self.assertEqual(response['result'], "")
    slap = slapos.slap.slap()
    slap.initializeConnection(self.app.config['master_url'])
    computer = slap.registerComputer(self.app.config['computer_id'])
    partitionList = computer.getComputerPartitionList()
    self.assertNotEqual(partitionList, [])
    #Assume that the requested partition is partition 0
    slapParameterDict = partitionList[0].getInstanceParameterDict()
    self.assertTrue('appname' in slapParameterDict)
    self.assertTrue('cacountry' in slapParameterDict)
    self.assertEqual(slapParameterDict['appname'], 'slaprunnerTest')
    self.assertEqual(slapParameterDict['cacountry'], 'France')
    self.assertEqual(slapParameterDict['slap_software_type'], 'production')

    #test getParameterXml for webrunner UI
    response = loadJson(self.app.get('/getParameterXml/xml'))
    self.assertEqual(parameterXml, response['result'])
    response = loadJson(self.app.get('/getParameterXml/dict'))
    self.assertEqual(parameterDict, response['result']['instance'])
    self.stopSlapproxy()

  def test_requestInstance(self):
    """Scenarion 6: request software instance"""
    self.test_updateInstanceParameter()
    #run Software profile
    response = loadJson(self.app.post('/runSoftwareProfile',
                                      data=dict(),
                                      follow_redirects=True))
    while self.app.get('/isSRReady').data == "2":
      time.sleep(2)
    self.assertEqual(self.app.get('/isSRReady').data, "1")
    #run instance profile
    response = loadJson(self.app.post('/runInstanceProfile',
                                      data=dict(),
                                      follow_redirects=True))
    self.assertTrue(response['result'])
    # lets some time to the Instance to be deployed
    time.sleep(5)
    #Check that all partitions has been created
    assert "create-file" in open(self.app.config['instance_log']).read()
    for num in range(int(self.app.config['partition_amount'])):
      partition = os.path.join(self.app.config['instance_root'],
                    self.partitionPrefix + str(num))
      self.assertTrue(os.path.exists(partition))

    #Go to partition 0
    instancePath = os.path.join(self.app.config['instance_root'],
                         self.partitionPrefix + '0')
    createdFile = os.path.join(instancePath, 'etc', 'testfile')
    self.assertTrue(os.path.exists(createdFile))
    assert 'simple file' in open(createdFile).read()
    self.proxyStatus(True)
    self.stopSlapproxy()

  def test_safeAutoDeploy(self):
    """Scenario 7: isSRReady won't overwrite the existing
    Sofware Instance if it has been deployed yet"""
    # Test that SR won't be deployed with auto_deploy=False
    self.updateConfigParameter('auto_deploy', False)
    self.updateConfigParameter('autorun', False)
    project = open(os.path.join(self.app.config['etc_dir'],
                  '.project'), "w")
    project.write(self.software + 'slaprunner-test')
    project.close()
    response = isSoftwareReleaseReady(self.app.config)
    self.assertEqual(response, "0")
    # Test if auto_deploy parameter starts the deployment of SR
    self.updateConfigParameter('auto_deploy', True)
    self.setupTestSoftware()
    response = isSoftwareReleaseReady(self.app.config)
    self.assertEqual(response, "2")
    # Test that the new call to isSoftwareReleaseReady
    # doesn't overwrite the previous installed one
    sup_process.killRunningProcess(self.app.config, 'slapgrid-sr')
    completed_path = os.path.join(self.app.config['runner_workdir'],
        'softwareLink', 'slaprunner-test', '.completed')
    completed_text = ".completed file: test"
    completed = open(completed_path, "w")
    completed.write(completed_text)
    completed.close()
    response = isSoftwareReleaseReady(self.app.config)
    self.assertEqual(response, "1")
    assert completed_text in open(completed_path).read()

  def test_maximumRunOfSlapgrid(self):
    """Scenario 8: runSlapgridUntilSucces run until a defined maximum of time
    slapgrid-sr and slapgrid-cp if it fails. It can also run only one or both
    of them if it is defined so
    We directly calls runSlapgridUntilSuccess, because we want
    to test the return code of the function"""
    # Installs a wrong buildout which will fail
    MAX_RUN_SOFTWARE = getBuildAndRunParams(self.app.config)['max_run_software']
    MAX_RUN_INSTANCE = getBuildAndRunParams(self.app.config)['max_run_instance']
    self.test_createSR()
    newSoftware = self.getCurrentSR()
    softwareRelease = "[buildout]\n\nparts =\n  test-application\n"
    softwareRelease += "#Test download git web repos éè@: utf-8 caracters\n"
    softwareRelease += "[test-application]\nrecipe = slapos.cookbook:mkdirectory\n"
    softwareRelease += "test = /root/test\n"
    response = loadJson(self.app.post('/saveFileContent',
                                      data=dict(file=newSoftware,
                                                content=softwareRelease),
                                      follow_redirects=True))
    response = runSlapgridUntilSuccess(self.app.config, 'software')
    self.assertEqual(response, MAX_RUN_SOFTWARE)
    # clean folders for other tests
    workdir = os.path.join(self.app.config['runner_workdir'], 'project')
    git_repo = os.path.join(workdir, 'slapos')
    if os.path.exists(git_repo):
      shutil.rmtree(git_repo)
    # Installs a software which deploys, but fails while instanciating
    # preparation
    base = os.path.join(self.app.config['workspace'], 'slapos')
    software = os.path.join(base, 'software')
    testSoftware = os.path.join(software, 'slaprunner-test')
    if not os.path.exists(testSoftware):
      os.makedirs(testSoftware)
    software_cfg = os.path.join(testSoftware, 'software.cfg')
    instance_cfg = os.path.join(testSoftware, 'instance.cfg')
    # software.cfg
    softwareRelease = "[buildout]\n\nparts =\n  failing-template\n\n"
    softwareRelease += "[failing-template]\nrecipe = hexagonit.recipe.download\n"
    softwareRelease += "url = %s\n" % (instance_cfg)
    softwareRelease += "destination = ${buildout:directory}\n"
    softwareRelease += "download-only = true\n"
    open(software_cfg, 'w+').write(softwareRelease)
    # instance.cfg
    content = "[buildout]\n\nparts =\n fail\n"
    content += "[fail]\nrecipe=plone.recipe.command\n"
    content += "command = exit 1"
    open(instance_cfg, 'w+').write(content)
    project = open(os.path.join(self.app.config['etc_dir'],
                  '.project'), "w")
    project.write(self.software + 'slaprunner-test')
    project.close()
    # Build and Run
    parameters = getBuildAndRunParams(self.app.config)
    parameters['run_instance'] = False
    saveBuildAndRunParams(self.app.config, parameters)
    response = runSlapgridUntilSuccess(self.app.config, 'software')
    self.assertEqual(response, 1)
    parameters['run_instance'] = True
    saveBuildAndRunParams(self.app.config, parameters)
    response = runSlapgridUntilSuccess(self.app.config, 'software')
    self.assertEqual(response, (1, MAX_RUN_INSTANCE))

  def test_slaveInstanceDeployment(self):
    """
    In order to test both slapproxy and core features of
    slaprunner, will install special Software Release
    into the current webrunner and fetch its instance
    parameters once deployed.
    """
    # XXX: This test should NOT be a unit test but should be run
    # by a Test Agent running against a slapproxy.

    # Deploy "test-slave-instance-deployment" Software Release
    self.test_cloneProject()
    software = os.path.join(self.software, 'test-slave-instance-deployment')

    # Checkout to master branch
    response = loadJson(self.app.post('/newBranch',
                                      data=dict(
                                        project=self.software,
                                        create='0',
                                        name='master'
                                      ),
                                      follow_redirects=True)).get(u'code')
    self.assertEqual(response, 1)
    response = loadJson(self.app.post('/setCurrentProject',
                                      data=dict(path=software),
                                      follow_redirects=True)).get(u'code')
    self.assertEqual(response, 1)

    response = loadJson(self.app.post('/saveParameterXml',
                                      data=dict(parameter='<?xml version="1.0" encoding="utf-8"?>\n<instance/>',
                                                software_type='default'),
                                      follow_redirects=True))

    while self.app.get('/isSRReady').data == "2":
      time.sleep(2)
    self.assertEqual(self.app.get('/isSRReady').data, "1")

    # Run instance deployment 3 times
    runInstanceWithLock(self.app.config)
    runInstanceWithLock(self.app.config)
    result = runInstanceWithLock(self.app.config)
    # result is True if returncode is 0 (i.e "deployed and promise passed")
    self.assertTrue(result)

    self.proxyStatus(True)
    self.stopSlapproxy()

  def test_dynamicParametersReading(self):
    """Test if the value of a parameter can change in the flask application
    only by changing the value of slapos.cfg config file. This can happen when
    slapgrid processes the webrunner's partition.
    """
    config_file = os.path.join(self.app.config['etc_dir'], 'slapos-test.cfg')
    runner_config_old = os.environ['RUNNER_CONFIG']
    os.environ['RUNNER_CONFIG'] = config_file
    open(config_file, 'w').write("[section]\nvar=value")
    config = self.app.config
    self.assertEqual(config['var'], "value")
    open(config_file, 'w').write("[section]\nvar=value_changed")
    self.assertEqual(config['var'], "value_changed")
    # cleanup
    os.environ['RUNNER_CONFIG'] = runner_config_old


def main():
  """
  Function meant to be run by erp5testnode.
  """
  args = parseArguments()
  master = taskdistribution.TaskDistributionTool(args.master_url)
  test_suite_title = args.test_suite_title or args.test_suite
  revision = args.revision

  test_result = master.createTestResult(revision, [test_suite_title],
    args.test_node_title, True, test_suite_title, 'foo')
    #args.project_title)
  test_line = test_result.start()

  start_time = time.time()

  stderr = StringIO.StringIO()

  suite = unittest.TestLoader().loadTestsFromTestCase(SlaprunnerTestCase)
  test_result = unittest.TextTestRunner(verbosity=2, stream=stderr).run(suite)

  test_duration = time.time() - start_time
  test_line.stop(stderr=stderr.getvalue(),
                  test_count=test_result.testsRun,
                  error_count=len(test_result.errors),
                  failure_count=len(test_result.failures) + len(test_result.unexpectedSuccesses),
                  skip_count=len(test_result.skipped),
                  duration=test_duration)

def runStandaloneUnitTest():
  """
  Run unit tests without erp5testnode."
  """
  unittest.main(module=__name__)
