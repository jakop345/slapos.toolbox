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

import json
import urllib
import time

from .erp5 import ERP5TestSuite

class ERP5ClusterTestSuite(ERP5TestSuite):
  """
  Run ERP5 (erp5-cluster flavor) inside Slaprunner Resiliency Test.
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

  def _gitClone(self):
    ERP5TestSuite._gitClone(self)
    self._connectToSlaprunner(
      resource='/newBranch',
      data='project=workspace%2Fslapos&name=erp5-cluster&create=0'
    )

  def _connectToERP5(self, url, data=None, password=None):
    if password is None:
      password = self._getERP5Password()
    return ERP5TestSuite._connectToERP5(self, url, data, password)

  def _createRandomERP5Document(self, password=None):
    if password is None:
      password = self._getERP5Password()

    return ERP5TestSuite._createRandomERP5Document(self, password)

  def _getCreatedERP5Document(self):
    """ Fetch and return content of ERP5 document created above."""
    url = "%s/erp5/getTitle" % self._getERP5Url()
    return self._connectToERP5(url)

def runTestSuite(*args, **kwargs):
  """
  Run ERP5 erp5-cluster Resiliency Test.
  """
  return ERP5ClusterTestSuite(*args, **kwargs).runTestSuite()

