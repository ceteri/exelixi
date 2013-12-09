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


from gevent import monkey, spawn, wsgi, Greenlet
from gevent.event import Event
from gevent.queue import JoinableQueue
from json import dumps, loads
from util import instantiate_class, post_distrib_rest
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
        # REST services
        monkey.patch_all()
        self.server = wsgi.WSGIServer(('', int(port)), self._response_handler, log=None)
        self.is_config = False

        # sharding
        self.prefix = None
        self.shard_id = None
        self.ring = None

        # concurrency
        self.task_event = None
        self.task_queue = None

        # UnitOfWork
        self._uow = None


    def _get_response_context (self, args):
        """decode the WSGI response context from the Greenlet args"""
        env = args[0]
        msg = env["wsgi.input"].read()
        payload = loads(msg)
        start_response = args[1]
        body = args[2]

        return payload, start_response, body


    def _bad_auth (self, payload, start_response, body):
        """UoW caller did not provide the correct credentials to access this shard"""
        start_response('403 Forbidden', [('Content-Type', 'text/plain')])
        body.put('Forbidden\r\n')
        body.put(StopIteration)

        logging.error("incorrect shard %s prefix %s", payload["shard_id"], payload["prefix"])


    def queue_consumer (self):
        """consume/serve requests until the task_queue empties"""
        while True:
            payload = self.task_queue.get()

            try:
                self._uow.perform_task(payload)
            finally:
                self.task_queue.task_done()


    def shard_start (self):
        """start the service"""
        self.server.serve_forever()


    def shard_stop (self, *args, **kwargs):
        """stop the service"""
        payload = args[0]

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            logging.info("executor service stopping... you can safely ignore any exceptions that follow")
            self.server.stop()
        else:
            # returns incorrect response in this case, to avoid exception
            logging.error("incorrect shard %s prefix %s", payload["shard_id"], payload["prefix"])


    def shard_config (self, *args, **kwargs):
        """configure the service to run a shard"""
        payload, start_response, body = self._get_response_context(args)

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

            ff_name = payload["ff_name"]
            logging.info("initializing population based on %s", ff_name)

            ff = instantiate_class(ff_name)
            self._uow = ff.instantiate_uow(ff_name, self.prefix)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            logging.info("configuring shard %s prefix %s", self.shard_id, self.prefix)


    def shard_wait (self, *args, **kwargs):
        """wait until all shards finished sending task_queue requests"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            if self.task_event:
                self.task_event.wait()

            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, start_response, body)


    def shard_join (self, *args, **kwargs):
        """join on the task_queue, as a barrier to wait until it empties"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("join queue...\r\n")

            ## NB: TODO this step of emptying out the task_queue on
            ## shards could take a while on a large run... perhaps use
            ## a long-polling HTTP request or websocket instead?
            self.task_queue.join()

            body.put("done\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, start_response, body)


    def ring_init (self, *args, **kwargs):
        """initialize the HashRing"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.ring = payload["ring"]

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            logging.info("setting hash ring %s", self.ring)
        else:
            self._bad_auth(payload, body, start_response)


    def _response_handler (self, env, start_response):
        """handle HTTP request/response"""
        uri_path = env["PATH_INFO"]
        body = JoinableQueue()

        ##########################################
        # Worker endpoints

        if uri_path == '/shard/config':
            # configure the service to run a shard
            Greenlet(self.shard_config, env, start_response, body).start()

        elif uri_path == '/shard/wait':
            # wait until all shards have finished sending task_queue requests
            Greenlet(self.shard_wait, env, start_response, body).start()

        elif uri_path == '/shard/join':
            # join on the task_queue, as a barrier to wait until it empties
            Greenlet(self.shard_join, env, start_response, body).start()

        elif uri_path == '/shard/persist':
            ## NB: TODO checkpoint the service state to durable storage
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/shard/recover':
            ## NB: TODO restart the service, recovering from most recent checkpoint
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/shard/stop':
            # shutdown the service
            ## NB: must parse POST data first, to avoid exception
            payload = loads(env["wsgi.input"].read())
            Greenlet(self.shard_stop, payload).start_later(1)

            # HTTP response starts later, to avoid deadlock when server stops
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Goodbye\r\n")
            body.put(StopIteration)

        ##########################################
        # HashRing endpoints

        elif uri_path == '/ring/init':
            # initialize the HashRing
            Greenlet(self.ring_init, env, start_response, body).start()

        elif uri_path == '/ring/add':
            ## NB: TODO add a node to the HashRing
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

        elif uri_path == '/ring/del':
            ## NB: TODO delete a node from the HashRing
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

        elif self._uow and self._uow.handle_endpoints(self, uri_path, env, start_response, body):
            pass

        else:
            # ne znayu
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            body.put('Not Found\r\n')
            body.put(StopIteration)

        return body


    ######################################################################
    ## NB: TODO refactor GA-specific code into UnitOfWork design pattern

    def pop_init (self, *args, **kwargs):
        """initialize a Population of unique Individuals on this shard"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self._uow.set_ring(self.shard_id, self.ring)

            # prepare task_queue for another set of distributed tasks
            self.task_queue = JoinableQueue()
            spawn(self.queue_consumer)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, start_response, body)


    def pop_gen (self, *args, **kwargs):
        """create generation 0 of Individuals in this shard of the Population"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.task_event = Event()

            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            self._uow.populate(0)

            self.task_event.set()
            self.task_event = None
        else:
            self._bad_auth(payload, start_response, body)


    def pop_hist (self, *args, **kwargs):
        """calculate a partial histogram for the fitness distribution"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps({ "total_indiv": self._uow.total_indiv, "hist": self._uow.get_part_hist() }))
            body.put("\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, start_response, body)


    def pop_next (self, *args, **kwargs):
        """iterate N times or until a 'good enough' solution is found"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.task_event = Event()

            # HTTP response first, then initiate long-running task
            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)

            current_gen = payload["current_gen"]
            fitness_cutoff = payload["fitness_cutoff"]
            self._uow.next_generation(current_gen, fitness_cutoff)

            self.task_event.set()
            self.task_event = None
        else:
            self._bad_auth(payload, start_response, body)


    def pop_enum (self, *args, **kwargs):
        """enumerate the Individuals in this shard of the Population"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            fitness_cutoff = payload["fitness_cutoff"]

            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps(self._uow.enum(fitness_cutoff)))
            body.put("\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, start_response, body)


    def pop_reify (self, *args, **kwargs):
        """test/add a newly generated Individual into the Population (birth)"""
        payload, start_response, body = self._get_response_context(args)

        if (self.prefix == payload["prefix"]) and (self.shard_id == payload["shard_id"]):
            self.task_queue.put_nowait(payload)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)
        else:
            self._bad_auth(payload, start_response, body)


class Framework (object):
    def __init__ (self, ff_name, prefix="/tmp/exelixi"):
        """initialize the system parameters, which represent operational state"""
        self.uuid = uuid1().hex
        self.prefix = prefix + "/" + self.uuid
        logging.info("prefix: %s", self.prefix)

        print ff_name
        self.ff_name = ff_name
        ff = instantiate_class(self.ff_name)
        self._uow = ff.instantiate_uow(self.ff_name, self.prefix)

        self._shard_assoc = None
        self._ring = None


    def _gen_shard_id (self, i, n):
        """generate a shard_id"""
        s = str(i)
        z = ''.join([ '0' for _ in xrange(len(str(n)) - len(s)) ])
        return "shard/" + z + s


    def set_exe_list (self, exe_list, exe_info=None):
        """associate shards with Executors"""
        self._shard_assoc = {}

        for i in xrange(len(exe_list)):
            shard_id = self._gen_shard_id(i, len(exe_list))

            if not exe_info:
                self._shard_assoc[shard_id] = [exe_list[i], None]
            else:
                self._shard_assoc[shard_id] = [exe_list[i], exe_info[i]]

        logging.info("set executor list: %s", str(self._shard_assoc))


    def send_ring_rest (self, path, base_msg):
        """access a REST endpoint on each of the shards"""
        json_str = []

        for shard_id, (exe_uri, exe_info) in self._shard_assoc.items():
            lines = post_distrib_rest(self.prefix, shard_id, exe_uri, path, base_msg)
            json_str.append(lines[0])

        return json_str


    def shard_barrier (self):
        """
        implements a two-phase barrier to (1) wait until all shards
        have finished sending task_queue requests, then (2) join on
        each task_queue, to wait until it has emptied
        """
        self.send_ring_rest("shard/wait", {})
        self.send_ring_rest("shard/join", {})


    def orchestrate (self):
        """orchestrate a unit of work distributed across the hash ring via REST endpoints"""

        # configure the shards and the hash ring
        self.send_ring_rest("shard/config", { "ff_name": self.ff_name })

        self._ring = { shard_id: exe_uri for shard_id, (exe_uri, exe_info) in self._shard_assoc.items() }
        self.send_ring_rest("ring/init", { "ring": self._ring })

        # distribute the UnitOfWork tasks
        self._uow.orchestrate(self)

        # shutdown
        self.send_ring_rest("shard/stop", {})


class UnitOfWork (object):
    def set_ring (self, shard_id, ring):
        """initialize the HashRing"""
        pass

    def perform_task (self, payload):
        """perform a task consumed from the Worker.task_queue"""
        pass

    def orchestrate (self, framework):
        """orchestrate Workers via REST endpoints"""
        pass

    def handle_endpoints (self, worker, uri_path, env, start_response, body):
        """UnitOfWork REST endpoints"""
        pass


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
    print "framework launching at %s based on %s..." % (fra.prefix, ff_name)

    fra.set_exe_list([exe_uri])
    fra.orchestrate()
