# -*- coding: utf-8 -*-
import os, time
import sys
import shutil
import tempfile
import unittest
import json
from datetime import datetime
from slapos.monitor.runpromise import RunPromise, parseArguments

class MonitorPromiseTest(unittest.TestCase):

  def setUp(self):
    self.base_dir = tempfile.mkdtemp()
    self.promise_dir = os.path.join(self.base_dir, 'promise')
    self.monitor_promise_dir = os.path.join(self.base_dir, 'monitor-promise')
    self.report_dir = os.path.join(self.base_dir, 'report')
    self.public_dir = os.path.join(self.base_dir, 'public')
    self.private_dir = os.path.join(self.base_dir, 'private')
    self.run_dir = os.path.join(self.base_dir, 'run')
    os.mkdir(self.promise_dir)
    os.mkdir(self.public_dir)
    os.mkdir(self.private_dir)
    os.mkdir(self.report_dir)
    os.mkdir(self.run_dir)
    os.mkdir(self.monitor_promise_dir)


  def tearDown(self):
    if os.path.exists(self.base_dir):
      shutil.rmtree(self.base_dir)

  def writePromiseOK(self, name, monitor_folder=False):
    content = """#!/bin/sh

echo "success"
exit 0
"""
    promise_path = os.path.join(self.promise_dir, name)
    if monitor_folder:
      promise_path = os.path.join(self.monitor_promise_dir, name)
    self.writeContent(promise_path, content)
    os.chmod(promise_path, 0755)
    return promise_path

  def writePromiseNOK(self, name):
    content = """#!/bin/sh

echo "failed"
exit 2
"""
    promise_path = os.path.join(self.promise_dir, name)
    self.writeContent(promise_path, content)
    os.chmod(promise_path, 0755)
    return promise_path

  def writeContent(self, file_path, config):
    with open(file_path, 'w') as cfg:
      cfg.write(config)

  def getUniquePromiseParser(self, name, promise_path, promise_type):
    pid_path = os.path.join(self.run_dir, '%s.pid' % name)
    if promise_type == "report":
      output_path = os.path.join(self.private_dir, '%s.report.json' % name)
    else:
      output_path = os.path.join(self.public_dir, '%s.status.json' % name)
    promise_cmd = [
      '--pid_path',
      '%s' % pid_path, '--output', output_path,
      '--promise_script', promise_path,
      '--promise_name', name, '--promise_type', promise_type,
      '--monitor_url', 'https://monitor.test.com/share/jio_private/',
      '--history_folder', self.public_dir,
      '--instance_name', 'Monitor', '--hosting_name', 'Monitor ROOT']
    arg_parser = parseArguments()
    return arg_parser.parse_args(promise_cmd)

  def getPromiseParser(self):
    pid_path = os.path.join(self.run_dir, 'monitor-promise.pid')

    promise_cmd = [
      '--pid_path',
      '%s' % pid_path, '--output', self.public_dir,
      '--promise_folder', self.promise_dir,
      '--monitor_promise_folder', self.monitor_promise_dir,
      '--promise_type', 'status',
      '--monitor_url', 'https://monitor.test.com/share/jio_private/',
      '--history_folder', self.public_dir,
      '--instance_name', 'Monitor', '--hosting_name', 'Monitor ROOT']
    arg_parser = parseArguments()
    return arg_parser.parse_args(promise_cmd)

  def test_promise_OK(self):
    
    promise = self.writePromiseOK('promise_1')
    parser = self.getPromiseParser()
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.public_dir, 'promise_1.status.json')
    self.assertTrue(os.path.exists(result_file))
    result1 = json.loads(open(result_file).read())
    change_time = result1.pop('change-time', 0)
    change_date = datetime.fromtimestamp(change_time)
    start_date = result1.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': u'promise_1', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'status'}
    self.assertEquals(expected_result, result1)

    # second run
    time.sleep(1)
    promise_runner.runpromise()
    result2 = json.loads(open(result_file).read())
    change_time2 = result2.pop('change-time', 0)
    start_date2 = result2.pop('start-date')
    change_date2 = datetime.fromtimestamp(change_time2)
    self.assertEquals(expected_result, result2)
    self.assertEquals(change_date.strftime('%Y-%m-%d %H:%M:%S'),
      change_date2.strftime('%Y-%m-%d %H:%M:%S'))

    history_file = os.path.join(self.public_dir, 'promise_1.history.json')
    self.assertTrue(os.path.exists(history_file))
    history = json.load(open(history_file))
    self.assertTrue(history['date'] > change_time)
    self.assertTrue(len(history['data']) == 2)

    result1['change-time'] = change_time
    result1['start-date'] = start_date
    result1.pop('_links')
    result2['start-date'] = start_date2
    result2['change-time'] = change_time2
    # not in history
    result2.pop('_links')
    result2.pop('hosting_subscription')
    result2.pop('title')
    result2.pop('instance')
    result2.pop('type')
    self.assertEquals(history['data'][0], result1)
    self.assertEquals(history['data'][1], result2)

  def test_promise_two_folder(self):
    
    promise = self.writePromiseOK('promise_1')
    promise2 = self.writePromiseOK('promise_2', monitor_folder=True)
    parser = self.getPromiseParser()
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.public_dir, 'promise_1.status.json')
    result2_file = os.path.join(self.public_dir, 'promise_2.status.json')
    self.assertTrue(os.path.exists(result_file))
    self.assertTrue(os.path.exists(result2_file))
    result1 = json.loads(open(result_file).read())
    result1.pop('change-time')
    result1.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': u'promise_1', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'status'}
    self.assertEquals(expected_result, result1)

    result2 = json.loads(open(result2_file).read())
    result2.pop('change-time')
    result2.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': u'promise_2', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'status'}
    self.assertEquals(expected_result, result2)

  def test_promise_One_By_One(self):
    
    promise = self.writePromiseOK('promise_1')
    parser = self.getUniquePromiseParser('promise_1', promise, 'status')
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.public_dir, 'promise_1.status.json')
    self.assertTrue(os.path.exists(result_file))
    result1 = json.loads(open(result_file).read())
    change_time = result1.pop('change-time', 0)
    change_date = datetime.fromtimestamp(change_time)
    start_date = result1.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': u'promise_1', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'status'}
    self.assertEquals(expected_result, result1)

    # second run
    promise_runner.runpromise()
    result2 = json.loads(open(result_file).read())
    change_time2 = result2.pop('change-time', 0)
    result2.pop('start-date', '2016-08-05 00:00:00')
    change_date2 = datetime.fromtimestamp(change_time2)
    self.assertEquals(expected_result, result2)
    self.assertEquals(change_date.strftime('%Y-%m-%d %H:%M:%S'),
      change_date2.strftime('%Y-%m-%d %H:%M:%S'))

    history_file = os.path.join(self.public_dir, 'promise_1.history.json')
    self.assertTrue(os.path.exists(history_file))
    history = json.load(open(history_file))
    self.assertTrue(history['date'] > change_time)
    self.assertTrue(len(history['data']) == 1)

    result1['change-time'] = change_time
    result1['start-date'] = start_date
    result1.pop('_links')
    self.assertEquals(history['data'][0], result1)
    
  def test_promise_NOK(self):
    
    promise = self.writePromiseNOK('promise_1')
    parser = self.getPromiseParser()
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.public_dir, 'promise_1.status.json')
    self.assertTrue(os.path.exists(result_file))
    result1 = json.loads(open(result_file).read())
    change_time = result1.pop('change-time', 0)
    change_date = datetime.fromtimestamp(change_time)
    start_date = result1.pop('start-date')
    
    expected_result = {'status': 'ERROR', 'hosting_subscription': 'Monitor ROOT',
      'title': u'promise_1', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'failed\n', 'type': 'status'}
    self.assertEquals(expected_result, result1)

    # second run
    promise_runner.runpromise()
    result2 = json.loads(open(result_file).read())
    change_time2 = result2.pop('change-time', 0)
    result2.pop('start-date', '2016-08-05 00:00:00')
    change_date2 = datetime.fromtimestamp(change_time2)
    self.assertEquals(expected_result, result2)
    self.assertEquals(change_date.strftime('%Y-%m-%d %H:%M:%S'),
      change_date2.strftime('%Y-%m-%d %H:%M:%S'))

  def test_promise_mixed(self):
    
    promise = self.writePromiseOK('promise_1')
    parser = self.getPromiseParser()
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.public_dir, 'promise_1.status.json')
    self.assertTrue(os.path.exists(result_file))
    result1 = json.loads(open(result_file).read())
    change_time = result1.pop('change-time')
    change_date = datetime.fromtimestamp(change_time)
    start_date = result1.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': u'promise_1', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'status'}
    self.assertEquals(expected_result, result1)

    # second run with failure
    time.sleep(2)
    promise = self.writePromiseNOK('promise_1')
    parser = self.getPromiseParser()
    expected_result['message'] = 'failed\n'
    expected_result['status'] = 'ERROR'
    promise_runner.runpromise()

    result2 = json.loads(open(result_file).read())
    change_time2 = result2.pop('change-time')
    result2.pop('start-date')
    change_date2 = datetime.fromtimestamp(change_time2)
    self.assertEquals(expected_result, result2)
    self.assertNotEquals(change_date.strftime('%Y-%m-%d %H:%M:%S'),
      change_date2.strftime('%Y-%m-%d %H:%M:%S'))

  def test_report_OK(self):
    
    promise = self.writePromiseOK('sample_report')
    parser = self.getUniquePromiseParser('sample_report', promise, 'report')
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.private_dir, 'sample_report.report.json')
    self.assertTrue(os.path.exists(result_file))
    result1 = json.loads(open(result_file).read())
    change_time = result1.pop('change-time', 0)
    change_date = datetime.fromtimestamp(change_time)
    start_date = result1.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': 'sample_report', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'report'}
    self.assertEquals(expected_result, result1)

    # second run
    promise_runner.runpromise()
    result2 = json.loads(open(result_file).read())
    change_time2 = result2.pop('change-time', 0)
    result2.pop('start-date', '2016-08-05 00:00:00')
    change_date2 = datetime.fromtimestamp(change_time2)
    self.assertEquals(expected_result, result2)
    self.assertEquals(change_date.strftime('%Y-%m-%d %H:%M:%S'),
      change_date2.strftime('%Y-%m-%d %H:%M:%S'))

    history_file = os.path.join(self.public_dir, 'sample_report.history.json')
    self.assertTrue(os.path.exists(history_file))
    history = json.load(open(history_file))


    result1['change-time'] = change_time
    result1['start-date'] = start_date
    #result1.pop('_links')
    self.assertEquals(history, result1)

  def test_report_mixed(self):
    
    promise = self.writePromiseOK('sample_report')
    parser = self.getUniquePromiseParser('sample_report', promise, 'report')
    promise_runner = RunPromise(parser)
    promise_runner.runpromise()

    result_file = os.path.join(self.private_dir, 'sample_report.report.json')
    self.assertTrue(os.path.exists(result_file))
    result1 = json.loads(open(result_file).read())
    change_time = result1.pop('change-time', 0)
    change_date = datetime.fromtimestamp(change_time)
    start_date = result1.pop('start-date')
    
    expected_result = {'status': 'OK', 'hosting_subscription': 'Monitor ROOT',
      'title': 'sample_report', 'instance': 'Monitor',
      '_links': 
        {'monitor': {'href': 'https://monitor.test.com/share/jio_private/'}},
        'message': 'success\n', 'type': 'report'}
    self.assertEquals(expected_result, result1)

    # second run with failure
    time.sleep(2)
    promise = self.writePromiseNOK('sample_report')
    parser = self.getUniquePromiseParser('sample_report', promise, 'report')
    expected_result['message'] = 'failed\n'
    expected_result['status'] = 'ERROR'
    promise_runner.runpromise()

    result2 = json.loads(open(result_file).read())
    change_time2 = result2.pop('change-time')
    result2.pop('start-date')
    change_date2 = datetime.fromtimestamp(change_time2)
    self.assertEquals(expected_result, result2)
    self.assertNotEquals(change_date.strftime('%Y-%m-%d %H:%M:%S'),
      change_date2.strftime('%Y-%m-%d %H:%M:%S'))


