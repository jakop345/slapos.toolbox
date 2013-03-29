# -*- coding: utf-8 -*-
# vim: set et sts=2:
# pylint: disable-msg=W0311,C0301,C0103,C0111,R0904

import argparse
import ConfigParser
import datetime
import json
import os
import shutil
import time
import unittest
import hashlib

from slapos.runner.utils import (getProfilePath, getSession, isInstanceRunning,
                                 isSoftwareRunning, startProxy)
from slapos.runner.process import killRunningProcess, isRunning
from slapos.runner import views
import slapos.slap

#Helpers
def loadJson(response):
  return json.loads(response.data)


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
    self.configuration_file_path = os.path.abspath(os.environ.get('CONFIG_FILE_PATH'))

    # Load configuration file
    configuration_parser = ConfigParser.SafeConfigParser()
    configuration_parser.read(self.configuration_file_path)
    # Merges the arguments and configuration

    for section in ("slaprunner", "slapos", "slapproxy", "slapformat",
                    "sshkeys_authority", "gitclient", "cloud9_IDE"):
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
    self.rcode = "41bf2657"
    self.repo = 'http://git.erp5.org/repos/slapos.git'
    self.software = "workspace/slapos/software/" #relative directory fo SR
    self.project = 'slapos' #Default project name
    self.template = 'template.cfg'
    self.partitionPrefix = 'slappart'
    self.slaposBuildout = "1.6.0-dev-SlapOS-010"
    #create slaprunner configuration
    config = Config()
    config.setConfig()
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
      workspace = workdir,
      software_link=software_link,
      instance_profile='instance.cfg',
      software_profile='software.cfg',
      SECRET_KEY="123456",
      PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=31),
    )
    self.app = views.app.test_client()
    self.app.config = views.app.config
    #Create password recover code
    rpwd = open(os.path.join(views.app.config['etc_dir'], '.rcode'), 'w')
    rpwd.write(self.rcode)
    rpwd.close()

  def tearDown(self):
    """Remove all test data"""
    os.unlink(os.path.join(self.app.config['etc_dir'], '.rcode'))
    project = os.path.join(self.app.config['etc_dir'], '.project')
    users = os.path.join(self.app.config['etc_dir'], '.users')

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
    self.logout()
    #Stop process
    killRunningProcess('slapproxy', recursive=True)
    killRunningProcess('slapgrid-cp', recursive=True)
    killRunningProcess('slapgrid-sr', recursive=True)

  def configAccount(self, username, password, email, name, rcode):
    """Helper for configAccount"""
    return self.app.post('/configAccount', data=dict(
            username=username,
            password=password,
            email=email,
            name=name,
            rcode=rcode
          ), follow_redirects=True)

  def login(self, username, password):
    """Helper for Login method"""
    return self.app.post('/doLogin', data=dict(
            clogin=username,
            cpwd=password
          ), follow_redirects=True)

  def setAccount(self):
    """Initialize user account and log user in"""
    response = loadJson(self.configAccount(self.users[0], self.users[1],
                  self.users[2], self.users[3], self.rcode))
    response2 = loadJson(self.login(self.users[0], self.users[1]))
    self.assertEqual(response['result'], "")
    self.assertEqual(response2['result'], "")

  def logout(self):
    """Helper for Logout current user"""
    return self.app.get('/dologout', follow_redirects=True)

  def updateAccount(self, newaccount, rcode):
    """Helper for update user account data"""
    return self.app.post('/updateAccount', data=dict(
            username=newaccount[0],
            password=newaccount[1],
            email=newaccount[2],
            name=newaccount[3],
            rcode=rcode
          ), follow_redirects=True)

  def getCurrentSR(self):
   return getProfilePath(self.app.config['etc_dir'],
                              self.app.config['software_profile'])

  def proxyStatus(self, status=True, sleep_time=0):
    """Helper for testslapproxy status"""
    proxy = isRunning('slapproxy')
    if proxy != status and sleep_time != 0:
      time.sleep(sleep_time)
      proxy = isRunning('slapproxy')
    self.assertEqual(proxy, status)

  def setupProjectFolder(self, withSoftware=False):
    """Helper for create a project folder as for slapos.git"""
    base = os.path.join(self.app.config['workspace'], 'slapos')
    software = os.path.join(base, 'software')
    os.mkdir(base)
    os.mkdir(software)
    if withSoftware:
      testSoftware = os.path.join(software, 'slaprunner-test')
      sr = "[buildout]\n\n"
      sr += "parts = command\n\nunzip = true\nnetworkcache-section = networkcache\n\n"
      sr += "find-links += http://www.nexedi.org/static/packages/source/slapos.buildout/\n\n"
      sr += "[networkcache]\ndownload-cache-url = http://www.shacache.org/shacache"
      sr += "\ndownload-dir-url = http://www.shacache.org/shadir\n\n"
      sr += "[command]\nrecipe = zc.recipe.egg\neggs = plone.recipe.command\n\n"
      sr += "[versions]\nzc.buildout = %s\n" % self.slaposBuildout
      os.mkdir(testSoftware)
      open(os.path.join(testSoftware, self.app.config['software_profile']),
                          'w').write(sr)

  def setupSoftwareFolder(self):
    """Helper for setup compiled software release dir"""
    self.setupProjectFolder(withSoftware=True)
    md5 = hashlib.md5(os.path.join(self.app.config['workspace'],
        "slapos/software/slaprunner-test", self.app.config['software_profile'])
      ).hexdigest()
    base = os.path.join(self.app.config['software_root'], md5)
    template = os.path.join(base, self.template)
    content = "[buildout]\n"
    content += "parts = \n  create-file\n\n"
    content += "eggs-directory = %s\n" % os.path.join(base, 'eggs')
    content += "develop-eggs-directory = %s\n\n"  % os.path.join(base, 'develop-eggs')
    content += "[create-file]\nrecipe = plone.recipe.command\n"
    content += "filename = ${buildout:directory}/etc\n"
    content += "command = mkdir ${:filename} && echo 'simple file' > ${:filename}/testfile\n"
    os.mkdir(self.app.config['software_root'])
    os.mkdir(base)
    open(template, "w").write(content)

  def stopSlapproxy(self):
    """Kill slapproxy process"""
    killRunningProcess('slapproxy', recursive=True)


  #Begin test case here
  def test_wrong_login(self):
    """Test Login user before create session. This should return error value"""
    response = self.login(self.users[0], self.users[1])
    #redirect to config account page
    assert "<h2 class='title'>Your personal informations</h2><br/>" in response.data

  def test_configAccount(self):
    """For the first lauch of slaprunner user need do create first account"""
    result = self.configAccount(self.users[0], self.users[1], self.users[2],
                  self.users[3], self.rcode)
    response = loadJson(result)
    self.assertEqual(response['code'], 1)
    account = getSession(self.app.config)
    self.assertEqual(account, self.users)

  def test_login_logout(self):
    """test login with good and wrong values, test logout"""
    response = loadJson(self.configAccount(self.users[0], self.users[1],
                  self.users[2], self.users[3], self.rcode))
    self.assertEqual(response['result'], "")
    result = loadJson(self.login(self.users[0], "wrongpwd"))
    self.assertEqual(result['result'], "Login or password is incorrect, please check it!")
    resultwr = loadJson(self.login("wronglogin", "wrongpwd"))
    self.assertEqual(resultwr['result'], "Login or password is incorrect, please check it!")
    #try now with true values
    resultlg = loadJson(self.login(self.users[0], self.users[1]))
    self.assertEqual(resultlg['result'], "")
    #after login test logout
    result = self.logout()
    assert "<h2>Login to Slapos Web Runner</h2>" in result.data

  def test_updateAccount(self):
    """test Update accound, this need user to loging in"""
    self.setAccount()
    response = loadJson(self.updateAccount(self.updateUser, self.rcode))
    self.assertEqual(response['code'], 1)
    result = self.logout()
    assert "<h2>Login to Slapos Web Runner</h2>" in result.data
    #retry login with new values
    response = loadJson(self.login(self.updateUser[0], self.updateUser[1]))
    self.assertEqual(response['result'], "")
    #log out now!
    self.logout()

  def test_startProxy(self):
    """Test slapproxy"""
    self.proxyStatus(False)
    startProxy(self.app.config)
    self.proxyStatus(True)
    self.stopSlapproxy()
    self.proxyStatus(False, sleep_time=1)

  def test_cloneProject(self):
    """Start scenario 1 for deploying SR: Clone a project from git repository"""
    self.setAccount()
    folder = 'workspace/' + self.project
    data = {"repo":self.repo, "user":'Slaprunner test',
          "email":'slaprunner@nexedi.com', "name":folder}
    response = loadJson(self.app.post('/cloneRepository', data=data,
                    follow_redirects=True))
    self.assertEqual(response['result'], "")
    #Get realpath of create project
    path_data = dict(file=folder)
    response = loadJson(self.app.post('/getPath', data=path_data,
                    follow_redirects=True))
    self.assertEqual(response['code'], 1)
    realFolder = response['result'].split('#')[0]
    #Check git configuration
    config = open(os.path.join(realFolder, '.git/config'), 'r').read()
    assert "slaprunner@nexedi.com" in config and "Slaprunner test" in config
    #Checkout to slaprunner branch, this supose that branch slaprunner exit
    response = loadJson(self.app.post('/newBranch', data=dict(
                    project=folder,
                    create='0',
                    name='slaprunner'),
                    follow_redirects=True))
    self.assertEqual(response['result'], "")
    self.logout()

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
    self.logout()

  def test_openSR(self):
    """Scenario 3: Open software release"""
    self.test_cloneProject()
    #Login
    self.login(self.users[0], self.users[1])
    software = os.path.join(self.software, 'drupal') #Drupal SR must exist in SR folder
    response = loadJson(self.app.post('/setCurrentProject',
                    data=dict(path=software),
                    follow_redirects=True))
    self.assertEqual(response['result'], "")
    currentSR = self.getCurrentSR()
    assert software in currentSR
    self.assertFalse(isInstanceRunning(self.app.config))
    self.assertFalse(isSoftwareRunning(self.app.config))
    #Slapproxy process is supose to be started
    #newSoftware = os.path.join(self.software, 'slaprunner-test')
    self.proxyStatus(True)
    self.stopSlapproxy()
    self.logout()

  def test_runSoftware(self):
    """Scenario 4: CReate empty SR and save software.cfg file
      then run slapgrid-sr
    """
    #Call config account
    #call create software Release
    self.test_createSR()
    #Login
    self.login(self.users[0], self.users[1])
    newSoftware = self.getCurrentSR()
    softwareRelease = "[buildout]\n\nparts =\n  test-application\n"
    softwareRelease += "#Test download git web repos éè@: utf-8 caracters\n"
    softwareRelease += "[test-application]\nrecipe = hexagonit.recipe.download\n"
    softwareRelease += "url = http://git.erp5.org/gitweb/slapos.git\n"
    softwareRelease += "filename = slapos.git\n"
    softwareRelease += "download-only = true\n"
    response = loadJson(self.app.post('/saveFileContent',
                    data=dict(file=newSoftware,
                    content=softwareRelease),
                    follow_redirects=True))
    self.assertEqual(response['result'], "")
    #Compile software and wait until slapgrid it end
    #this is supose to use curent SR
    response = loadJson(self.app.post('/runSoftwareProfile',
                    data=dict(),
                    follow_redirects=True))
    self.assertTrue(response['result'])
    self.assertTrue(os.path.exists(self.app.config['software_root']))
    self.assertTrue(os.path.exists(self.app.config['software_log']))
    assert "test-application" in open(self.app.config['software_log'], 'r').read()
    sr_dir = os.listdir(self.app.config['software_root'])
    self.assertEqual(len(sr_dir), 1)
    createdFile = os.path.join(self.app.config['software_root'], sr_dir[0],
                              'parts', 'test-application', 'slapos.git')
    self.assertTrue(os.path.exists(createdFile))
    self.proxyStatus(True)
    self.stopSlapproxy()
    self.logout()

  def test_updateInstanceParameter(self):
    """Scenarion 5: Update parameters of current sofware profile"""
    self.setAccount()
    self.setupSoftwareFolder()
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
    self.assertTrue(slapParameterDict.has_key('appname'))
    self.assertTrue(slapParameterDict.has_key('cacountry'))
    self.assertEqual(slapParameterDict['appname'], 'slaprunnerTest')
    self.assertEqual(slapParameterDict['cacountry'], 'France')
    self.assertEqual(slapParameterDict['slap_software_type'], 'production')

    #test getParameterXml for webrunner UI
    response = loadJson(self.app.get('/getParameterXml/xml'))
    self.assertEqual(parameterXml, response['result'])
    response = loadJson(self.app.get('/getParameterXml/dict'))
    self.assertEqual(parameterDict, response['result']['instance'])
    self.stopSlapproxy()
    self.logout()

  def test_requestInstance(self):
    """Scenarion 6: request software instance"""
    self.test_updateInstanceParameter()
    #Login
    self.login(self.users[0], self.users[1])
    self.proxyStatus(False, sleep_time=1)
    #run Software profile
    response = loadJson(self.app.post('/runSoftwareProfile',
                    data=dict(),
                    follow_redirects=True))
    self.assertTrue(response['result'])
    #run instance profile
    response = loadJson(self.app.post('/runInstanceProfile',
                    data=dict(),
                    follow_redirects=True))
    self.assertTrue(response['result'])
    #Check that all partitions has been created
    assert "create-file" in open(self.app.config['instance_log'], 'r').read()
    instanceDir = os.listdir(self.app.config['instance_root'])
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
    self.logout()

def main():
  # Empty parser for now - so that erp5testnode is happy when doing --help
  parser = argparse.ArgumentParser()
  parser.parse_args()
  unittest.main(module=__name__)

if __name__ == '__main__':
  main()