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
from hashring import HashRing
from hashlib import sha224
from json import dumps
from random import randint, random, sample
from uuid import uuid1


######################################################################
## class definitions

class Population (object):
    def __init__ (self, indiv, prefix="/tmp/exelixi", n_pop=10, n_gen=5, limit=0.0, resolution=3):
        self.indiv_class = indiv.__class__
        self.prefix = prefix
        self.n_pop = n_pop
        self.n_gen = n_gen
        self.limit = limit
        self.resolution = resolution

        self._uniq_dht = {}
        self._bf = BloomFilter(num_bytes=125, num_probes=14, iterable=[])
        self._part_hist = {}


    def populate (self, gen):
        """initialize the population"""
        for x in xrange(self.n_pop):
            # constructor pattern
            indiv = self.indiv_class()
            indiv.populate(gen, indiv.generate_feature_set())

            # add the generated Individual to the Population
            # failure semantics: must filter nulls from initial population
            self.reify(indiv)


    def reify (self, indiv):
        """test/put a newly generated Individual to the dictionary for uniques"""

        # NB: distribute this operation over the hash ring, through a remote queue
        if not indiv.key in self._uniq_dht:
            # NB: potentially the most expensive operation, deferred until remote reification
            indiv.calc_fitness()

            self._bf.update([indiv.key])
            self._uniq_dht[indiv.key] = indiv
            self._tally_hist(indiv, True)

            return True
        else:
            return False


    def _tally_hist (self, indiv, increment):
        """tally counts for the partial histogram"""
        bin = round(indiv.fitness, self.resolution)

        if bin not in self._part_hist:
            self._part_hist[bin] = 0

        if increment:
            self._part_hist[bin] += 1
        else:
            self._part_hist[bin] -= 1


    def _get_bin_lower (self, selection_rate):
        """determine bin threshold for parent selection filter"""
        sum = 0
        break_next = False

        for bin, count in sorted(self._part_hist.items(), reverse=True):
            if break_next:
                break

            sum += count
            percentile = sum / float(self.n_pop)
            break_next = percentile >= selection_rate

        return bin


    def _get_storage_path (self, indiv):
        """create a path for durable storage of an Individual"""
        return self.prefix + "/" + indiv.key


    def remove_individual (self, indiv):
        """dereify: remove Individual from the Population"""
        if indiv.key in self._uniq_dht:
            # remove locally
            del self._uniq_dht[indiv.key]
            self._tally_hist(indiv, False)

            # NB: serialize to disk (write behinds)
            url = self._get_storage_path(indiv)


    def _add_diversity (self, gen, indiv, diversity_rate, mutation_rate):
        """randomly add other individuals to promote genetic diversity"""
        if diversity_rate > random():
            if mutation_rate > random():
                indiv.mutate(self, gen)
        else:
            self.remove_individual(indiv)


    def _select_parents (self, gen, selection_rate=0.2, diversity_rate=0.05, mutation_rate=0.02):
        """select the parents for the next generation"""
        bin_lower = self._get_bin_lower(selection_rate)
        partition = map(lambda x: (x.fitness > bin_lower, x), self._uniq_dht.values())

        good_fit = map(lambda x: x[1], filter(lambda x: x[0], partition))
        poor_fit = map(lambda x: x[1], filter(lambda x: not x[0], partition))

        # randomly select other individuals to promote genetic diversity, while removing the remnant
        for indiv in poor_fit:
            self._add_diversity(gen, indiv, diversity_rate, mutation_rate)

        return self._uniq_dht.values()


    def _run_generation (self, gen):
        """select/mutate/crossover parents to produce a new generation"""
        parents = self._select_parents(gen, selection_rate=0.5)

        for (f, m) in [ sample(parents, 2) for i in xrange(self.n_pop - len(parents)) ]:
            f.breed(pop, gen, m)


    def _test_termination (self, gen):
        """evaluate the terminating condition for this generation and report progress"""
        # find the mean squared error (MSE) of fitness for a population
        mse = sum([ count * (1.0 - bin) ** 2.0 for bin, count in self._part_hist.items() ]) / float(self.n_pop)

        # report the progress for one generation
        print gen, "%.2e" % mse, filter(lambda x: x[1] > 0, sorted(self._part_hist.items(), reverse=True))

        # stop when a "good enough" solution is found
        return mse <= self.limit


    def evolve (self):
        """iterate N times or until a 'good enough' solution is found"""
        for gen in xrange(self.n_gen):
            self._run_generation(gen)

            if self._test_termination(gen):
                break


    def report_summary (self):
        """report a summary of the evolution"""
        for indiv in sorted(self._uniq_dht.values(), key=lambda x: x.fitness, reverse=True):
            print self._get_storage_path(indiv)
            print "\t".join(["%0.4f" % indiv.fitness, "%d" % indiv.gen, indiv.get_json_feature_set()])


class Individual (object):
    # feature set parameters (customize this part)
    target = 231
    length = 5
    min = 0
    max = 100


    def __init__ (self):
        """create a member of the population"""
        self.gen = None
        self._feature_set = None
        self.key = None
        self.fitness = None


    def populate (self, gen, feature_set):
        """populate the instance variables"""
        self.gen = gen
        self._feature_set = feature_set
        self.key = self.get_unique_key()


    def generate_feature_set (self):
        """generate a new feature set"""
        return sorted([ randint(Individual.min, Individual.max) for x in xrange(Individual.length) ])


    def get_json_feature_set (self):
        """dump the feature set as a JSON string"""
        return dumps(tuple(self._feature_set))


    def get_unique_key (self):
        """create a unique key by taking a SHA-3 digest of the JSON representing this feature set"""
        m = sha224()
        m.update(self.get_json_feature_set())
        return m.hexdigest()


    def calc_fitness (self):
        """determine the fitness ranging [0.0, 1.0]; higher is better"""
        self.fitness = 1.0 - abs(sum(self._feature_set) - Individual.target) / float(Individual.target)


    def mutate (self, pop, gen):
        """attempt to mutate the feature set"""
        pos_to_mutate = randint(0, len(self._feature_set) - 1)
        mutated_feature_set = self._feature_set
        mutated_feature_set[pos_to_mutate] = randint(Individual.min, Individual.max)

        # constructor pattern
        mutant = self.__class__()
        mutant.populate(gen, sorted(mutated_feature_set))

        # add the mutant Individual to the Population, but remove its prior self
        # failure semantics: ignore, mutation rate is approx upper bounds
        if pop.reify(mutant):
            pop.remove_individual(self)


    def breed (self, pop, gen, mate):
        """breed with a mate to produce a child"""
        half = len(self._feature_set) / 2

        # constructor pattern
        child = self.__class__()
        child.populate(gen, sorted(self._feature_set[half:] + mate._feature_set[:half]))

        # add the child Individual to the Population
        # failure semantics: ignore, the count will rebalance over the hash ring
        pop.reify(child)


if __name__=='__main__':
    ## Framework operations:

    # generate a unique prefix
    uuid = uuid1().hex
    prefix = "/tmp/exelixi/%s" % uuid

    # initialize a Population of unique Individuals at generation 0
    pop = Population(Individual(), prefix=prefix, n_pop=20, n_gen=5, limit=1.0e-03)
    pop.populate(0)

    # iterate N times or until a "good enough" solution is found
    pop.evolve()

    # report summary
    pop.report_summary()
