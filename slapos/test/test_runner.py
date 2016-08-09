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

if __name__ == '__main__':
  random.seed()
  unittest.main()
