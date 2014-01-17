#!/usr/bin/env python
# encoding: utf-8

from collections import namedtuple
from gevent import Greenlet
from json import dumps, loads
from os.path import abspath
from service import UnitOfWork
from uow import UnitOfWorkFactory
import logging
import sys


######################################################################
## class definitions

class Container (object):
    """Container for a scikit-learn UnitOfWork"""

    def __init__ (self):
        """constructor"""
        self.param_space = []

        ## NB: override to specify the data source
        self.file_name = abspath('dat/foo.tsv')
        ## NB: override to define the fields of a result tuple
        self.Result = namedtuple('Foo', ['bar', 'ugh'])


    def data_load (self, file_name):
        """load the specified data file"""
        ## NB: override to load the data file
        self.param_space.append(23)


    def run_calc (self, params):
        """run calculations based on the given param space element"""
        ## NB: override to calculate a job
        return self.Result(93, 11)


class SklearnFactory (UnitOfWorkFactory):
    """UnitOfWorkFactory definition for scikit-learn jobs"""

    def __init__ (self):
        #super(UnitOfWorkFactory, self).__init__()
        pass

    def instantiate_uow (self, uow_name, prefix):
        return Sklearn(uow_name, prefix, Container())


class Sklearn (UnitOfWork):
    """UnitOfWork definition for scikit-learn jobs"""
    def __init__ (self, uow_name, prefix, container):
        super(Sklearn, self).__init__(uow_name, prefix)
        self._shard = {}

        self._container = container
        self.results = []


    def perform_task (self, payload):
        """perform a task consumed from the Worker.task_queue"""
        logging.debug(payload)

        if "job" in payload:
            result = self._container.run_calc(payload["job"])
            self.results.append(result)
            logging.debug(result)
        elif "nop" in payload:
            pass


    def orchestrate (self, framework):
        """initialize shards, then iterate until all percentiles are trained"""
        framework.send_ring_rest("shard/init", {})
        framework.send_ring_rest("data/load", { "file": self._container.file_name })

        self._container.data_load(self._container.file_name)
        framework.phase_barrier()

        while len(self._container.param_space) > 0:
            for shard_id, shard_uri in framework.get_worker_list():
                if len(self._container.param_space) > 0:
                    params = self._container.param_space.pop(0)
                    framework.send_worker_rest(shard_id, shard_uri, "calc/run", { "params": params })

        framework.phase_barrier()

        # report the results
        needs_header = True

        for shard_msg in framework.send_ring_rest("shard/dump", {}):
            payload = loads(shard_msg)

            if needs_header:
                print "\t".join(payload["fields"])
                needs_header = False

            for result in payload["results"]:
                print "\t".join(map(lambda x: str(x), result))


    def handle_endpoints (self, worker, uri_path, env, start_response, body):
        """UnitOfWork REST endpoints, delegated from the Worker"""
        if uri_path == '/shard/init':
            # initialize the shard
            Greenlet(self.shard_init, worker, env, start_response, body).start()
            return True
        elif uri_path == '/data/load':
            # load the data
            Greenlet(self.data_load, worker, env, start_response, body).start()
            return True
        elif uri_path == '/calc/run':
            # run the calculations
            Greenlet(self.calc_run, worker, env, start_response, body).start()
            return True
        elif uri_path == '/shard/dump':
            # dump the results
            Greenlet(self.shard_dump, worker, env, start_response, body).start()
            return True
        else:
            return False


    ######################################################################
    ## job-specific REST endpoints implemented as gevent coroutines

    def shard_init (self, *args, **kwargs):
        """initialize a shard"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            self.set_ring(worker.shard_id, worker.ring)
            worker.prep_task_queue()

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)


    def data_load (self, *args, **kwargs):
        """prepare for calculations"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            with worker.wrap_task_event():
                # HTTP response first, then initiate long-running task
                start_response('200 OK', [('Content-Type', 'text/plain')])
                body.put("Bokay\r\n")
                body.put(StopIteration)

                # load the data file
                logging.debug(payload["file"])
                self._container.data_load(payload["file"])

                # put a NOP into the queue, so we'll have something to join on
                worker.put_task_queue({ "nop": True })


    def calc_run (self, *args, **kwargs):
        """enqueue one calculation"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            with worker.wrap_task_event():
                # caller expects JSON response
                start_response('200 OK', [('Content-Type', 'application/json')])
                body.put(dumps({ "ok": 1 }))
                body.put("\r\n")
                body.put(StopIteration)

                # put the params into the queue
                worker.put_task_queue({ "job": payload["params"] })


    def shard_dump (self, *args, **kwargs):
        """dump the results"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps({ "fields": self.results[0]._fields, "results": self.results }))
            body.put("\r\n")
            body.put(StopIteration)


if __name__=='__main__':
    ## test GA in standalone-mode, without distributed services
    pass
