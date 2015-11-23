import socket
import logging
import time
import ConfigParser
import logging.handlers
import urllib2
import subprocess
import re
import sys
import shutil
import netifaces
import random
import pycurl
import json
from StringIO import StringIO

botname = socket.gethostname()

# rtt min/avg/max/mdev = 1.102/1.493/2.203/0.438 ms
ping_re = re.compile(
    ".*"
    "(?P<min>[\d\.]+)/"
    "(?P<avg>[\d\.]+)/"
    "(?P<max>[\d\.]+)/"
    "(?P<mdev>[\d\.]+) ms"
    )

date_reg_exp = re.compile('\d{4}[-/]\d{2}[-/]\d{2}')

def _get_network_gateway(self):
  return netifaces.gateways()["default"][netifaces.AF_INET][0]

def _test_dns(name):
  begin = time.time()
  try:
    socket.gethostbyname(name)
    resolution = 200
    status = "OK"
  except socket.gaierror:
    resolution = 600
    status = "Cannot resolve the hostname"

  resolving_time = time.time() - begin
  return ('DNS', name, resolution, resolving_time, status)

def _test_ping(host, timeout=10, protocol="4"):
  if protocol == '4':
    ping_bin = 'ping'
    test_title = 'PING'
  elif protocol == '6':
    ping_bin = 'ping6'
    test_title = 'PING6'
  
  proc = subprocess.Popen((ping_bin, '-c', '10', '-w', str(timeout), host), 
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  out, err = proc.communicate()
  if 'Network is unreachable' in err:
    return (test_title, host, '600', 'failed', 100, "Network is unreachable")
  try:
    packet_loss_line, summary_line = (out.splitlines() or [''])[-2:]
  except:
    return (test_title, host, '600', 'failed', -1, "Fail to parser ping output")
  m = ping_re.match(summary_line)
  match = re.search('(\d*)% packet loss', packet_loss_line)
  packet_lost_ratio = match.group(1)
  
  info_list = (test_title, host, '600', 'failed', packet_lost_ratio, "Cannot ping host")
  if packet_lost_ratio != 0:
    if m:
      info_list = (test_title, host, '200', m.group('avg'), packet_lost_ratio,
           'min %(min)s max %(max)s avg %(avg)s' % m.groupdict())
  else:
    info_list = (test_title, host, '600', 'failed', packet_lost_ratio,
      "You have package Lost")

  return info_list

def _test_ping6(host, timeout=10):
  return _test_ping(host, timeout=10, protocol='6')

def _test_url_request(url):
  begin = time.time()
  
  buffer = StringIO()
  curl = pycurl.Curl()
  curl.setopt(curl.URL, url)
  curl.setopt(curl.CONNECTTIMEOUT, 10)
  curl.setopt(curl.TIMEOUT, 300)
  curl.setopt(curl.WRITEDATA, buffer)
  curl.setopt(curl.SSL_VERIFYPEER, False)
  curl.setopt(curl.SSL_VERIFYHOST, False)

  result = "OK"
  
  try:
    curl.perform()
  except:
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    result = "FAIL"
  
  body = buffer.getvalue()
  
  rendering_time = "%s;%s;%s;%s;%s" % \
    (curl.getinfo(curl.NAMELOOKUP_TIME),
     curl.getinfo(curl.CONNECT_TIME),
     curl.getinfo(curl.PRETRANSFER_TIME),
     curl.getinfo(curl.STARTTRANSFER_TIME),
     curl.getinfo(curl.TOTAL_TIME))
  
  response_code = curl.getinfo(pycurl.HTTP_CODE)
  
  curl.close()

  info_list = ('GET', url, response_code, rendering_time, result)
  
  return info_list
  
def download_external_configuration(url):
  buffer = StringIO()
  curl = pycurl.Curl()
  curl.setopt(curl.URL, url)
  curl.setopt(curl.CONNECTTIMEOUT, 10)
  curl.setopt(curl.TIMEOUT, 300)
  curl.setopt(curl.WRITEDATA, buffer)
  curl.setopt(curl.SSL_VERIFYPEER, False)
  curl.setopt(curl.SSL_VERIFYHOST, False)

  try:
    curl.perform()
  except:
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()

  response_code = curl.getinfo(pycurl.HTTP_CODE)
  
  curl.close()

  if response_code == 200:
    try:
      return json.loads(buffer.getvalue())
    except ValueError:
      print "Unable to parse external configuration, error:"
      import traceback
      traceback.print_exc(file=sys.stderr)
      sys.stderr.flush()
      print "Ignoring external configuration"

  return {}

def is_rotate_log(log_file_path):
  try:
    log_file = open(log_file_path, 'r')
  except IOError:
    return False

  # Handling try-except-finally together.
  try:
    try:
      log_file.seek(0, 2)
      size = log_file.tell()
      log_file.seek(-min(size, 4096), 1)
      today = time.strftime("%Y-%m-%d")
      
      for line in reversed(log_file.read().split('\n')):
        if len(line.strip()):
          match_list = date_reg_exp.findall(line)
          if len(match_list):
            if match_list[0] != today:
              return ValueError(match_list[0])
            break

    except IOError:
      return False
  finally:
    log_file.close()

def create_logger(name, log_folder):
  new_logger = logging.getLogger(name)

  new_logger.setLevel(logging.DEBUG)
  log_file = '%s/network_bench.%s.log' % (log_folder, name)
  handler = logging.handlers.TimedRotatingFileHandler(
                     log_file, when="D",
                     backupCount=1000)

  last_date = is_rotate_log(log_file)
  if last_date:
    handler.doRollover()
    today = time.strftime("%Y-%m-%d")
    shutil.move("%s.%s" % (log_file, today),
                "%s.%s" % (log_file, last_date))
    # The simpler the better
    sp = subprocess.Popen("gzip %s.%s" % (log_file, last_date),
               stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
    sp.communicate()

  format = "%%(asctime)-16s;%s;%%(message)s" % botname
  handler.setFormatter(logging.Formatter(format))
  new_logger.addHandler(handler)
  return new_logger

def main():
  if len(sys.argv) not in [2, 3]:
    print " USAGE: %s configuration_file [log_folder]" % sys.argv[0]
    return

  config = ConfigParser.ConfigParser()
  config.read(sys.argv[1])

  if len(sys.argv) == 3:
    log_folder = sys.argv[2]
  else:
    log_folder = "."

  delay = random.randint(0, 30)

  name_list = []
  url_list = []
  ping_list = []
  ping6_list = []

  if config.has_option("network_bench", "dns"):
    name_list = config.get("network_bench", "dns").split()

  if config.has_option("network_bench", "url"):
    url_list = config.get("network_bench", "url").split()

  if config.has_option("network_bench", "ping"):
    ping_list = config.get("network_bench", "ping").split()

  if config.has_option("network_bench", "ping6"):
    ping6_list = config.get("network_bench", "ping6").split()
  

  if config.has_option("network_bench", "test_distributor_url"):
    
    external_configuration_url = config.get("network_bench", "test_distributor_url")
    external_config_dict = download_external_configuration(external_configuration_url)
  
    name_list.extend(external_config_dict.get("dns", []))
    url_list.extend(external_config_dict.get("url",[]))
    ping_list.extend(external_config_dict.get("ping", []))
    ping6_list.extend(external_config_dict.get("ping6", []))

  time.sleep(delay)

  dns_logger = create_logger("dns", log_folder)
  for name in name_list:
    info_list = _test_dns(name)
    dns_logger.info(';'.join(str(x) for x in info_list))

  ping_logger = create_logger("ping", log_folder)
  for host in ping_list:
    info_list = _test_ping(host)
    ping_logger.info(';'.join(str(x) for x in info_list))


  ping6_logger = create_logger("ping6", log_folder)
  for host in ping6_list:
    info_list = _test_ping6(host)
    ping6_logger.info(';'.join(str(x) for x in info_list))

  http_logger = create_logger("http", log_folder)
  for url in url_list:
    info_list = _test_url_request(url)
    http_logger.info(';'.join(str(x) for x in info_list))
