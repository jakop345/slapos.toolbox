import datetime
import json
import sys
import traceback
import time
import feedparser
from uritemplate import expand

import slapos.slap
from slapos.slap import SoftwareProductCollection

from slapos.slap.slap import ConnectionError
from requests.exceptions import HTTPError


from erp5.util.taskdistribution import SAFE_RPC_EXCEPTION_LIST

SOFTWARE_PRODUCT_NAMESPACE = "product."

SOFTWARE_STATE_UNKNOWN = "SOFTWARE_STATE_UNKNOWN"
SOFTWARE_STATE_INSTALLING = "SOFTWARE_STATE_INSTALLING"
SOFTWARE_STATE_INSTALLED = "SOFTWARE_STATE_INSTALLED"
SOFTWARE_STATE_DESTROYING = "SOFTWARE_STATE_DESTROYING"

INSTANCE_STATE_UNKNOWN = "INSTANCE_STATE_UNKNOWN"
INSTANCE_STATE_STARTING = "INSTANCE_STATE_STARTING"
INSTANCE_STATE_STARTED = "INSTANCE_STATE_STARTED"
INSTANCE_STATE_STARTED_WITH_ERROR = "INSTANCE_STATE_STARTED_WITH_ERROR"
INSTANCE_STATE_STOPPING = "INSTANCE_STATE_STOPPING"
INSTANCE_STATE_STOPPED = "INSTANCE_STATE_STOPPED"
INSTANCE_STATE_DESTROYING = "INSTANCE_STATE_DESTROYING"

TESTER_STATE_INITIAL = "TESTER_STATE_INITIAL"
TESTER_STATE_NOTHING = "TESTER_STATE_NOTHING"
TESTER_STATE_SOFTWARE_INSTALLED = "TESTER_STATE_SOFTWARE_INSTALLED"
TESTER_STATE_INSTANCE_INSTALLED = "TESTER_STATE_INSTANCE_INSTALLED"
TESTER_STATE_INSTANCE_STARTED = "TESTER_STATE_INSTANCE_STARTED"
TESTER_STATE_INSTANCE_UNINSTALLED = "TESTER_STATE_INSTANCE_UNINSTALLED"

class TestTimeout(Exception):
  pass



# Simple decorator to prevent raise due small
# network failures.
def retryOnNetworkFailure(func):
  def wrapper(*args, **kwargs):
    retry_time = 64
    while True:
      try:
        return func(*args, **kwargs)
      except SAFE_RPC_EXCEPTION_LIST, e:
        print 'Network failure: %s , %s' % (sys.exc_info(), e)
      except HTTPError, e:
        print 'Network failure: %s , %s' % (sys.exc_info(), e)
      except ConnectionError, e:
        print 'Network failure: %s , %s' % (sys.exc_info(), e)
      except slapos.slap.ConnectionError, e:
        print 'Network failure: %s , %s' % (sys.exc_info(), e)

      print 'Retry method %s in %i seconds' % (func, retry_time)
      time.sleep(retry_time)
      retry_time += retry_time >> 1

  wrapper.__name__ = func.__name__
  wrapper.__doc__ = func.__doc__
  return wrapper


class SlapOSMasterCommunicator(object):


  def __init__(self, slap, slap_supply, slap_order, url, logger):

    self._logger = logger
    self.slap = slap
    self.slap_order = slap_order
    self.slap_supply = slap_supply
    self.hateoas_navigator = self.slap._hateoas_navigator
    self.hosting_subscription_url = None

    if url is not None and \
      url.startswith(SOFTWARE_PRODUCT_NAMESPACE):

      product = SoftwareProductCollection(self._logger, self.slap)
      try:
        url = product.__getattr__(url[len(SOFTWARE_PRODUCT_NAMESPACE):])
      except AttributeError as e:
        self._logger.warning('Error on get software release : %s ' % e.message)

    self.url = url  

  @retryOnNetworkFailure
  def _supply(self, state):
    if self.computer_guid is None:
      self._logger.info('Nothing to supply for %s.' % (self.name))
      return None

    self._logger.info('Supply %s@%s: %s', self.url, self.computer_guid,
        state)
    return self.slap_supply.supply(self.url, self.computer_guid, state)

  @retryOnNetworkFailure
  def _request(self, state):
    self._logger.info('Request %s@%s: %s', self.url, self.name, state)
    self.latest_state = state
    return self.slap_order.request(
          software_release=self.url,
          partition_reference=self.name,
          state=state,
          **self.request_kw)

  @retryOnNetworkFailure
  def _hateoas_getComputer(self, reference):

    root_document = self.hateoas_navigator.getRootDocument()
    search_url = root_document["_links"]['raw_search']['href']

    getter_link = expand(search_url, { 
      "query": "reference:%s AND portal_type:Computer" % reference, 
      "select_list": ["relative_url"],
      "limit": 1})

    result = self.hateoas_navigator.GET(getter_link)
    content_list = json.loads(result)['_embedded']['contents']

    if len(content_list) == 0:
      raise Exception('No Computer found.')

    computer_relative_url = content_list[0]["relative_url"]
    
    getter_url = self.hateoas_navigator.getDocumentAndHateoas(
      computer_relative_url)

    return json.loads(self.hateoas_navigator.GET(getter_url))
    
 
  @retryOnNetworkFailure
  def getSoftwareInstallationList(self):
    # XXX Move me to slap.py API 

    computer = self._hateoas_getComputer(self.computer_guid)

    # Not a list ?
    action = computer['_links']['action_object_slap']

    if action.get('title') == 'getHateoasSoftwareInstallationList':
      getter_link = action['href']
    else:
      raise Exception('No Link found found.')

    result = self.hateoas_navigator.GET(getter_link)
    return json.loads(result)['_links']['content']


  @retryOnNetworkFailure
  def getSoftwareInstallationNews(self):
    for si in self.getSoftwareInstallationList():
      if si["title"] == self.url:
        getter_link = si["href"]
        break
    
    result = self.hateoas_navigator.GET(getter_link)
    action_object_slap_list = json.loads(result)['_links']['action_object_slap']

    for action in action_object_slap_list:
      if action.get('title') == 'getHateoasNews':
        getter_link = action['href']
        break
    else:
      raise Exception('getHateoasNews not found.')

    result = self.hateoas_navigator.GET(getter_link)
    if len(json.loads(result)['news']) > 0:
      return json.loads(result)['news'][0]["text"]
    return ""

  @retryOnNetworkFailure
  def getInstanceUrlList(self):

    if self.hosting_subscription_url is None:
      hosting_subscription_dict = self.hateoas_navigator._hateoas_getHostingSubscriptionDict()
      for hs in hosting_subscription_dict:
        if hs['title'] == self.name:
          self.hosting_subscription_url = hs['href'] 
          break 

    if self.hosting_subscription_url is None:
      return None

    return self.hateoas_navigator.getHateoasInstanceList(
            self.hosting_subscription_url)

  @retryOnNetworkFailure
  def getNewsFromInstance(self, url):

    result = self.hateoas_navigator.GET(url)
    result = json.loads(result)
    if result['_links'].get('action_object_slap', None) is None:
      return None

    object_link = self.hateoas_navigator.hateoasGetLinkFromLinks(
       result['_links']['action_object_slap'], 'getHateoasNews')
    
    result = self.hateoas_navigator.GET(object_link)
    return json.loads(result)['news']

  @retryOnNetworkFailure
  def getInformationFromInstance(self, url):

    result = self.hateoas_navigator.GET(url)
    result = json.loads(result)
    if result['_links'].get('action_object_slap', None) is None:
      print result['links']
      return None

    object_link = self.hateoas_navigator.hateoasGetLinkFromLinks(
       result['_links']['action_object_slap'], 'getHateoasInformation')

    result = self.hateoas_navigator.GET(object_link)
    return json.loads(result)


class SoftwareReleaseTester(SlapOSMasterCommunicator):
  deadline = None
  latest_state = None

  def __init__(self,
              name,
              logger,
              slap,
              slap_order,
              slap_supply,
              url, # software release url
              computer_guid=None, # computer for supply if desired
              request_kw=None, # instance parameters, if instantiation
                               # testing is desired
              software_timeout=3600,
              instance_timeout=3600,
          ):

    super(SoftwareReleaseTester, self).__init__( 
      slap, slap_supply, slap_order, url, logger) 

    self.name = name
    self.computer_guid = computer_guid

    if isinstance(request_kw, str) or \
      isinstance(request_kw, unicode):
      self.request_kw = json.loads(request_kw)
    else:
      self.request_kw = request_kw
    self.message_history = []
 
    self.state = TESTER_STATE_INITIAL
    self.transition_dict = {
      # step function
      # delay
      # next_state
      # software_state
      # instance_state
      TESTER_STATE_INITIAL: (
        lambda t: None,
        None,
        TESTER_STATE_NOTHING,
        None,
        None,
      ),
      TESTER_STATE_NOTHING: (
        lambda t: t._supply("available"),
        int(software_timeout),
        request_kw is None and TESTER_STATE_INSTANCE_UNINSTALLED or \
            TESTER_STATE_SOFTWARE_INSTALLED,
        SOFTWARE_STATE_INSTALLED,
        None,
      ),
      TESTER_STATE_SOFTWARE_INSTALLED: (
        lambda t: t._request("started"),
        int(instance_timeout),
        TESTER_STATE_INSTANCE_STARTED,
        None,
        INSTANCE_STATE_STARTED,
      ),
      TESTER_STATE_INSTANCE_STARTED: (
        lambda t: t._request("destroyed"),
        int(1200),
        TESTER_STATE_INSTANCE_UNINSTALLED,
        None,
        INSTANCE_STATE_STOPPED,
      ),
      TESTER_STATE_INSTANCE_UNINSTALLED: (
        lambda t: t._supply("destroyed"),
        int(1200),
        None,
        None,
        None,
      ),
     }

  def __repr__(self):
      deadline = self.deadline
      if deadline is not None:
          deadline -= time.time()
          deadline = '+%is' % (deadline, )
      return '<%s(state=%s, deadline=%s) at %x>' % (
          self.__class__.__name__, self.state, deadline, id(self))

  def getInfo(self):
    info = ""
    info += "Software Release URL: %s\n" % (self.url)
    if self.computer_guid is not None:
      info += "Supply requested on: %s\n" % (self.computer_guid)
    info += "Instance Requested (Parameters): %s\n" % self.request_kw
    return info

  def getFormatedLastMessage(self):
    if len(self.message_history) == 0:
      return "No message"

    summary = "Summary about the test. Instance List and Status:\n"
    message = "Last information about the tester:\n"
    if self.message_history[-1] is not None:
      message_list = self.message_history[-1]
      for entry in message_list:
        summary += "%s %s -> %s\n" % (
          entry['title'], entry["slave"] and "(slave)" or "", entry['state'])
        for prop in entry:
          if prop != "information":
            message += "%s = %s\n" % (prop, json.dumps(entry[prop], indent=2))
          
        message += "=== connection_dict === \n%s\n" % (
          json.dumps(entry["information"]["connection_dict"], indent=2))
        message += "\n"
        message += "=== parameter_dict === \n%s\n" % (
          json.dumps(entry["information"]["parameter_dict"], indent=2))
        message += "\n"
      message += "="*79
      message += "\n\n\n"
 
    return summary + message

  def _getSoftwareState(self):
    if self.computer_guid is None:
      return SOFTWARE_STATE_INSTALLED

    message = self.getSoftwareInstallationNews()
    if message.startswith("#error no data found"):
      return SOFTWARE_STATE_UNKNOWN

    if message.startswith('#access software release'):
      return SOFTWARE_STATE_INSTALLED

    if message.startswith('#error'):
      return SOFTWARE_STATE_INSTALLING

    return SOFTWARE_STATE_UNKNOWN 

  @retryOnNetworkFailure
  def getRSSEntryFromMonitoring(self, base_url):
    if base_url is None:
      return {}

    feed_url = base_url + '/monitor-public/rssfeed.html'
    d = feedparser.parse(feed_url) 
    
    if len(d.entries) > 0:
      return {"date": d.entries[0].published, 
              "message": d.entries[0].description, 
              "title" : d.entries[0].title}
        
    return {}

  @retryOnNetworkFailure
  def _getInstanceState(self):
    latest_state = self.latest_state
    self._logger.debug('latest_state = %r', latest_state)

    if latest_state is None:
      return INSTANCE_STATE_UNKNOWN

    message_list = [] 
    try:
      for instance in self.getInstanceUrlList():
        news = self.getNewsFromInstance(instance["href"])
        information = self.getInformationFromInstance(instance["href"])
        state = INSTANCE_STATE_UNKNOWN
        monitor_information_dict = {}

        info_created_at = "-1"
        is_slave = information['slave']
        if is_slave:
          self._logger.debug('Instance is slave')
          if (information["connection_dict"]) > 0:
            state =  INSTANCE_STATE_STARTED
        else:
          # not slave
          instance_state = news[0]
          if instance_state.get('created_at', '-1') != "-1":
            # the following does NOT take TZ into account
            created_at = datetime.datetime.strptime(instance_state['created_at'], 
              '%a, %d %b %Y %H:%M:%S %Z')
            gmt_now = datetime.datetime(*time.gmtime()[:6])

            info_created_at = '%s (%d)' % (
               instance_state['created_at'], (gmt_now - created_at).seconds)

            if instance_state['text'].startswith('#access'):
              state =  INSTANCE_STATE_STARTED

            if instance_state['text'].startswith('#access Instance correctly stopped'):
              state =  INSTANCE_STATE_STOPPED

            if instance_state['text'].startswith('#error'):
              state = INSTANCE_STATE_STARTED_WITH_ERROR

        if state == INSTANCE_STATE_STARTED_WITH_ERROR:
          # search for monitor url
          monitor_v6_url = information["connection_dict"].get("monitor_v6_url")
          try:
            monitor_information_dict = self.getRSSEntryFromMonitoring(monitor_v6_url)
          except Exception:
            self._logger.exception('Unable to download promises for: %s' % (instance["title"]))
            self._logger.info(traceback.format_exc())
            monitor_information_dict = {"message": "Unable to download"}

        self._logger.info('Instance state: %s -> %s' % (instance['title'], state))
        self._logger.info('Instance Created at: %s -> %s' % (instance['title'], info_created_at))
 
        message_list.append({
          'title': instance["title"],
          'slave': is_slave,
          'news': news[0],
          'information': information,
          'monitor': monitor_information_dict,
          'state': state
        })

    except slapos.slap.ServerError:
      self._logger.exception('Got an error requesting partition for '
            'its state')
      return INSTANCE_STATE_UNKNOWN
 
    started = 0
    stopped = 0
    self.message_history.append(message_list)
    for instance in message_list:
      if not instance['slave'] and \
        instance['state'] in (INSTANCE_STATE_UNKNOWN, INSTANCE_STATE_STARTED_WITH_ERROR):
        return instance['state']
      elif not instance['slave'] and instance['state'] == INSTANCE_STATE_STARTED:
        started = 1
      elif not instance['slave'] and instance['state'] == INSTANCE_STATE_STOPPED:
        stopped = 1
      
      if instance['slave'] and instance['state'] == INSTANCE_STATE_UNKNOWN:
        return instance['state']

    if started and stopped:
      return INSTANCE_STATE_UNKNOWN
    
    if started:
      return INSTANCE_STATE_STARTED

    if stopped:
      return INSTANCE_STATE_STOPPED

  @retryOnNetworkFailure
  def teardown(self):
    """
    Interrupt a running test sequence, putting it in idle state.
    """
    self._logger.info('Invoking TearDown for %s@%s' % (self.url, self.name))
    if self.request_kw is not None:
       self._request('destroyed')
    if self.computer_guid is not None:
      self._supply('destroyed')
    self.state = TESTER_STATE_INSTANCE_UNINSTALLED

  def tic(self, now):
    """
    Check for missed deadlines (-> test failure), conditions for moving to
    next state, and actually moving to next state (executing its payload).
    """
    self._logger.debug('TIC')
    deadline = self.deadline

    if deadline < now and deadline is not None:
      raise TestTimeout(self.state)

    _, _, next_state, software_state, instance_state = self.transition_dict[
        self.state]

    if (software_state is None or
          software_state == self._getSoftwareState()) and (
          instance_state is None or
          instance_state == self._getInstanceState()):

      self._logger.debug('Going to state %s (%r)', next_state, instance_state)
      if next_state is None:
        return None

      self.state = next_state
      stepfunc, delay, _, _, _ = self.transition_dict[next_state]
      self.deadline = now + delay
      stepfunc(self)
    return self.deadline

