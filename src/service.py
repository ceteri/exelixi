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


from ga import instantiate_class, post_exe_rest, APP_NAME, Individual, Population
from gevent import monkey, spawn, wsgi, Greenlet
from gevent.event import Event
from gevent.queue import JoinableQueue, Queue
from hashring import HashRing
from itertools import chain
from json import dumps, loads
from urllib2 import urlopen, Request
from uuid import uuid1
import logging
import sys


######################################################################
## class definitions

class Worker (object):
    # http://www.gevent.org/gevent.wsgi.html
    # http://toastdriven.com/blog/2011/jul/31/gevent-long-polling-you/
    # http://blog.pythonisito.com/2012/07/gevent-and-greenlets.html

    DEFAULT_PORT = "9311"


    def __init__ (self, port=DEFAULT_PORT):
        monkey.patch_all()
        self.server = wsgi.WSGIServer(('', int(port)), self._response_handler, log=None)
        self.is_config = False
        self.prefix = None
        self.shard_id = None
        self.ring = None
        self.ff_name = None
        self.pop = None
        self.evt = None
        self.reify_queue = None


    def start (self):
        """start the service"""
        self.server.serve_forever()


    def stop (self, *args, **kwargs):
        """stop the service"""
        payload = args[0]
        body = args[1]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            logging.info("executor service stopping... you can safely ignore any exceptions that follow")
            self.server.stop()
        else:
            # returns incorrect response in this case, to avoid exception
            logging.error("incorrect shard %s prefix %s", payload["shard_id"], payload["prefix"])


    def _bad_auth (self, payload, body, start_response):
        """Framework did not provide the correct credentials to access this shard"""
        start_response('403 Forbidden', [('Content-Type', 'text/plain')])
        body.put('Forbidden\r\n')
        body.put(StopIteration)

        logging.error("incorrect shard %s prefix %s", payload["shard_id"], payload["prefix"])


    def reify_consumer (self):
        """consume/serve reify requests until the queue empties"""

        while True:
            payload = self.reify_queue.get()

            try:
                key = payload["key"]
                gen = payload["gen"]
                feature_set = payload["feature_set"]
                self.pop.receive_reify(key, gen, feature_set)
            finally:
                self.reify_queue.task_done()


    def shard_config (self, *args, **kwargs):
        """configure the service to run a shard"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if self.is_config:
            # hey, somebody call security...
            start_response('403 Forbidden', [('Content-Type', 'text/plain')])
            body.put("Forbidden, executor already in a configured state\r\n")
            body.put(StopIteration)

            logging.warning("denied configuring shard %s prefix %s", self.shard_id, self.prefix)
        else:
            self.is_config = True
            self.prefix = payload["prefix"]
            self.shard_id = payload["shard_id"]

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            logging.info("configuring shard %s prefix %s", self.shard_id, self.prefix)


    def ring_init (self, *args, **kwargs):
        """initialize the HashRing"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.ring = payload["ring"]

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            logging.info("setting hash ring %s", self.ring)
        else:
            self._bad_auth(payload, body, start_response)


    def pop_init (self, *args, **kwargs):
        """initialize a Population of unique Individuals on this shard"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.ff_name = payload["ff_name"]
            logging.info("initializing population based on %s", self.ff_name)

            self.pop = Population(Individual(), self.ff_name, self.prefix)
            self.pop.set_ring(self.shard_id, self.ring)

            self.reify_queue = JoinableQueue()
            spawn(self.reify_consumer)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, body, start_response)


    def pop_gen (self, *args, **kwargs):
        """create generation 0 of Individuals in this shard of the Population"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.evt = Event()

            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            self.pop.populate(0)

            self.evt.set()
            self.evt = None
        else:
            self._bad_auth(payload, body, start_response)


    def pop_wait (self, *args, **kwargs):
        """wait until all shards finished sending reify requests"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            if self.evt:
                self.evt.wait()

            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, body, start_response)


    def pop_join (self, *args, **kwargs):
        """join on the reify queue, to wait until it empties"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("join queue...\r\n")

            self.reify_queue.join()

            ## NB: TODO this step of emptying out the reify queues on
            ## shards could take a while on a large run... perhaps use
            ## a long-polling HTTP request or websocket instead?

            body.put("done\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, body, start_response)


    def pop_hist (self, *args, **kwargs):
        """calculate a partial histogram for the fitness distribution"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps({ "total_indiv": self.pop.total_indiv, "hist": self.pop.get_part_hist() }))
            body.put("\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, body, start_response)


    def pop_next (self, *args, **kwargs):
        """iterate N times or until a 'good enough' solution is found"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.evt = Event()

            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            current_gen = payload["current_gen"]
            fitness_cutoff = payload["fitness_cutoff"]
            self.pop.next_generation(current_gen, fitness_cutoff)

            self.evt.set()
            self.evt = None
        else:
            self._bad_auth(payload, body, start_response)


    def pop_enum (self, *args, **kwargs):
        """enumerate the Individuals in this shard of the Population"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            fitness_cutoff = payload["fitness_cutoff"]

            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps(self.pop.enum(fitness_cutoff)))
            body.put("\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, body, start_response)


    def pop_reify (self, *args, **kwargs):
        """test/add a newly generated Individual into the Population (birth)"""
        payload = args[0]
        body = args[1]
        start_response = args[2]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.reify_queue.put_nowait(payload)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, body, start_response)


    def _response_handler (self, env, start_response):
        """handle HTTP request/response"""
        uri_path = env['PATH_INFO']
        body = Queue()

        ## NB: TODO handler cases could be collapsed into a common
        ## pattern, except for config/stop

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
            gl = Greenlet(self.ring_init, payload, body, start_response)
            gl.start()

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

        elif uri_path == '/pop/gen':
            # create generation 0 of Individuals in this shard of the
            # Population
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_gen, payload, body, start_response)
            gl.start()

        elif uri_path == '/pop/wait':
            # wait until all shards have finished sending reify requests
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_wait, payload, body, start_response)
            gl.start()

        elif uri_path == '/pop/join':
            # join on the reify queue, to wait until it empties
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_join, payload, body, start_response)
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

        elif uri_path == '/pop/enum':
            # enumerate the Individuals in this shard of the Population
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_enum, payload, body, start_response)
            gl.start()

        elif uri_path == '/pop/reify':
            # test/add a new Individual into the Population (birth)
            payload = loads(env['wsgi.input'].read())
            gl = Greenlet(self.pop_reify, payload, body, start_response)
            gl.start()

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
            # HTTP response must start here, to avoid failure when
            # server stops
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
    def __init__ (self, ff_name, prefix="/tmp/exelixi"):
        # system parameters, for representing operational state
        self.ff_name = ff_name
        self.feature_factory = instantiate_class(ff_name)

        self.uuid = uuid1().hex
        self.prefix = prefix + "/" + self.uuid
        logging.info("prefix: %s", self.prefix)

        self.n_gen = self.feature_factory.n_gen
        self.current_gen = 0
        self._shard_assoc = None


    def _gen_shard_id (self, i, n):
        """generate a shard_id"""
        s = str(i)
        z = ''.join([ '0' for _ in xrange(len(str(n)) - len(s)) ])
        return "shard/" + z + s


    def set_exe_list (self, exe_list, exe_info=None):
        """associate shards with executors"""
        self._shard_assoc = {}

        for i in xrange(len(exe_list)):
            shard_id = self._gen_shard_id(i, len(exe_list))

            if not exe_info:
                self._shard_assoc[shard_id] = [exe_list[i], None]
            else:
                self._shard_assoc[shard_id] = [exe_list[i], exe_info[i]]

        logging.info("set executor list: %s", str(self._shard_assoc))


    def _send_exe_rest (self, path, base_msg):
        """access a REST endpoint on each of the Executors"""
        json_str = []

        for shard_id, (exe_uri, exe_info) in self._shard_assoc.items():
            lines = post_exe_rest(self.prefix, shard_id, exe_uri, path, base_msg)
            json_str.append(lines[0])

        return json_str


    def aggregate_hist (self, hist, shard_hist):
        """aggregate the values of a shard's partial histogram into the full histogram"""
        for key, val in shard_hist:
            if key not in hist:
                hist[key] = val
            else:
                hist[key] += val


    def orchestrate (self):
        """orchestrate an algorithm run across the hash ring via REST endpoints"""

        # configure the shards and their HashRing
        self._send_exe_rest("shard/config", {})
        ring = { shard_id: exe_uri for shard_id, (exe_uri, exe_info) in self._shard_assoc.items() }
        self._send_exe_rest("ring/init", { "ring": ring })

        # initialize Population of unique Individuals at generation 0,
        # then iterate N times or until a "good enough" solution is
        # found
        pop = Population(Individual(), self.ff_name, prefix=self.prefix)
        self._send_exe_rest("pop/init", { "ff_name": self.ff_name })
        self._send_exe_rest("pop/gen", {})

        while True:
            # test (1) wait until all shards have finished sending
            # reify requests, then (2) join on each reify request
            # queue, to wait until they have emptied
            self._send_exe_rest("pop/wait", {})
            self._send_exe_rest("pop/join", {})

            if self.current_gen == self.n_gen:
                break

            # determine the fitness cutoff threshold
            pop.total_indiv = 0
            hist = {}

            for shard_msg in self._send_exe_rest("pop/hist", {}):
                logging.debug(shard_msg)
                payload = loads(shard_msg)
                pop.total_indiv += payload["total_indiv"]
                self.aggregate_hist(hist, payload["hist"])

            # test for the terminating condition
            if pop.test_termination(self.current_gen, hist):
                break

            ## NB: TODO save Framework state to Zookeeper

            # apply fitness cutoff and breed "children" for the next
            # generation
            fitness_cutoff = pop.get_fitness_cutoff(hist)
            self._send_exe_rest("pop/next", { "current_gen": self.current_gen, "fitness_cutoff": fitness_cutoff })
            self.current_gen += 1

        # report the best Individuals in the final result
        results = []

        for l in self._send_exe_rest("pop/enum", { "fitness_cutoff": fitness_cutoff }):
            results.extend(loads(l))

        results.sort(reverse=True)

        for x in results:
            # print results to stdout
            print "\t".join(x)

        # shutdown
        self._send_exe_rest("stop", {})


class SlaveInfo (object):
    def __init__ (self, offer, task):
        self.host = offer.hostname
        self.slave_id = offer.slave_id.value
        self.task_id = task.task_id.value
        self.executor_id = task.executor.executor_id.value
        self.ip_addr = None
        self.port = None

    def get_exe_uri (self):
        """generate a URI for the service on this Executor"""
        return self.ip_addr + ":" + self.port


    def report (self):
        """report the slave telemetry + state"""
        return "host %s slave %s task %s exe %s ip %s:%s" % (self.host, self.slave_id, str(self.task_id), self.executor_id, self.ip_addr, self.port)


if __name__=='__main__':
    if len(sys.argv) < 2:
        print "usage:\n  %s <host:port> <feature factory>" % (sys.argv[0])
        sys.exit(1)

    exe_uri = sys.argv[1]
    ff_name = sys.argv[2]

    fra = Framework(ff_name)
    print "%s: framework launching at %s based on %s..." % (APP_NAME, fra.prefix, ff_name)

    fra.set_exe_list([exe_uri])
    fra.orchestrate()
