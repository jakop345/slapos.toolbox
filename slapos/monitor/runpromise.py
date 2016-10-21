#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import json
import psutil
import time
from shutil import copyfile
import glob
import argparse
import traceback

# Promise timeout after 12 seconds
promise_timeout = 12

def parseArguments():
  """
  Parse arguments for monitor collector instance.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument('--pid_path',
                      help='Path where the pid of this process will be writen.')
  parser.add_argument('--output',
                      help='The Path of file where Json result of this promise will be saved.')
  parser.add_argument('--promise_script',
                      help='Promise script to execute.')
  parser.add_argument('--promise_folder',
                      help='Folder where to find promises to execute. Hide --promise_script and --promise_name')
  parser.add_argument('--monitor_promise_folder',
                      help='Folder where to find Custom monitor promises to execute.')
  parser.add_argument('--promise_name',
                      help='Title to give to this promise.')
  parser.add_argument('--promise_type',
                      default='status',
                      help='Type of promise to execute. [status, report].')
  parser.add_argument('--monitor_url',
                      help='Monitor Instance website URL.')
  parser.add_argument('--history_folder',
                      help='Path where old result file will be placed before generate a new json result file.')
  parser.add_argument('--instance_name',
                      default='UNKNOWN Software Instance',
                      help='Software Instance name.')
  parser.add_argument('--hosting_name',
                      default='UNKNOWN Hosting Subscription',
                      help='Hosting Subscription name.')

  return parser

class RunPromise(object):

  def __init__(self, config_parser):
    self.config = config_parser

  def runpromise(self):

    if self.config.promise_folder:
      # run all promises from the given folder
      return self.runpromise_synchronous()

    if os.path.exists(self.config.pid_path):
      with open(self.config.pid_path, "r") as pidfile:
        try:
          pid = int(pidfile.read(6))
        except ValueError:
          pid = None
        if pid and os.path.exists("/proc/" + str(pid)):
          print("A process is already running with pid " + str(pid))
          return 1
    start_date = ""
    with open(self.config.pid_path, "w") as pidfile:
      process = self.executeCommand(self.config.promise_script)
      ps_process = psutil.Process(process.pid)
      start_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ps_process.create_time()))
      pidfile.write(str(process.pid))

    status_json = self.generateStatusJsonFromProcess(process, start_date=start_date)

    status_json['_links'] = {"monitor": {"href": self.config.monitor_url}}
    status_json['title'] = self.config.promise_name
    status_json['instance'] = self.config.instance_name
    status_json['hosting_subscription'] = self.config.hosting_name
    status_json['type'] = self.config.promise_type

    # Save the lastest status change date (needed for rss)
    status_json['change-time'] = ps_process.create_time()
    if os.path.exists(self.config.output):
      with open(self.config.output) as f:
        try:
          last_result = json.loads(f.read())
          if status_json['status'] == last_result['status'] and last_result.has_key('change-time'):
            status_json['change-time'] = last_result['change-time']
        except ValueError:
          pass

    self.updateStatusHistoryFolder(
      self.config.promise_name,
      self.config.output,
      self.config.history_folder,
      self.config.promise_type
    )
    with open(self.config.output, "w") as outputfile:
      json.dump(status_json, outputfile)
    os.remove(self.config.pid_path)

  def runpromise_synchronous(self):

    if os.path.exists(self.config.pid_path):
      # Check if another run promise is running
      with open(self.config.pid_path) as fpid:
        try:
          pid = int(fpid.read(6))
        except ValueError:
          pid = None
        if pid and os.path.exists("/proc/" + str(pid)):
          print("A process is already running with pid " + str(pid))
          return []

    with open(self.config.pid_path, 'w') as fpid:
      fpid.write(str(os.getpid()))

    promise_folder_list = [self.config.promise_folder]
    if self.config.monitor_promise_folder:
      promise_folder_list.append(self.config.monitor_promise_folder)
    status_list = self.checkPromises(promise_folder_list)
    promises_status_file = os.path.join(self.config.output, '_promise_status')
    previous_state_dict = {}
    new_state_dict = {}
    base_dict = {
      '_links': {"monitor": {"href": self.config.monitor_url}},
      'instance': self.config.instance_name,
      'hosting_subscription': self.config.hosting_name,
    }

    if os.path.exists(promises_status_file):
      with open(promises_status_file) as f:
        try:
          previous_state_dict = json.loads(f.read())
        except ValueError:
          pass

    for status_dict in status_list:
      status_dict.update(base_dict)
      if previous_state_dict.has_key(status_dict['title']):
        status, time = previous_state_dict[status_dict['title']].split('#')
        if status_dict['status'] == status:
          status_dict['change-time'] = float(time)

      promise_result_file = os.path.join(self.config.output, 
                                         "%s.status.json" % status_dict['title'])
      with open(promise_result_file, "w") as outputfile:
        json.dump(status_dict, outputfile)
      new_state_dict[status_dict['title']] = '%s#%s' % (status_dict['status'],
                                                        status_dict['change-time'])
      self.updateStatusHistoryFolder(
        status_dict['title'],
        promise_result_file,
        self.config.history_folder,
        'status'
      )

    with open(promises_status_file, "w") as outputfile:
      json.dump(new_state_dict, outputfile)

    os.remove(self.config.pid_path)

  def updateStatusHistoryFolder(self, name, status_file, history_folder, promise_type):
    history_path = os.path.join(history_folder)
    if not os.path.exists(status_file):
      return
    if not os.path.exists(history_folder):
      return
    if not os.path.exists(history_path):
      try:
        os.makedirs(history_path)
      except OSError, e:
        if e.errno == os.errno.EEXIST and os.path.isdir(history_path):
          pass
        else: raise
    with open(status_file, 'r') as sf:
      try:
        status_dict = json.loads(sf.read())
      except ValueError:
        traceback.print_exc()
        return

    if promise_type == 'status':
      filename = '%s.history.json' % name
      history_file = os.path.join(history_path, filename)
      # Remove links from history (not needed)
      status_dict.pop('_links', None)
      if not os.path.exists(history_file):
        with open(history_file, 'w') as f_history:
          data_dict = {
            "date": time.time(),
            "data": [status_dict]
          }
          f_history.write(json.dumps(data_dict))
      else:
        # Remove useless informations
        status_dict.pop('hosting_subscription', '')
        status_dict.pop('title', '')
        status_dict.pop('instance', '')
        status_dict.pop('type', '')

        with open (history_file, mode="r+") as f_history:
          f_history.seek(0,2)
          position = f_history.tell() -2
          f_history.seek(position)
          #f_history.write(',%s]}' % str(status_dict))
          f_history.write('%s}' % ',{}]'.format(json.dumps(status_dict)))
    elif promise_type == 'report':
      # keep_item_amount = 3
      filename = '%s.history.json' % (
        name)

      copyfile(status_file, os.path.join(history_path, filename))
      """# Don't let history foler grow too much, keep xx files
      file_list = filter(os.path.isfile,
          glob.glob("%s/*.%s.history.json" % (history_path, promise_type))
        )
      file_count = len(file_list)
      if file_count > keep_item_amount:
        file_list.sort(key=lambda x: os.path.getmtime(x))
        while file_count > keep_item_amount:
          to_delete = file_list.pop(0)
          try:
            os.unlink(to_delete)
            file_count -= 1
          except OSError:
            raise"""

  def generateStatusJsonFromProcess(self, process, start_date=None, title=None):
    stdout, stderr = process.communicate()
    status_json = {}
    if process.returncode != 0:
      status_json["status"] = "ERROR"
    else:
      status_json["status"] = "OK"
    if stderr:
      status_json["message"] = stderr
    elif stdout:
      status_json["message"] = stdout
    if start_date:
      status_json["start-date"] = start_date
    if title:
      status_json["title"] = title
    return status_json


  def executeCommand(self, args):
    return subprocess.Popen(
      args,
      #cwd=instance_path,
      #env=None if sys.platform == 'cygwin' else {},
      stdin=None,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE
    )

  def checkPromises(self, promise_dir_list):
    """
      Run all promises found into specified folder
    """
    promise_list = []
    for promise_dir in promise_dir_list:
      if not os.path.exists(promise_dir) or not os.path.isdir(promise_dir):
        continue
      promise_list.extend([os.path.join(promise_dir, promise)
                            for promise in os.listdir(promise_dir)])

    promise_result_list = []

    # Check whether every promise is kept
    for promise_script in promise_list:

      if not os.path.isfile(promise_script) or not os.access(promise_script, os.X_OK):
        # Not executable file
        continue

      command = [promise_script]
      promise_name = os.path.basename(command[0])
      result_dict = {
        "status": "ERROR",
        "type": "status",
        "title": promise_name,
        "start-date" : time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())),
        "change-time": time.time()
      }

      process_handler = subprocess.Popen(command,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         stdin=subprocess.PIPE)
      process_handler.stdin.flush()
      process_handler.stdin.close()
      process_handler.stdin = None

      sleep_time = 0.1
      increment_limit = int(promise_timeout / sleep_time)
      for current_increment in range(0, increment_limit):
        if process_handler.poll() is None:
          time.sleep(sleep_time)
          continue
        if process_handler.poll() == 0:
          # Success!
          result_dict["message"] = process_handler.communicate()[0]
          result_dict["status"] = "OK"
        else:
          stdout, stderr = process_handler.communicate()
          result_dict["message"] = stderr
          if not stderr:
            result_dict["message"] = stdout
        break
      else:
        process_handler.terminate()
        message = process_handler.stderr.read()
        if message is None:
          message = process_handler.stdout.read() or ""
        message += '\nPROMISE TIME OUT AFTER %s SECONDS' % promise_timeout
        result_dict["message"] = message

      promise_result_list.append(result_dict)

    return promise_result_list


def main():
  arg_parser = parseArguments()
  promise_runner = RunPromise(arg_parser.parse_args())
  sys.exit(promise_runner.runpromise())
