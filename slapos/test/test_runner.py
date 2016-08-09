import mock
import os
import string
import random
import unittest

from slapos.runner import views as runner_views
from slapos.runner import utils as runner_utils
from slapos.runner import sup_process as runner_process

class TestRunner(unittest.TestCase):
  def tearDown(self):
    htpasswd_file = os.path.join(*(os.getcwd(), '.htpasswd'))
    if os.path.exists(htpasswd_file):
      os.remove(htpasswd_file)

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

  @mock.patch('slapos.runner.utils.open')
  @mock.patch('os.path.exists')
  def test_getCurrentSoftwareReleaseProfile(self, mock_path_exists, mock_open):
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
    mock_open.return_value.read.return_value = "workspace/fake/path/"
    mock_path_exists.return_value = False
    profile = runner_utils.getCurrentSoftwareReleaseProfile(config)
    self.assertEqual(profile, "")

    # If software_profile exists, getCurrentSoftwareReleaseProfile should
    # return its absolute path
    mock_open.return_value.read.return_value = "workspace/project/software/"
    mock_path_exists.return_value = True
    profile = runner_utils.getCurrentSoftwareReleaseProfile(config)
    self.assertEqual(profile, os.path.join(config['workspace'], 'project',
        'software', config['software_profile']))

if __name__ == '__main__':
  random.seed()
  unittest.main()
