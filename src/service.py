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


from ga import instantiate_class, APP_NAME, Individual, Population
from gevent import monkey, queue, wsgi, Greenlet
from hashring import HashRing
from json import dumps, loads
from uuid import uuid1
import sys


######################################################################
## class definitions

class Worker (object):
    # http://www.gevent.org/gevent.wsgi.html
    # http://toastdriven.com/blog/2011/jul/31/gevent-long-polling-you/
    # http://blog.pythonisito.com/2012/07/gevent-and-greenlets.html

    DEFAULT_PORT = 9311


    def __init__ (self, port=Worker.DEFAULT_PORT):
        monkey.patch_all()
        self.server = wsgi.WSGIServer(('', port), self._response_handler)
        self.is_config = False
        self.prefix = None
        self.shard_id = None
        self.hash_ring = None
        self.ff_name = None
        self.pop = None


    def start (self):
        """start the service"""
        self.server.serve_forever()


    def stop (self, *args, **kwargs):
        """stop the service"""
        payload = args[0]
        body = args[1]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            print "%s: executor service stopping... you can safely ignore any exceptions that follow." % (APP_NAME)
            self.server.stop()
        else:
            # NB: you have dialed a wrong number!
            # returns incorrect response in this case, to avoid exception
            print "%s: incorrect shard %s prefix %s" % (APP_NAME, payload["shard_id"], payload["prefix"])


    def shard_config (self, *args, **kwargs):
        """configure the service to run a shard"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if self.is_config:
            # somebody contact security...
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            body.put("Denied, executor already in a configured state\r\n")
            body.put(StopIteration)
            print "%s: denied configuring shard %s prefix %s" % (APP_NAME, self.shard_id, self.prefix)
        else:
            self.is_config = True
            self.prefix = payload["prefix"]
            self.shard_id = payload["shard_id"]

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
            print "%s: configuring shard %s prefix %s" % (APP_NAME, self.shard_id, self.prefix)


    def pop_init (self, *args, **kwargs):
        """initialize a Population of unique Individuals on this shard at generation 0"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            self.ff_name = payload["ff_name"]
            print "%s: initializing population based on %s" % (APP_NAME, self.ff_name)
            self.pop = Population(Individual(), self.ff_name, self.prefix, self.hash_ring)
            self.pop.populate(0)
        else:
            self.bad_auth(payload, body, start_response)


    def pop_hist (self, *args, **kwargs):
        """calculate a partial histogram for the fitness distribution"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps(self.pop.get_part_hist()))
            body.put("\r\n")
            body.put(StopIteration)
        else:
            self.bad_auth(payload, body, start_response)


    def pop_next (self, *args, **kwargs):
        """iterate N times or until a 'good enough' solution is found"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            current_gen = payload["current_gen"]
            fitness_cutoff = payload["fitness_cutoff"]
            self.pop.next_generation(current_gen, fitness_cutoff)
        else:
            self.bad_auth(payload, body, start_response)


    def _response_handler (self, env, start_response):
        """handle HTTP request/response"""
        uri_path = env['PATH_INFO']
        body = queue.Queue()

        ## NB: these handler cases can be collapsed into a common pattern
        ## except for config/stop -- later

        ##########################################
        # shard lifecycle endpoints

        if uri_path == '/shard/config':
            # configure the service to run a shard
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.shard_config, payload, body, start_response)
            gl.start()

        elif uri_path == '/shard/persist':
            # checkpoint the service state to durable storage
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/shard/recover':
            # restart the service, recovering from the most recent checkpoint
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        ##########################################
        # HashRing endpoints

        elif uri_path == '/ring/init':
            # initialize the HashRing
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/ring/add':
            # add a node to the HashRing
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/ring/del':
            # delete a node from the HashRing
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        ##########################################
        # evolution endpoints

        elif uri_path == '/pop/init':
            # initialize the Population subset on this shard
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_init, payload, body, start_response)
            gl.start()

        elif uri_path == '/pop/hist':
            # calculate a partial histogram for the fitness distribution
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_hist, payload, body, start_response)
            gl.start()

        elif uri_path == '/pop/next':
            # attempt to run another generation
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_next, payload, body, start_response)
            gl.start()

        elif uri_path == '/pop/reify':
            # test/add a newly generated Individual into the Population (birth)
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/pop/evict':
            # remove an Individual from the Population (death)
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/pop/enum':
            # enumerate the Individuals in this shard of the Population
            payload = loads(env['wsgi.input'].read())
            print "POST", payload
            ## TODO
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        ##########################################
        # utility endpoints

        elif uri_path == '/':
            # dump info about the service in general
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put(str(env) + "\r\n")
            body.put(StopIteration)

        elif uri_path == '/stop':
            # shutdown the service
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.stop, payload, body)
            gl.start_later(1)
            # HTTP response must start here, to avoid failure when server stops
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Goodbye\r\n")
            body.put(StopIteration)

        else:
            # ne znayu
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            body.put('Not Found\r\n')
            body.put(StopIteration)

        return body


class Framework (object):
    def __init__ (self, ff_name, prefix="/tmp/exelixi/"):
        # system parameters, for representing operational state
        self.feature_factory = instantiate_class(ff_name)
        self.uuid = uuid1().hex
        self.prefix = prefix + self.uuid
        self.hash_ring = None
        self.n_gen = self.feature_factory.n_gen
        self.current_gen = 0


if __name__=='__main__':
    ## Framework operations:

    # parse command line options
    if len(sys.argv) < 2:
        print "usage:\n  %s <feature factory>" % (sys.argv[0])
        sys.exit(1)

    ff_name = sys.argv[1]
    ff = instantiate_class(ff_name)

    fra = Framework(ff_name)
    print "%s: framework launching at %s based on %s..." % (APP_NAME, fra.prefix, ff_name)

    ## NB: standalone mode
    # initialize a Population of unique Individuals at generation 0
    pop = Population(Individual(), ff_name, prefix=fra.prefix, hash_ring=fra.hash_ring)
    pop.populate(fra.current_gen)

    # iterate N times or until a "good enough" solution is found

    while fra.current_gen < fra.n_gen:
        hist = pop.get_part_hist()

        if pop.test_termination(fra.current_gen, hist):
            break

        fitness_cutoff = pop.get_fitness_cutoff(hist)
        pop.next_generation(fra.current_gen, fitness_cutoff)
        fra.current_gen += 1
        ## NB: save state to Zookeeper

    # report summary
    pop.report_summary()
