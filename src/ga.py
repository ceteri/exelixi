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


from bloomfilter import BloomFilter
from collections import Counter
from hashlib import sha224
from hashring import HashRing
from httplib import BadStatusLine
from importlib import import_module
from json import dumps, loads
from random import random, sample
from urllib2 import urlopen, Request, URLError
import logging
import sys


######################################################################
## globals and utilities

APP_NAME = "Exelixi"


def instantiate_class (class_path):
    """instantiate a class from the given package.class name"""
    module_name, class_name = class_path.split(".")
    return getattr(import_module(module_name), class_name)()


def post_exe_rest (prefix, shard_id, exe_uri, path, base_msg):
    """POST a JSON-based message to a REST endpoint on a shard"""
    msg = base_msg.copy()

    # populate credentials
    msg["prefix"] = prefix
    msg["shard_id"] = shard_id

    # POST to the REST endpoint
    uri = "http://" + exe_uri + "/" + path
    req = Request(uri)
    req.add_header('Content-Type', 'application/json')

    logging.debug("send %s %s", exe_uri, path)
    logging.debug(dumps(msg))

    # read/collect the response
    try:
        f = urlopen(req, dumps(msg))
        return f.readlines()
    except URLError as e:
        logging.critical("could not reach REST endpoint %s error: %s", uri, str(e.reason), exc_info=True)
        raise
    except BadStatusLine as e:
        logging.critical("REST endpoint died %s error: %s", uri, str(e.line), exc_info=True)


######################################################################
## class definitions

class Population (object):
    def __init__ (self, indiv_instance, ff_name, prefix="/tmp/exelixi"):
        self.indiv_class = indiv_instance.__class__
        self.feature_factory = instantiate_class(ff_name)

        self.prefix = prefix
        self._shard_id = None
        self._exe_dict = None
        self._hash_ring = None

        self.n_pop = self.feature_factory.n_pop
        self.total_indiv = 0
        self._term_limit = self.feature_factory.term_limit
        self._hist_granularity = self.feature_factory.hist_granularity

        self._selection_rate = self.feature_factory.selection_rate
        self._mutation_rate = self.feature_factory.mutation_rate

        self._shard = {}
        self._bf = BloomFilter(num_bytes=125, num_probes=14, iterable=[])


    def set_ring (self, shard_id, exe_dict):
        """initialize the HashRing"""
        self._shard_id = shard_id
        self._exe_dict = exe_dict
        self._hash_ring = HashRing(exe_dict.keys())


    ######################################################################
    ## Individual lifecycle within the local subset of the Population

    def populate (self, current_gen):
        """initialize the population"""
        for _ in xrange(self.n_pop):
            # constructor pattern
            indiv = self.indiv_class()
            indiv.populate(current_gen, self.feature_factory.generate_features())

            # add the generated Individual to the Population
            # failure semantics: must filter nulls from initial population
            self.reify(indiv)


    def reify (self, indiv):
        """test/add a newly generated Individual into the Population (birth)"""
        neighbor_shard_id = None
        exe_uri = None

        if self._hash_ring:
            neighbor_shard_id = self._hash_ring.get_node(indiv.key)

            if neighbor_shard_id != self._shard_id:
                exe_uri = self._exe_dict[neighbor_shard_id]

        # distribute this operation over the hash ring, through a remote queue
        if exe_uri:
            msg = { "key": indiv.key, "gen": indiv.gen, "feature_set": loads(indiv.get_json_feature_set()) }
            lines = post_exe_rest(self.prefix, neighbor_shard_id, exe_uri, "pop/reify", msg)
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
        if not indiv.key in self._bf:
            self._bf.update([indiv.key])
            self.total_indiv += 1

            # potentially the most expensive operation, deferred until remote reification
            indiv.get_fitness(self.feature_factory, force=True)
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
        d = (Counter([ round(indiv.get_fitness(self.feature_factory, force=False), self._hist_granularity) for indiv in self._shard.values() ])).items()
        d.sort(reverse=True)
        return d


    def get_fitness_cutoff (self, hist):
        """determine fitness cutoff (bin lower bounds) for the parent selection filter"""
        h = hist.items()
        h.sort(reverse=True)
        logging.debug("fit: %s", h)

        n_indiv = sum([ count for bin, count in h ])
        part_sum = 0
        break_next = False

        for bin, count in h:
            if break_next:
                break

            part_sum += count
            percentile = part_sum / float(n_indiv)
            break_next = percentile >= self._selection_rate

        logging.debug("fit: percentile %f part_sum %d n_indiv %d bin %f", percentile, part_sum, n_indiv, bin)
        return bin


    def _get_storage_path (self, indiv):
        """create a path for durable storage of an Individual"""
        return self.prefix + "/" + indiv.key


    def _boost_diversity (self, current_gen, indiv):
        """randomly select other individuals and mutate them, to promote genetic diversity"""
        if self._mutation_rate > random():
            indiv.mutate(self, current_gen, self.feature_factory)
        elif len(self._shard.values()) >= 3:
            # NB: ensure that at least three parents remain in each
            # shard per generation
            self.evict(indiv)


    def _select_parents (self, current_gen, fitness_cutoff):
        """select the parents for the next generation"""
        partition = map(lambda x: (round(x.get_fitness(), self._hist_granularity) >= fitness_cutoff, x), self._shard.values())
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

        for _ in xrange(self.n_pop - len(parents)):
            f, m = sample(parents, 2) 
            success = f.breed(self, current_gen, m, self.feature_factory)

        # backfill to avoid the dreaded Population collapse
        for _ in xrange(self.n_pop - len(self._shard.values())):
            # constructor pattern
            indiv = self.indiv_class()
            indiv.populate(current_gen, self.feature_factory.generate_features())
            self.reify(indiv)

        logging.info("gen\t%d\tshard\t%s\tsize\t%d\ttotal\t%d", current_gen, self._shard_id, len(self._shard.values()), self.total_indiv)


    def test_termination (self, current_gen, hist):
        """evaluate the terminating condition for this generation and report progress"""
        return self.feature_factory.test_termination(current_gen, self._term_limit, hist, self.total_indiv)


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


    def get_fitness (self, feature_factory=None, force=False):
        """determine the fitness ranging [0.0, 1.0]; higher is better"""
        if feature_factory and feature_factory.use_force(force):
            # potentially the most expensive operation, deferred with careful consideration
            self._fitness = feature_factory.get_fitness(self._feature_set)

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
        self.key = m.hexdigest()


    def mutate (self, pop, gen, feature_factory):
        """attempt to mutate the feature set"""
        # constructor pattern
        mutant = self.__class__()
        mutant.populate(gen, feature_factory.mutate_features(self._feature_set))

        # add the mutant Individual to the Population, but remove its prior self
        # failure semantics: ignore, mutation rate is approx upper bounds
        if pop.reify(mutant):
            pop.evict(self)
            return True
        else:
            return False


    def breed (self, pop, gen, mate, feature_factory):
        """breed with a mate to produce a child"""
        # constructor pattern
        child = self.__class__()
        child.populate(gen, feature_factory.breed_features(self._feature_set, mate._feature_set))

        # add the child Individual to the Population
        # failure semantics: ignore, the count will rebalance over the hash ring
        return pop.reify(child)


if __name__=='__main__':
    ## test on single node / single shard

    # parse command line options
    if len(sys.argv) < 2:
        ff_name = "run.FeatureFactory"
    else:
        ff_name = sys.argv[1]

    ## test GA in standalone-mode, i.e., without a Framework or Executor
    ff = instantiate_class(ff_name)

    # initialize a Population of unique Individuals at generation 0
    pop = Population(Individual(), ff_name, prefix="/tmp/exelixi")
    pop.populate(0)

    # iterate N times or until a "good enough" solution is found
    for current_gen in xrange(ff.n_gen):
        hist = pop.get_part_hist()

        if pop.test_termination(current_gen, hist):
            break

        fitness_cutoff = pop.get_fitness_cutoff(hist)
        pop.next_generation(current_gen, fitness_cutoff)

    # report summary
    pop.enum(fitness_cutoff)
