# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2013 Vifib SARL and Contributors. All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import argparse
import json
import importlib
import logging
import os
import sys
import time
import traceback
from erp5.util import taskdistribution
from erp5.util.testnode import Utils

MAX_INSTALLATION_TIME = 60 * 50
MAX_TESTING_TIME = 60
MAX_GETTING_CONNECTION_TIME = 60 * 5

def importFrom(name):
  """
  Import a test suite module (in the suites module) and return it.
  """
  return importlib.import_module('.suites.%s' % name, package=__name__)

def parseArguments():
  """
  Parse arguments.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument('--test-result-path',
                      metavar='ERP5_TEST_RESULT_PATH',
                      help='ERP5 relative path of the test result')

  parser.add_argument('--revision',
                      metavar='REVISION',
                      help='Revision of the test_suite')

  parser.add_argument('--test-suite',
                      metavar='TEST_SUITE',
                      help='Name of the test suite')

  parser.add_argument('--node-title',
                      metavar='NODE_TITLE',
                      help='Title of the testnode which is running this'
                            'launcher')

  parser.add_argument('--test-suite-master-url',
                      metavar='TEST_SUITE_MASTER_URL',
                      help='Url to connect to the ERP5 Master testsuite taskditributor')

  parser.add_argument('--log-path',
                      metavar='LOG_PATH',
                      help='Log Path')

  parser.add_argument('additional_arguments', nargs=argparse.REMAINDER)

  return parser.parse_args()

def setupLogging(log_path, name=__name__):
  logger_format = '%(asctime)s %(name)-13s: %(levelname)-8s %(message)s'
  formatter = logging.Formatter(logger_format)
  logging.basicConfig(level=logging.INFO,
                      format=logger_format)
  logger = logging.getLogger(name)
  logger.addHandler(logging.NullHandler())
  file_handler = logging.handlers.RotatingFileHandler(
      filename=log_path,
      maxBytes=20000000, backupCount=4)
  file_handler.setFormatter(formatter)
  logger.addHandler(file_handler)
  return logger

class ScalabilityTest(object):
  def __init__(self, data, test_result):
    self.__dict__ = {}
    self.__dict__.update(data)
    self.test_result = test_result

class ScalabilityLauncher(object):
  def __init__(self):
    self._argumentNamespace = parseArguments()
    log_path = os.path.join(self._argumentNamespace.log_path,
                            'runScalabilityTestSuite.log')
    self.log = setupLogging('runScalabilityTestSuite', log_path).info

    # Proxy to erp5 master test_result
    self.test_result = taskdistribution.TestResultProxyProxy(
                        self._argumentNamespace.test_suite_master_url,
                        1.0, self.log,
                        self._argumentNamespace.test_result_path,
                        self._argumentNamespace.node_title,
                        self._argumentNamespace.revision
                      )

  def getNextTest(self):
    """
    Return a ScalabilityTest with current running test case informations,
    or None if no test_case ready
    """
    data = self.test_result.getNextTestCase()
    if data == None :
      return None
    decoded_data = Utils.deunicodeData(json.loads(
                  data
                ))
    next_test = ScalabilityTest(decoded_data, self.test_result)
    return next_test

  def runCurrentTestSuite(self):
    try:
      # Generate the additional arguments that were given using the syntax
      # additionalargument1=value1 additionalargument2=value2
      additional_arguments = dict(key.split('=') for key in self._argumentNamespace.additional_arguments)
      test_suite_module = importFrom(self._argumentNamespace.test_suite)
      success = test_suite_module.runTestSuite(**additional_arguments)
    except:
      self.log('Impossible to run resiliency test:')
      self.log(traceback.print_exc())
      success = False
    return success

  def run(self):
    self.log('Resiliency Launcher started, with:')
    self.log('Test suite master url: %s' % self._argumentNamespace.test_suite_master_url)
    self.log('Test suite: %s' % self._argumentNamespace.test_suite)
    self.log('Test result path: %s' % self._argumentNamespace.test_result_path)
    self.log('Revision: %s' % self._argumentNamespace.revision)
    self.log('Node title: %s' % self._argumentNamespace.node_title)

    while True:
      time.sleep(5)
      current_test = self.getNextTest()
      if current_test == None:
        self.log('No Test Case Ready')
      else:
        start_time = time.time()
        error_message_set, exit_status = set(), 0

        proxy = taskdistribution.ServerProxy(
                    self._argumentNamespace.test_suite_master_url,
                    allow_none=True
                ).portal_task_distribution
        retry_time = 2.0
        test_result_line_test = taskdistribution.TestResultLineProxy(
                                  proxy, retry_time, self.log,
                                  current_test.relative_path,
                                  current_test.title
                                )

        success = self.runCurrentTestSuite()

        if success:
          error_count = 0
        else:
          error_count = 1

        test_duration = time.time() - start_time
        test_result_line_test.stop(stdout='Success',
                        test_count=1,
                        error_count=error_count,
                        duration=test_duration)
        self.log('Test Case Stopped')

    return error_message_set, exit_status

def runResiliencyTest():
  error_message_set, exit_status = ScalabilityLauncher().run()
  for error_message in error_message_set:
    print >>sys.stderr, 'ERROR: %s' % error_message

  sys.exit(exit_status)