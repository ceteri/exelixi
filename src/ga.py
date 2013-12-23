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


from datrie import Trie
from collections import Counter
from gevent import Greenlet
from hashlib import sha224
from hashring import HashRing
from json import dumps, loads
from monoids import dictm
from random import random, sample
from service import UnitOfWork
from string import ascii_lowercase
from util import instantiate_class, post_distrib_rest
import logging
import sys


######################################################################
## class definitions

class Population (UnitOfWork):
    def __init__ (self, uow_name, prefix, indiv_instance):
        super(Population, self).__init__(uow_name, prefix)

        self.indiv_class = indiv_instance.__class__
        self.total_indiv = 0
        self.current_gen = 0

        self._shard = {}
        self._trie = Trie(ascii_lowercase)


    def perform_task (self, payload):
        """perform a task consumed from the Worker.task_queue"""
        key = payload["key"]
        gen = payload["gen"]
        feature_set = payload["feature_set"]
        self.receive_reify(key, gen, feature_set)


    def orchestrate (self, framework):
        """
        initialize a Population of unique Individuals at generation 0,
        then iterate N times or until a "good enough" solution is found
        """
        framework.send_ring_rest("pop/init", {})
        framework.send_ring_rest("pop/gen", {})

        while True:
            framework.phase_barrier()

            if self.current_gen == self.uow_factory.n_gen:
                break

            # determine the fitness cutoff threshold
            self.total_indiv = 0
            hist = {}

            for shard_msg in framework.send_ring_rest("pop/hist", {}):
                logging.debug(shard_msg)
                payload = loads(shard_msg)
                self.total_indiv += payload["total_indiv"]
                hist = dictm.fold([hist, payload["hist"]])

            # test for the terminating condition
            hist_items = map(lambda x: (float(x[0]), x[1],), sorted(hist.items(), reverse=True))

            if self.test_termination(self.current_gen, hist_items):
                break

            ## NB: TODO save Framework state to Zookeeper

            # apply the fitness cutoff and breed "children" for the
            # next generation
            fitness_cutoff = self.get_fitness_cutoff(hist_items)
            framework.send_ring_rest("pop/next", { "current_gen": self.current_gen, "fitness_cutoff": fitness_cutoff })
            self.current_gen += 1

        # report the best Individuals in the final result
        results = []

        for l in framework.send_ring_rest("pop/enum", { "fitness_cutoff": fitness_cutoff }):
            results.extend(loads(l))

        results.sort(reverse=True)

        for x in results:
            # print results to stdout
            print "\t".join(x)


    def handle_endpoints (self, worker, uri_path, env, start_response, body):
        """UnitOfWork REST endpoints, delegated from the Worker"""
        if uri_path == '/pop/init':
            # initialize the Population subset on this shard
            Greenlet(self.pop_init, worker, env, start_response, body).start()
            return True
        elif uri_path == '/pop/gen':
            # create generation 0 in this shard
            Greenlet(self.pop_gen, worker, env, start_response, body).start()
            return True
        elif uri_path == '/pop/hist':
            # calculate a partial histogram for the fitness distribution
            Greenlet(self.pop_hist, worker, env, start_response, body).start()
            return True
        elif uri_path == '/pop/next':
            # attempt to run another generation
            Greenlet(self.pop_next, worker, env, start_response, body).start()
            return True
        elif uri_path == '/pop/enum':
            # enumerate the Individuals in this shard of the Population
            Greenlet(self.pop_enum, worker, env, start_response, body).start()
            return True
        elif uri_path == '/pop/reify':
            # test/add a new Individual into the Population (birth)
            Greenlet(self.pop_reify, worker, env, start_response, body).start()
            return True
        else:
            return False


    ######################################################################
    ## GA-specific REST endpoints implemented as gevent coroutines

    def pop_init (self, *args, **kwargs):
        """initialize a Population of unique Individuals on this shard"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            self.set_ring(worker.shard_id, worker.ring)
            worker.prep_task_queue()

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)


    def pop_gen (self, *args, **kwargs):
        """create generation 0 of Individuals in this shard of the Population"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            with worker.wrap_task_event():
                # HTTP response first, then initiate long-running task
                start_response('200 OK', [('Content-Type', 'text/plain')])
                body.put("Bokay\r\n")
                body.put(StopIteration)

                self.populate(0)


    def pop_hist (self, *args, **kwargs):
        """calculate a partial histogram for the fitness distribution"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps({ "total_indiv": self.total_indiv, "hist": self.get_part_hist() }))
            body.put("\r\n")
            body.put(StopIteration)


    def pop_next (self, *args, **kwargs):
        """iterate N times or until a 'good enough' solution is found"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            with worker.wrap_task_event():
                # HTTP response first, then initiate long-running task
                start_response('200 OK', [('Content-Type', 'text/plain')])
                body.put("Bokay\r\n")
                body.put(StopIteration)

                current_gen = payload["current_gen"]
                fitness_cutoff = payload["fitness_cutoff"]
                self.next_generation(current_gen, fitness_cutoff)


    def pop_enum (self, *args, **kwargs):
        """enumerate the Individuals in this shard of the Population"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            fitness_cutoff = payload["fitness_cutoff"]

            start_response('200 OK', [('Content-Type', 'application/json')])
            body.put(dumps(self.enum(fitness_cutoff)))
            body.put("\r\n")
            body.put(StopIteration)


    def pop_reify (self, *args, **kwargs):
        """test/add a newly generated Individual into the Population (birth)"""
        worker = args[0]
        payload, start_response, body = worker.get_response_context(args[1:])

        if worker.auth_request(payload, start_response, body):
            worker.put_task_queue(payload)

            start_response('200 OK', [('Content-Type', 'text/plain')])
            body.put("Bokay\r\n")
            body.put(StopIteration)


    ######################################################################
    ## Individual lifecycle within the local subset of the Population

    def populate (self, current_gen):
        """initialize the population"""
        for _ in xrange(self.uow_factory.n_pop):
            # constructor pattern
            indiv = self.indiv_class()
            indiv.populate(current_gen, self.uow_factory.generate_features())

            # add the generated Individual to the Population
            # failure semantics: must filter nulls from initial population
            self.reify(indiv)


    def reify (self, indiv):
        """test/add a newly generated Individual into the Population (birth)"""
        neighbor_shard_id = None
        shard_uri = None

        if self._hash_ring:
            neighbor_shard_id = self._hash_ring.get_node(indiv.key)

            if neighbor_shard_id != self._shard_id:
                shard_uri = self._shard_dict[neighbor_shard_id]

        # distribute the tasks in this phase throughout the HashRing,
        # using a remote task_queue with synchronization based on a
        # barrier pattern

        if shard_uri:
            msg = { "key": indiv.key, "gen": indiv.gen, "feature_set": loads(indiv.get_json_feature_set()) }
            lines = post_distrib_rest(self.prefix, neighbor_shard_id, shard_uri, "pop/reify", msg)
            return False
        else:
            return self._reify_locally(indiv)


    def receive_reify (self, key, gen, feature_set):
        """test/add a received reify request """
        indiv = self.indiv_class()
        indiv.populate(gen, feature_set)
        self._reify_locally(indiv)


    def _reify_locally (self, indiv):
        """test/add a newly generated Individual into the Population locally (birth)"""
        if not (indiv.key in self._trie):
            self._trie[indiv.key] = 1
            self.total_indiv += 1

            # potentially an expensive operation, deferred until remote reification
            indiv.get_fitness(self.uow_factory, force=True)
            self._shard[indiv.key] = indiv

            return True
        else:
            return False


    def evict (self, indiv):
        """remove an Individual from the Population (death)"""
        if indiv.key in self._shard:
            # Individual only needs to be removed locally
            del self._shard[indiv.key]

            # NB: serialize to disk (write behinds)
            url = self._get_storage_path(indiv)


    def get_part_hist (self):
        """tally counts for the partial histogram of the fitness distribution"""
        l = [ round(indiv.get_fitness(self.uow_factory, force=False), self.uow_factory.hist_granularity) for indiv in self._shard.values() ]
        return dict(Counter(l))


    def get_fitness_cutoff (self, hist_items):
        """determine fitness cutoff (bin lower bounds) for the parent selection filter"""
        logging.debug("fit: %s", hist_items)

        n_indiv = sum([ count for bin, count in hist_items ])
        part_sum = 0
        break_next = False

        for bin, count in hist_items:
            if break_next:
                break

            part_sum += count
            percentile = part_sum / float(n_indiv)
            break_next = percentile >= self.uow_factory.selection_rate

        logging.debug("fit: percentile %f part_sum %d n_indiv %d bin %f", percentile, part_sum, n_indiv, bin)
        return bin


    def _get_storage_path (self, indiv):
        """create a path for durable storage of an Individual"""
        return self.prefix + "/" + indiv.key


    def _boost_diversity (self, current_gen, indiv):
        """randomly select other individuals and mutate them, to promote genetic diversity"""
        if self.uow_factory.mutation_rate > random():
            indiv.mutate(self, current_gen, self.uow_factory)
        elif len(self._shard.values()) >= 3:
            # NB: ensure that at least three parents remain in each
            # shard per generation
            self.evict(indiv)


    def _select_parents (self, current_gen, fitness_cutoff):
        """select the parents for the next generation"""
        partition = map(lambda x: (round(x.get_fitness(), self.uow_factory.hist_granularity) > fitness_cutoff, x), self._shard.values())
        good_fit = map(lambda x: x[1], filter(lambda x: x[0], partition))
        poor_fit = map(lambda x: x[1], filter(lambda x: not x[0], partition))

        # randomly select other individuals to promote genetic
        # diversity, while removing the remnant
        for indiv in poor_fit:
            self._boost_diversity(current_gen, indiv)

        return self._shard.values()


    def next_generation (self, current_gen, fitness_cutoff):
        """select/mutate/crossover parents to produce a new generation"""
        parents = self._select_parents(current_gen, fitness_cutoff)

        for _ in xrange(self.uow_factory.n_pop - len(parents)):
            f, m = sample(parents, 2) 
            success = f.breed(self, current_gen, m, self.uow_factory)

        # backfill to replenish / avoid the dreaded Population collapse
        new_count = 0

        for _ in xrange(self.uow_factory.n_pop - len(self._shard.values())):
            # constructor pattern
            indiv = self.indiv_class()
            indiv.populate(current_gen, self.uow_factory.generate_features())
            self.reify(indiv)

        logging.info("gen\t%d\tshard\t%s\tsize\t%d\ttotal\t%d", current_gen, self._shard_id, len(self._shard.values()), self.total_indiv)


    def test_termination (self, current_gen, hist):
        """evaluate the terminating condition for this generation and report progress"""
        return self.uow_factory.test_termination(current_gen, hist, self.total_indiv)


    def enum (self, fitness_cutoff):
        """enum all Individuals that exceed the given fitness cutoff"""
        return [[ "indiv", "%0.4f" % indiv.get_fitness(), str(indiv.gen), indiv.get_json_feature_set() ]
                for indiv in filter(lambda x: x.get_fitness() >= fitness_cutoff, self._shard.values()) ]


class Individual (object):
    def __init__ (self):
        """create an Individual member of the Population"""
        self.gen = None
        self.key = None
        self._feature_set = None
        self._fitness = None


    def get_fitness (self, uow_factory=None, force=False):
        """determine the fitness ranging [0.0, 1.0]; higher is better"""
        if uow_factory and uow_factory.use_force(force):
            # potentially the most expensive operation, deferred with careful consideration
            self._fitness = uow_factory.get_fitness(self._feature_set)

        return self._fitness


    def get_json_feature_set (self):
        """dump the feature set as a JSON string"""
        return dumps(tuple(self._feature_set))


    def populate (self, gen, feature_set):
        """populate the instance variables"""
        self.gen = gen
        self._feature_set = feature_set

        # create a unique key using a SHA-3 digest of the JSON representing this feature set
        m = sha224()
        m.update(self.get_json_feature_set())
        self.key = unicode(m.hexdigest())


    def mutate (self, pop, gen, uow_factory):
        """attempt to mutate the feature set"""
        # constructor pattern
        mutant = self.__class__()
        mutant.populate(gen, uow_factory.mutate_features(self._feature_set))

        # add the mutant Individual to the Population, but remove its prior self
        # failure semantics: ignore, mutation rate is approx upper bounds
        if pop.reify(mutant):
            pop.evict(self)
            return True
        else:
            return False


    def breed (self, pop, gen, mate, uow_factory):
        """breed with a mate to produce a child"""
        # constructor pattern
        child = self.__class__()
        child.populate(gen, uow_factory.breed_features(self._feature_set, mate._feature_set))

        # add the child Individual to the Population
        # failure semantics: ignore, the count will rebalance over the hash ring
        return pop.reify(child)


if __name__=='__main__':
    ## test GA in standalone-mode, without distributed services

    # parse command line options
    if len(sys.argv) < 2:
        uow_name = "uow.UnitOfWorkFactory"
    else:
        uow_name = sys.argv[1]

    uow_factory = instantiate_class(uow_name)

    # initialize a Population of unique Individuals at generation 0
    uow = uow_factory.instantiate_uow(uow_name, "/tmp/exelixi")
    uow.populate(uow.current_gen)
    fitness_cutoff = 0

    # iterate N times or until a "good enough" solution is found
    while uow.current_gen < uow_factory.n_gen:
        hist = uow.get_part_hist()
        hist_items = map(lambda x: (float(x[0]), x[1],), sorted(hist.items(), reverse=True))

        if uow.test_termination(uow.current_gen, hist_items):
            break

        fitness_cutoff = uow.get_fitness_cutoff(hist_items)
        uow.next_generation(uow.current_gen, fitness_cutoff)

        uow.current_gen += 1

    # report summary
    for x in sorted(uow.enum(fitness_cutoff), reverse=True):
        print "\t".join(x)
