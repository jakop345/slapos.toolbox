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

# XXX: takeover module should be in slapos.toolbox, not in slapos.cookbook
from slapos.recipe.addresiliency.takeover import takeover
import slapos.slap

import logging
import time

class ResiliencyTestSuite(object):
  """
  Abstract class supposed to be extended by Resiliency Test Suites.
  """
  def __init__(self,
               server_url, key_file, cert_file,
               computer_id, partition_id, software,
               namebase,
               root_instance_name,
               total_instance_count="3"):
    self.server_url = server_url
    self.key_file = key_file
    self.cert_file = cert_file
    self.computer_id = computer_id
    self.partition_id = partition_id
    self.software = software
    self.namebase = namebase
    self.total_instance_count = total_instance_count
    self.root_instance_name = root_instance_name

    slap = slapos.slap.slap()
    slap.initializeConnection(server_url, key_file, cert_file)
    self.partition = slap.registerComputerPartition(
        computer_guid=computer_id,
        partition_id=partition_id
    )

    self.logger = logging.getLogger('SlaprunnerResiliencyTest')
    # XXX Quite hardcoded...
    self.logger.setLevel(logging.DEBUG)

  def _doTakeover(self, target_clone):
    """
    Private method.
    Make the specified clone instance takeover the main instance.
    """
    self.logger.info('Replacing main instance by clone instance %s%s...' % (
        self.namebase, target_clone))
    takeover(
        server_url=self.server_url,
        key_file=self.key_file,
        cert_file=self.cert_file,
        computer_guid=self.computer_id,
        partition_id=self.partition_id,
        software_release=self.software,
        namebase=self.namebase,
        winner_instance_suffix=str(target_clone),
    )
    self.logger.info('Done.')

  def generateData(self):
    """
    Generate data that will be used by the test.
    """
    raise NotImplementedError('Overload me, I am an abstract method.')

  def pushDataOnMainInstance(self):
    """
    Push our data to the main instance.
    """
    raise NotImplementedError('Overload me, I am an abstract method.')

  def checkDataOnCloneInstance(self):
    """
    Check that, on the ex-clone, now-main instance, data is the same as
    what we pushed to the ex-main instance.
    """
    raise NotImplementedError('Overload me, I am an abstract method.')


  def _getPartitionParameterDict(self):
    """
    Helper.
    Return the partition parameter dict of the main root ("resilient") instance.
    """
    return self.partition.request(
        software_release=self.software,
        software_type='resilient',
        partition_reference=self.root_instance_name
    ).getConnectionParameterDict()

  def _returnNewInstanceParameter(self, parameter_key, old_parameter_value):
    """
    Helper, can be used inside of checkDataOnCloneInstance.
    Wait for the new parameter (of old-clone new-main instance) to appear.
    Check than it is different from the old parameter
    """
    self.logger.info('Waiting for new main instance to be ready...')
    new_parameter_value = None
    while not new_parameter_value or new_parameter_value == 'None' or  new_parameter_value == old_parameter_value:
      self.logger.info('Not ready yet. SlapOS says new parameter value is %s' % new_parameter_value)
      time.sleep(60)
      new_parameter_value = self._getPartitionParameterDict().get(parameter_key, None)
    self.logger.info('New parameter value of instance is %s' % new_parameter_value)

    return new_parameter_value


  def runTestSuite(self):
    """
    Generate data to send,
    Push data on main instance,
    Wait for replication to be done,
    For each clone: Do a takeover, Check data.
    """
    self.generateData()

    self.pushDataOnMainInstance()

    # In resilient stack, main instance (example with KVM) is named "kvm0",
    # clones are named "kvm1", "kvm2", ...
    clone_count = int(self.total_instance_count) - 1
    # So first clone starts from 1.
    current_clone = 1

    # Test each clone
    while current_clone <= clone_count:
      # Wait for XX minutes so that replication is done
      sleep_time = 60 * 15#2 * 60 * 60
      self.logger.info('Sleeping for %s seconds before testing clone %s.' % (
          sleep_time,
          current_clone
      ))
      time.sleep(sleep_time)
      self._doTakeover(current_clone)
      self.logger.info('Testing %s%s instance.' % (self.namebase, current_clone))
      success = self.checkDataOnCloneInstance()
      if not success:
        return False
      current_clone = current_clone + 1

    # All clones have been successfully tested: success.
    return True