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


from json import loads
from urllib2 import urlopen
import sys


######################################################################
## utilities

def get_master_state (master_uri):
    """get current state, represented as JSON, from the Mesos master"""
    response = urlopen("http://" + master_uri + "/master/state.json")
    return loads(response.read())


def get_master_leader (master_uri):
    """get the host:port for the Mesos master leader"""
    state = get_master_state(master_uri)
    return state["leader"].split("@")[1]


def get_slave_list (master_uri):
    """get a space-separated list of slave IP addr"""
    state = get_master_state(get_master_leader(master_uri))
    slaves = state["slaves"]
    return " ".join([ s["pid"].split("@")[1].split(":")[0] for s in slaves ])


if __name__=='__main__':
    master_uri = sys.argv[1]
    print get_slave_list(master_uri)
