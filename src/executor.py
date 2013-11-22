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


from ga import APP_NAME, Individual, Population
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
        self.prefix = None
        self.shard_id = None
        self.pop = None
        self.ff_name = None
        self.n_pop = None
        self.term_limit = None


    def start (self):
        """start the service"""
        self.server.serve_forever()


    def stop (self, *args, **kwargs):
        """stop the service"""
        print "%s: executor service stopping... you can safely ignore any exceptions that follow." % (APP_NAME)
        self.server.stop()


    def shard_config (self, *args, **kwargs):
        """configure the service to run a shard"""
        payload = args[0]
        self.prefix = payload["prefix"]
        self.shard_id = payload["shard_id"]
        print "%s: configuring shard %s prefix %s" % (APP_NAME, self.shard_id, self.prefix)


    def pop_init (self, *args, **kwargs):
        """initialize a Population of unique Individuals on this shard at generation 0"""
        payload = args[0]
        print "%s: initializing population" % (APP_NAME)

        self.ff_name = payload["ff_name"]
        self.n_pop = payload["n_pop"]
        self.term_limit = payload["term_limit"]

        self.pop = Population(Individual(), self.ff_name, self.prefix, self.n_pop, self.term_limit)
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


    def _response_handler (self, env, start_response):
        """handle HTTP request/response"""
        uri_path = env['PATH_INFO']
        body = queue.Queue()

        ##########################################
        # shard lifecycle endpoints

        if uri_path == '/shard/config':
            # configure the service to run a shard
            start_response('200 OK', [('Content-Type', 'text/plain')])

            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.shard_config, payload)
            gl.start()

            body.put("Bokay\r\n")

        elif uri_path == '/shard/persist':
            # checkpoint the service state to durable storage
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/shard/recover':
            # restart the service, recovering from the most recent checkpoint
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        ##########################################
        # HashRing endpoints

        elif uri_path == '/ring/init':
            # initialize the HashRing
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/ring/add':
            # add a node to the HashRing
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/ring/del':
            # delete a node from the HashRing
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        ##########################################
        # evolution endpoints

        elif uri_path == '/pop/init':
            # initialize the Population subset on this shard
            start_response('200 OK', [('Content-Type', 'text/plain')])

            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_init, payload)
            gl.start()

            body.put("Bokay\r\n")

        elif uri_path == '/pop/hist':
            # calculate a partial histogram for the fitness distribution
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/next':
            # attempt to run another generation
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/reify':
            # test/add a newly generated Individual into the Population (birth)
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/evict':
            # remove an Individual from the Population (death)
            payload = loads(env['wsgi.input'].read())
            print "POST", payload

            ## TODO

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")

        elif uri_path == '/pop/enum':
            # enumerate the Individuals in this shard of the Population
            payload = loads(env['wsgi.input'].read())
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
            start_response('200 OK', [('Content-Type', 'text/plain')])

            gl = Greenlet(self.stop)
            gl.start_later(1)

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
    print "%s: executor service running on %d..." % (APP_NAME, port)

    # "And now, a public service announcement on behalf of the Greenlet Party..."
    monkey.patch_all()

    # launch service
    exe = Executor(port=port)
    exe.start()

