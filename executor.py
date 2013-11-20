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


from gevent import wsgi, Greenlet
import sys


######################################################################
## class definitions

class Executor (object):
    def __init__ (self, port=9311):
        self.server = wsgi.WSGIServer(('', port), self._response_handler)


    def start (self):
        """start the service"""
        self.server.serve_forever()


    def stop (self, *args, **kwargs):
        """stop the service"""
        print "Exelixi: executor service stopping... you can safely ignore any exceptions that follow."
        self.server.stop()


    # REST endpoints TODO:
    # config
    # persist
    # recover

    # ring/init
    # ring/add
    # ring/del

    # pop/init
    # pop/hist
    # pop/nextgen
    # pop/reify
    # pop/evict
    # pop/report


    def _response_handler (self, env, start_response):
        """handle HTTP request/response"""
        uri_path = env['PATH_INFO']
        post_input = env['wsgi.input'].read()

        if uri_path == '/':
            # dump info
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [str(env) + "\r\n"]
        elif uri_path == '/stop':
            # stop service
            gl = Greenlet(self.stop)
            gl.start_later(1)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            return ["Goodbye\r\n"]
        else:
            # ne znayu
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return ['Not Found\r\n']


if __name__=='__main__':
    ## Executor operations:

    # parse command line options
    port = int(sys.argv[1])
    print 'Exelixi: executor service running on %d...' % port

    # launch service
    exe = Executor(port=port)
    exe.start()
