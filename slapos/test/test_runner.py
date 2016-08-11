import mock
import os
import string
import random
import supervisor
import thread
import unittest


import slapos.runner.utils as runner_utils

import sys
sys.modules['slapos.runner.utils'].sup_process = mock.MagicMock()


class TestRunnerBackEnd(unittest.TestCase):
  def setUp(self):
    self.sup_process = runner_utils.sup_process
    self.sup_process.reset_mock()
    runner_utils.open = mock.mock_open()

  def tearDown(self):
    htpasswd_file = os.path.join(*(os.getcwd(), '.htpasswd'))
    if os.path.exists(htpasswd_file):
      os.remove(htpasswd_file)

  def _startSupervisord(self):
    cwd = os.getcwd()
    supervisord_config_file = os.path.join(cwd, 'supervisord.conf')
    open(supervisord_config_file, 'w').write("""
    """)
    supervisord = supervisor.supervisord.Supervisord('-c', supervisord_config_file)
    thread.start_new_thread()

  def test_UserCanLoginAndUpdateCredentials(self):
    """
    * Create a user with createNewUser
    * Tests user can login with checkUserCredential
    * Updates user password updateUserCredential
    * Checks user can login with new credentials
    """
    def generate_password():
      return "".join(random.sample( \
        string.ascii_letters + string.digits + string.punctuation, 20))

    config = {'etc_dir': os.getcwd()}
    login = "admin"
    password = generate_password()
    self.assertTrue(runner_utils.createNewUser(config, login, password))
    self.assertTrue(runner_utils.checkUserCredential(config, login, password))

    new_password = generate_password()
    self.assertNotEqual(password, new_password)
    runner_utils.updateUserCredential(config, login, new_password)
    self.assertTrue(runner_utils.checkUserCredential(config, login, new_password))

  @mock.patch('os.path.exists')
  def test_getCurrentSoftwareReleaseProfile(self, mock_path_exists):
    """
    * Mock a .project file
    * Tests that getCurrentSoftwareReleaseProfile returns an absolute path
    """
    cwd = os.getcwd()

    # If .project file doesn't exist, then getCurrentSoftwareReleaseProfile
    # returns an empty string
    config = {'etc_dir': os.path.join(cwd, 'etc'),
              'workspace': os.path.join(cwd, 'srv', 'runner'),
              'software_profile': 'software.cfg'}

    profile = runner_utils.getCurrentSoftwareReleaseProfile(config)
    self.assertEqual(profile, "")

    # If .project points to a SR that doesn't exist, returns empty string
    runner_utils.open = mock.mock_open(read_data="workspace/fake/path/")
    mock_path_exists.return_value = False
    profile = runner_utils.getCurrentSoftwareReleaseProfile(config)
    self.assertEqual(profile, "")

    # If software_profile exists, getCurrentSoftwareReleaseProfile should
    # return its absolute path
    runner_utils.open = mock.mock_open(read_data = "workspace/project/software/")
    mock_path_exists.return_value = True
    profile = runner_utils.getCurrentSoftwareReleaseProfile(config)
    self.assertEqual(profile, os.path.join(config['workspace'], 'project',
        'software', config['software_profile']))

  @mock.patch('os.mkdir')
  @mock.patch('slapos.runner.utils.updateProxy')
  @mock.patch('slapos.runner.utils.config_SR_folder')
  def _runSlapgridWithLockMakesCorrectCallsToSupervisord(self,
                                                         run_slapgrid_function,
                                                         process_name,
                                                         mock_configSRFolder,
                                                         mock_updateProxy,
                                                         mock_mkdir):
    """
    Tests that runSoftwareWithLock and runInstanceWithLock make correct calls
    to sup_process (= supervisord)
    """
    mock_updateProxy.return_value = True
    cwd = os.getcwd()
    config = {'software_root': os.path.join(cwd, 'software'),
              'software_log': os.path.join(cwd, 'software.log'),
              'instance_root': os.path.join(cwd, 'software'),
              'instance_log': os.path.join(cwd, 'software.log')}
    # If process is already running, then does nothing
    self.sup_process.isRunning.return_value = True
    self.assertEqual(run_slapgrid_function(config), 1)
    self.assertFalse(self.sup_process.runProcess.called)

    # If the slapgrid process is not running, it should start it
    self.sup_process.isRunning.return_value = False
    # First, without Lock
    run_slapgrid_function(config)
    self.sup_process.runProcess.assert_called_once_with(config, process_name)
    self.assertFalse(self.sup_process.waitForProcessEnd.called)
    # Second, with Lock
    self.sup_process.reset_mock()
    run_slapgrid_function(config, lock=True)
    self.sup_process.runProcess.assert_called_once_with(config, process_name)
    self.sup_process.waitForProcessEnd.assert_called_once_with(config, process_name)

  def test_runSoftwareWithLockMakesCorrectCallstoSupervisord(self):
    self._runSlapgridWithLockMakesCorrectCallsToSupervisord(
      runner_utils.runSoftwareWithLock, 'slapgrid-sr')

  def test_runInstanceWithLockMakesCorrectCallstoSupervisord(self):
    self._runSlapgridWithLockMakesCorrectCallsToSupervisord(
      runner_utils.runInstanceWithLock, 'slapgrid-cp')

  @mock.patch('os.path.exists')
  @mock.patch('os.remove')
  @mock.patch('slapos.runner.utils.startProxy')
  @mock.patch('slapos.runner.utils.stopProxy')
  @mock.patch('slapos.runner.utils.removeProxyDb')
  def test_changingSRUpdatesProjectFileWithExistingPath(self,
                                                        mock_removeProxyDb,
                                                        mock_stopProxy,
                                                        mock_startProxy,
                                                        mock_remove,
                                                        mock_path_exists):
    cwd = os.getcwd()
    config = {'etc_dir' : os.path.join(cwd, 'etc'),
              'workspace': os.path.join(cwd, 'srv', 'runner')}
    projectpath = 'workspace/project/software/'
    self.assertNotEqual(runner_utils.realpath(config, projectpath, \
                                              check_exist=False), '')

    # If projectpath doesn't exist, .project file shouldn't be written
    mock_path_exists.return_value = False
    result = runner_utils.configNewSR(config, projectpath)
    self.assertFalse(result)

    # If projectpath exist, .project file should be overwritten
    mock_path_exists.return_value = True
    result = runner_utils.configNewSR(config, projectpath)
    self.assertTrue(result)
    runner_utils.open.assert_has_calls([mock.call().write(projectpath)])



if __name__ == '__main__':
  random.seed()
  unittest.main()
