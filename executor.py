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


from ga import Individual, Population
from gevent import monkey, queue, wsgi, Greenlet
from hashring import HashRing
from json import loads
import sys


######################################################################
## class definitions

class Executor (object):
    # http://www.gevent.org/gevent.wsgi.html
    # http://toastdriven.com/blog/2011/jul/31/gevent-long-polling-you/
    # http://blog.pythonisito.com/2012/07/gevent-and-greenlets.html

    def __init__ (self, port=9311):
        self.server = wsgi.WSGIServer(('', port), self._response_handler)
        self.pop = None


    def start (self):
        """start the service"""
        self.server.serve_forever()


    def stop (self, *args, **kwargs):
        """stop the service"""
        print "Exelixi: executor service stopping... you can safely ignore any exceptions that follow."
        self.server.stop()


    def _response_handler (self, env, start_response):
        """handle HTTP request/response"""
        uri_path = env['PATH_INFO']
        post_input = env['wsgi.input'].read()
        body = queue.Queue()

        ##########################################
        # shard lifecycle endpoints

        if uri_path == '/shard/config':
            # configure the service
            payload = loads(post_input)
            print "POST", payload

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/shard/persist':
            # checkpoint the service state to durable storage
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/shard/recover':
            # restart the service, recovering from the most recent checkpoint
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        ##########################################
        # HashRing endpoints

        elif uri_path == '/ring/init':
            # initialize the HashRing
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/ring/add':
            # add a node to the HashRing
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/ring/del':
            # delete a node from the HashRing
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        ##########################################
        # evolution endpoints

        elif uri_path == '/pop/init':
            # initialize the Population subset on this shard
            payload = loads(post_input)
            print "POST", payload

            start_response('200 OK', [('Content-Type', 'text/plain')])

            ## TODO
            # initialize a Population of unique Individuals on this shard at generation 0
            self.pop = Population(Individual(), prefix="/tmp/exelixi", n_pop=20, term_limit=1.0e-04)
            self.pop.populate(0)

            # iterate N times or until a "good enough" solution is found
            # NB: change this
            n_gen = 5

            for current_gen in xrange(n_gen):
                fitness_cutoff = self.pop.get_fitness_cutoff(selection_rate=0.2)
                self.pop.next_generation(current_gen, fitness_cutoff, mutation_rate=0.02)

                if self.pop.test_termination(current_gen):
                    break

            # report summary
            self.pop.report_summary()

            body.put("Bokay\r\n")

        elif uri_path == '/pop/hist':
            # calculate a partial histogram for the fitness distribution
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/next':
            # attempt to run another generation
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/reify':
            # test/add a newly generated Individual into the Population (birth)
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/evict':
            # remove an Individual from the Population (death)
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/enum':
            # enumerate the Individuals in this shard of the Population
            payload = loads(post_input)
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        ##########################################
        # utility endpoints

        elif uri_path == '/':
            # dump info about the service in general
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put(str(env) + "\r\n")

        elif uri_path == '/stop':
            # shutdown the service
            gl = Greenlet(self.stop)
            gl.start_later(1)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Goodbye\r\n")

        else:
            # ne znayu
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            body.put('Not Found\r\n')

        body.put(StopIteration)
        return body


if __name__=='__main__':
    ## Executor operations:

    # parse command line options
    port = int(sys.argv[1])
    print "Exelixi: executor service running on %d..." % port

    # "And now, a public service announcement on behalf of the Greenlet Party..."
    monkey.patch_all()

    # launch service
    exe = Executor(port=port)
    exe.start()
