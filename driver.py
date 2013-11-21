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


from json import dumps
from urllib2 import Request, urlopen
import sys


######################################################################
## JSON-based test driver for REST endpoints

if __name__=='__main__':
    uri = sys.argv[1]
    path = sys.argv[2]
    test = sys.argv[3]

    filename = test + "/" + path + ".json"
    data = ""

    with open (filename, "r") as f:
        data = f.read()

    req = Request("http://" + uri + "/" + path)
    req.add_header('Content-Type', 'application/json')

    f = urlopen(req, dumps(data))
    print f.read()
