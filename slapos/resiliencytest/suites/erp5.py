# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2014 Vifib SARL and Contributors. All Rights Reserved.
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

from .slaprunner import SlaprunnerTestSuite

import json
import random
import ssl
import string
import time
import urllib
import urllib2

class NotHttpOkException(Exception):
  pass

class ERP5TestSuite(SlaprunnerTestSuite):
  """
  Run ERP5 inside Slaprunner Resiliency Test.
  Note: requires specific kernel allowing long shebang paths.
  """

  def _setERP5InstanceParameter(self):
    """
    Set inside of slaprunner the instance parameter to use to deploy erp5 instance.
    """
    self._connectToSlaprunner(
        resource='saveParameterXml',
        data='software_type=create-erp5-site&parameter=%3C%3Fxml+version%3D%221.0%22+encoding%3D%22utf-8%22%3F%3E%0A%3Cinstance%3E%0A%3Cparameter+id%3D%22_%22%3E%7B%22zodb-zeo%22%3A+%7B%22backup-periodicity%22%3A+%22minutely%22%7D%2C+%22mariadb%22%3A+%7B%22backup-periodicity%22%3A+%22minutely%22%7D%7D%3C%2Fparameter%3E%0A%3C%2Finstance%3E%0A'
    )

  def _getERP5Url(self):
    """
    Return the backend url of erp5 instance.
    Note: it is not connection parameter of slaprunner,
    but connection parameter of what is inside of webrunner.
    """
    data = self._connectToSlaprunner(
        resource='getConnectionParameter/slappart7'
    )
    url = json.loads(json.loads(data)['_'])['default-v6']
    self.logger.info('Retrieved erp5 url is:\n%s' % url)
    return url

  def _getERP5Password(self):
    data = self._connectToSlaprunner(
        resource='getConnectionParameter/slappart0'
    )
    password = json.loads(json.loads(data)['_'])['inituser-password']
    self.logger.info('Retrieved erp5 password is:\n%s' % password)
    return password

  def _editHAProxyconfiguration(self):
    """
    XXX pure hack.
    haproxy processes don't support long path for sockets.
    Edit haproxy configuration file of erp5 to make it compatible with long paths
    Then restart haproxy.
    """
    self.logger.info('Editing HAProxy configuration...')

    result = self._connectToSlaprunner(
        resource='/getFileContent',
        data='file=runner_workdir%2Finstance%2Fslappart7%2Fetc%2Fhaproxy.cfg'
    )
    file_content = json.loads(result)['result']
    file_content = file_content.replace('var/run/haproxy.sock', 'ha.sock')
    self._connectToSlaprunner(
        resource='/saveFileContent',
        data='file=runner_workdir%%2Finstance%%2Fslappart7%%2Fetc%%2Fhaproxy.cfg&content=%s' % urllib.quote(file_content)
    )

    # Restart HAProxy
    self._connectToSlaprunner(
        resource='/startStopProccess/name/slappart7:haproxy/cmd/STOPPED'
    )

    time.sleep(15)

  def _getCreatedERP5Document(self):
    """ Fetch and return content of ERP5 document created above."""
    url = "%s/erp5/getTitle" % self._getERP5Url()
    return self._connectToERP5(url)


  def _connectToERP5(self, url, data=None, password=None):
    if password is None:
      password = self._getERP5Password()
    auth_handler = urllib2.HTTPBasicAuthHandler()
    auth_handler.add_password(realm='Zope', uri=url, user='zope', passwd=password)
    ssl_context = ssl._create_unverified_context()
    opener_director = urllib2.build_opener(
        auth_handler,
        urllib2.HTTPSHandler(context=ssl_context)
    )
    self.logger.info('Calling ERP5 url %s' % url)

    if data:
      result = opener_director.open(url, data=data)
    else:
      result = opener_director.open(url)

    if result.getcode() is not 200:
      raise NotHttpOkException(result.getcode())
    return result.read()

  def _createRandomERP5Document(self, password=None):
    """ Create a document with random content in erp5 site."""
    # XXX currently only sets erp5 site title.
    # XXX could be simplified to /erp5/setTitle?title=slapos
    if password is None:
      password = self._getERP5Password()

    erp5_site_title = self.slaprunner_user
    url = "%s/erp5?__ac_name=zope&__ac_password=%s" % (self._getERP5Url(), password)
    form = 'title%%3AUTF-8:string=%s&manage_editProperties%%3Amethod=Save+Changes' % erp5_site_title
    self._connectToERP5(url, form)
    return erp5_site_title

  def _editHAProxyconfiguration(self):
    """
    XXX pure hack.
    haproxy processes don't support long path for sockets.
    Edit haproxy configuration file of erp5 to make it compatible with long paths
    Then restart haproxy.
    """
    self.logger.info('Editing HAProxy configuration...')

    result = self._connectToSlaprunner(
        resource='/getFileContent',
        data='file=runner_workdir%2Finstance%2Fslappart5%2Fetc%2Fhaproxy-erp5.cfg'
    )
    file_content = json.loads(result)['result']
    file_content = file_content.replace('var/run/haproxy-erp5.sock', 'ha-erp5.sock')
    self._connectToSlaprunner(
        resource='/saveFileContent',
        data='file=runner_workdir%%2Finstance%%2Fslappart5%%2Fetc%%2Fhaproxy-erp5.cfg&content=%s' % urllib.quote(file_content)
    )

    # Restart HAProxy
    self._connectToSlaprunner(
        resource='/startStopProccess/name/slappart5:haproxy-erp5/cmd/STOPPED'
    )

    time.sleep(15)

    # In case erp5 bootstrap (in erp5-cluster) couldn't connect to zope through HAProxy
    self._connectToSlaprunner('/startAllPartition')

  def generateData(self):
    self.slaprunner_password = ''.join(
        random.SystemRandom().sample(string.ascii_lowercase, 8)
    )
    self.slaprunner_user = 'slapos'
    self.logger.info('Generated slaprunner user is: %s' % self.slaprunner_user)
    self.logger.info('Generated slaprunner password is: %s' % self.slaprunner_password)

  def pushDataOnMainInstance(self):
    """
    Create a dummy Software Release,
    Build it,
    Wait for build to be successful,
    Deploy instance,
    Wait for instance to be started.
    Store the main IP of the slaprunner for future use.
    """

    self.logger.debug('Getting the backend URL...')
    parameter_dict = self._getPartitionParameterDict()
    self.slaprunner_backend_url = parameter_dict['backend-url']
    self.logger.info('backend_url is %s.' % self.slaprunner_backend_url)
    self.slaprunner_user = parameter_dict['init-user']
    self.slaprunner_password = parameter_dict['init-password']

    self._login()
    time.sleep(10)

    self._gitClone()
    self._openSoftwareRelease('erp5')
    self._setERP5InstanceParameter()

    # Debug, remove me.
    time.sleep(600)

    self._buildSoftwareRelease()
    self._deployInstance()
    self._deployInstance()
    self._deployInstance()
    self._deployInstance()

    self._editHAProxyconfiguration()

    self.logger.info('Waiting 5 minutes so that erp5 can be bootstrapped...')
    time.sleep(300)

    self.data = self._createRandomERP5Document()

    self.logger.info('Wait half an hour for main instance to have backup of erp5...')
    time.sleep(3600 / 2)

    # in erp5testnode, we have only one IP, so we can't run at the same time
    # erp5 in webrunner of main instance, and mariadb/zope/etc in import script of clone instance
    # So we stop main instance processes.
    self._connectToSlaprunner('/stopAllPartition')

    self.logger.info('Wait half an hour for clone to have compiled ERP5 SR...')
    time.sleep(3600 / 2)

  def checkDataOnCloneInstance(self):
    """
    Check that:
      * backend_url is different
      * Software Release profile is the same,
      * Software Release is built and is the same,
      * Instance is deployed and is the same (contains same new data).
    """
    old_slaprunner_backend_url = self.slaprunner_backend_url
    self.slaprunner_backend_url = self._returnNewInstanceParameter(
        parameter_key='backend_url',
        old_parameter_value=old_slaprunner_backend_url,
        force_new=True,
    )
    self._login()
    self._waitForSoftwareBuild()
    self._deployInstance()
    time.sleep(60)

    self._editHAProxyconfiguration()
    new_data = self._getCreatedERP5Document()

    if new_data == self.data:
      self.logger.info('Data are the same: success.')
      return True
    else:
      self.logger.info('Data are different: failure.')
      return False


def runTestSuite(*args, **kwargs):
  """
  Run Slaprunner Resiliency Test.
  """
  return ERP5TestSuite(*args, **kwargs).runTestSuite()

