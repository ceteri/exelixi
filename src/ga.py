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
from importlib import import_module
from json import dumps
from random import randint, random, sample


######################################################################
## globals and utilities

APP_NAME = "Exelixi"


def instantiate_class (class_path):
    module_name, class_name = class_path.split(".")
    return getattr(import_module(module_name), class_name)()


######################################################################
## class definitions

class Population (object):
    def __init__ (self, indiv_instance, ff_name, prefix="/tmp/exelixi", n_pop=11, term_limit=0.0, hist_granularity=3):
        self.indiv_class = indiv_instance.__class__
        self.feature_factory = instantiate_class(ff_name)

        self.prefix = prefix
        self.n_pop = n_pop

        self._term_limit = term_limit
        self._hist_granularity = hist_granularity

        self._uniq_dht = {}
        self._bf = BloomFilter(num_bytes=125, num_probes=14, iterable=[])


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

        # NB: distribute this operation over the hash ring, through a remote queue
        if not indiv.key in self._bf:
            self._bf.update([indiv.key])

            # potentially the most expensive operation, deferred until remote reification
            indiv.get_fitness(self.feature_factory, force=True)
            self._uniq_dht[indiv.key] = indiv

            return True
        else:
            return False


    def evict (self, indiv):
        """remove an Individual from the Population (death)"""
        if indiv.key in self._uniq_dht:
            # only needs to be removed locally
            del self._uniq_dht[indiv.key]

            # NB: serialize to disk (write behinds)
            url = self._get_storage_path(indiv)


    def get_part_hist (self):
        """tally counts for the partial histogram of the fitness distribution"""
        d = dict(Counter([ round(indiv.get_fitness(self.feature_factory, force=False), self._hist_granularity) for indiv in self._uniq_dht.values() ])).items()
        d.sort(reverse=True)
        return d


    def get_fitness_cutoff (self, selection_rate):
        """determine fitness cutoff (bin lower bounds) for the parent selection filter"""
        sum = 0
        break_next = False

        for bin, count in self.get_part_hist():
            if break_next:
                break

            sum += count
            percentile = sum / float(self.n_pop)
            break_next = percentile >= selection_rate

        return bin


    def _get_storage_path (self, indiv):
        """create a path for durable storage of an Individual"""
        return self.prefix + "/" + indiv.key


    def _boost_diversity (self, current_gen, indiv, mutation_rate):
        """randomly select other individuals and mutate them, to promote genetic diversity"""
        if mutation_rate > random():
            indiv.mutate(self, current_gen, self.feature_factory)
        else:
            self.evict(indiv)


    def _select_parents (self, current_gen, fitness_cutoff, mutation_rate):
        """select the parents for the next generation"""
        partition = map(lambda x: (x.get_fitness() >= fitness_cutoff, x), self._uniq_dht.values())
        good_fit = map(lambda x: x[1], filter(lambda x: x[0], partition))
        poor_fit = map(lambda x: x[1], filter(lambda x: not x[0], partition))

        # randomly select other individuals to promote genetic diversity, while removing the remnant
        for indiv in poor_fit:
            self._boost_diversity(current_gen, indiv, mutation_rate)

        return self._uniq_dht.values()


    def next_generation (self, current_gen, fitness_cutoff, mutation_rate):
        """select/mutate/crossover parents to produce a new generation"""
        parents = self._select_parents(current_gen, fitness_cutoff, mutation_rate)

        for _ in xrange(self.n_pop - len(parents)):
            f, m = sample(parents, 2) 
            success = f.breed(self, current_gen, m, self.feature_factory)

        # backfill to avoid the dreaded Population collapse

        for _ in xrange(self.n_pop - len(self._uniq_dht.values())):
            # constructor pattern
            indiv = self.indiv_class()
            indiv.populate(current_gen, self.feature_factory.generate_features())
            self.reify(indiv)


    def test_termination (self, current_gen):
        """evaluate the terminating condition for this generation and report progress"""
        return self.feature_factory.test_termination(current_gen, self._term_limit, self.get_part_hist())


    def report_summary (self):
        """report a summary of the evolution"""
        for indiv in sorted(self._uniq_dht.values(), key=lambda x: x.get_fitness(), reverse=True):
            print self._get_storage_path(indiv)
            print "\t".join(["%0.4f" % indiv.get_fitness(), "%d" % indiv.gen, indiv.get_json_feature_set()])


class Individual (object):
    def __init__ (self):
        """create a member of the population"""
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


class FeatureFactory (object):
    def __init__ (self):
        ## NB: override these GA parameters
        self.n_pop = 11
        self.n_gen = 5
        self.term_limit = 9.0e-03
        self.selection_rate = 0.2
        self.mutation_rate = 0.02

        ## NB: override these feature set parameters
        self.length = 5
        self.min = 0
        self.max = 100
        self.target = 231


    def get_fitness (self, feature_set):
        """determine the fitness ranging [0.0, 1.0]; higher is better"""
        ## NB: override this fitness function
        return 1.0 - abs(sum(feature_set) - self.target) / float(self.target)


    def use_force (self, force):
        """determine whether to force recalculation of a fitness function"""
        # NB: override in some use cases, e.g., when required for evaluating shared resources
        return force


    def generate_features (self):
        """generate a new feature set"""
        ## NB: override this feature set generator
        return sorted([ randint(self.min, self.max) for _ in xrange(self.length) ])


    def mutate_features (self, feature_set):
        """mutate a copy of the given feature set"""
        ## NB: override this feature set mutator
        pos_to_mutate = randint(0, len(feature_set) - 1)
        mutated_feature_set = list(feature_set)
        mutated_feature_set[pos_to_mutate] = randint(self.min, self.max)
        return sorted(mutated_feature_set)


    def breed_features (self, f_feature_set, m_feature_set):
        """breed two feature sets to produce a child"""
        ## NB: override this feature set crossover
        half = len(f_feature_set) / 2
        return sorted(f_feature_set[half:] + m_feature_set[:half])


    def test_termination (self, current_gen, term_limit, hist):
        """evaluate the terminating condition for this generation and report progress"""
        ## NB: override this termination test

        # find the mean squared error (MSE) of fitness for a population
        n_indiv = sum([ count for bin, count in hist ])
        mse = sum([ count * (1.0 - bin) ** 2.0 for bin, count in hist ]) / float(n_indiv)

        # report the progress for one generation
        print current_gen, n_indiv, "%.2e" % mse, filter(lambda x: x[1] > 0, hist)

        # stop when a "good enough" solution is found
        return mse <= term_limit


if __name__=='__main__':
    ## test in standalone-mode, i.e., without a Framework or Executor

    ff_name = "ga.FeatureFactory"
    ff = instantiate_class(ff_name)

    # initialize a Population of unique Individuals at generation 0
    pop = Population(Individual(), ff_name, prefix="/tmp/exelixi", n_pop=ff.n_pop, term_limit=ff.term_limit)
    pop.populate(0)

    # iterate N times or until a "good enough" solution is found
    for current_gen in xrange(ff.n_gen):
        fitness_cutoff = pop.get_fitness_cutoff(selection_rate=ff.selection_rate)

        if pop.test_termination(current_gen):
            break

        pop.next_generation(current_gen, fitness_cutoff, mutation_rate=ff.mutation_rate)

    # report summary
    pop.report_summary()
