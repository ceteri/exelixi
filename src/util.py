#!/usr/bin/env python
# encoding: utf-8

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# author: Paco Nathan
# https://github.com/ceteri/exelixi


from collections import OrderedDict
from httplib import BadStatusLine
from importlib import import_module
from json import dumps, loads
from os.path import abspath
from random import random
from urllib2 import urlopen, Request, URLError
import logging
import psutil
import socket


######################################################################
## utilities

def instantiate_class (class_path):
    """instantiate a class from the given package.class name"""
    module_name, class_name = class_path.split(".")
    return getattr(import_module(module_name), class_name)()


def post_distrib_rest (prefix, shard_id, shard_uri, path, base_msg):
    """POST a JSON-based message to a REST endpoint on a shard"""
    msg = base_msg.copy()

    # populate credentials
    msg["prefix"] = prefix
    msg["shard_id"] = shard_id

    # POST the JSON payload to the REST endpoint
    uri = "http://" + shard_uri + "/" + path
    req = Request(uri)
    req.add_header('Content-Type', 'application/json')

    logging.debug("send %s %s", shard_uri, path)
    logging.debug(dumps(msg))

    # read/collect the response
    try:
        f = urlopen(req, dumps(msg))
        return f.readlines()
    except URLError as e:
        logging.critical("could not reach REST endpoint %s error: %s", uri, str(e.reason), exc_info=True)
        raise
    except BadStatusLine as e:
        logging.critical("REST endpoint died %s error: %s", uri, str(e.line), exc_info=True)


def get_telemetry ():
    """get system resource telemetry on a Mesos slave via psutil"""
    telemetry = OrderedDict()

    telemetry["ip_addr"] = socket.gethostbyname(socket.gethostname())

    telemetry["mem_free"] =  psutil.virtual_memory().free

    telemetry["cpu_num"] = psutil.NUM_CPUS

    x = psutil.cpu_times()
    telemetry["cpu_times"] = OrderedDict([ ("user", x.user), ("system", x.system), ("idle", x.idle) ])

    x = psutil.disk_usage("/tmp")
    telemetry["disk_usage"] = OrderedDict([ ("free", x.free), ("percent", x.percent) ])

    x = psutil.disk_io_counters()
    telemetry["disk_io"] = OrderedDict([ ("read_count", x.read_count), ("write_count", x.write_count), ("read_bytes", x.read_bytes), ("write_bytes", x.write_bytes), ("read_time", x.read_time), ("write_time", x.write_time) ])

    x = psutil.network_io_counters()
    telemetry["network_io"] = OrderedDict([ ("bytes_sent", x.bytes_sent), ("bytes_recv", x.bytes_recv), ("packets_sent", x.packets_sent), ("packets_recv", x.packets_recv), ("errin", x.errin), ("errout", x.errout), ("dropin", x.dropin), ("dropout", x.dropout) ])

    return telemetry


def get_master_state (master_uri):
    """get current state, represented as JSON, from the Mesos master"""
    uri = "http://" + master_uri + "/master/state.json"

    try:
        response = urlopen(uri)
        return loads(response.read())
    except URLError as e:
        logging.critical("could not reach REST endpoint %s error: %s", uri, str(e.reason), exc_info=True)
        raise


def get_master_leader (master_uri):
    """get the host:port for the Mesos master leader"""
    state = get_master_state(master_uri)
    return state["leader"].split("@")[1]


def pipe_slave_list (master_uri):
    """report a list of slave IP addr, one per line to stdout -- for building pipes"""
    state = get_master_state(get_master_leader(master_uri))

    for s in state["slaves"]:
        print s["pid"].split("@")[1].split(":")[0] 


if __name__=='__main__':
    pass
