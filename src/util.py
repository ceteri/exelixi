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


from httplib import BadStatusLine
from importlib import import_module
from json import dumps
from random import random
from urllib2 import urlopen, Request, URLError
import logging


######################################################################
## utilities

def instantiate_class (class_path):
    """instantiate a class from the given package.class name"""
    module_name, class_name = class_path.split(".")
    return getattr(import_module(module_name), class_name)()


def post_distrib_rest (prefix, shard_id, exe_uri, path, base_msg):
    """POST a JSON-based message to a REST endpoint on a shard"""
    msg = base_msg.copy()

    # populate credentials
    msg["prefix"] = prefix
    msg["shard_id"] = shard_id

    # POST to the REST endpoint
    uri = "http://" + exe_uri + "/" + path
    req = Request(uri)
    req.add_header('Content-Type', 'application/json')

    logging.debug("send %s %s", exe_uri, path)
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


if __name__=='__main__':
    pass
