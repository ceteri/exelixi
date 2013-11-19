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


from random import randint, random, sample
import hashlib
import json
import uuid


######################################################################
## class definitions

class Population (object):
    def __init__ (self, prefix="/tmp/exelixi", n_pop=10, n_gen=5, limit=0.0, resolution=3):
        self.prefix = prefix
        self.n_pop = n_pop
        self.n_gen = n_gen
        self.limit = limit
        self.resolution = resolution

        self._local_pop = {}
        self._uniq_dht = {}
        self._fit_hist = {}


    def populate (self):
        """initialize the population"""
        attempts = [ Individual.populate(self, 0) for x in xrange(self.n_pop) ]
        self._uniq_dht = dict([ (indiv.key, indiv) for indiv in filter(lambda x: x, attempts) ])
        self._local_pop = self._uniq_dht.values()


    def get_storage_path (self, indiv):
        """create a path for durable storage of an Individual"""
        return self.prefix + "/" + indiv.key


    def reify (self, indiv):
        """test/put a newly generated Individual to the dictionary for uniques"""

        if not indiv.key in self._uniq_dht:
            indiv.calc_fitness()

            # NB: must also serialize to disk
            url = self.get_storage_path(indiv)

            self._uniq_dht[indiv.key] = indiv
            indiv.tally(True)
            return True
        else:
            return False


    def get_bin_threshold (self, selection_rate):
        """determine bin threshold for parent selection filter"""
        sum = 0
        break_next = False

        for bin, count in sorted(self._fit_hist.items(), reverse=True):
            if break_next:
                break

            sum += count
            percentile = sum / float(self.n_pop)
            break_next = percentile >= selection_rate

        return bin


    def add_diversity (self, indiv, rand, diversity_rate, mutation_rate):
        """randomly add other individuals to promote genetic diversity"""
        if diversity_rate > rand:
            if mutation_rate > rand:
                indiv.mutate()

            return True
        else:
            indiv.tally(False)
            return False


    def select_parents (self, selection_rate=0.2, diversity_rate=0.05, mutation_rate=0.02):
        """select the parents for the next generation"""
        bin_lower = self.get_bin_threshold(selection_rate)
        thresh = map(lambda x: (x.fitness > bin_lower, x), self._local_pop)
        parents = map(lambda x: x[1], filter(lambda x: x[0], thresh))

        # randomly add other individuals to promote genetic diversity
        poor = map(lambda x: (x[1], random()), filter(lambda x: not x[0], thresh))
        diverse = map(lambda x: x[0], filter(lambda x: self.add_diversity(x[0], x[1], diversity_rate, mutation_rate), poor))

        parents.extend(diverse)
        return parents


    def crossover_parents (self, gen, parents):
        """crossover parents to create the children"""
        pairs = [ sample(parents, 2) for i in xrange(self.n_pop - len(parents)) ]
        return filter(lambda x: x, [ f.breed(m, gen) for (f, m) in pairs ])


    def tally_hist (self, fitness, increment):
        """tally counts for the distributed histogram"""
        bin = round(fitness, self.resolution)

        if bin not in self._fit_hist:
            self._fit_hist[bin] = 0

        if increment:
            self._fit_hist[bin] += 1
        else:
            self._fit_hist[bin] -= 1


    def run_generation (self, gen):
        """select/mutate/crossover to produce a new generation"""
        parents = self.select_parents(selection_rate=0.5)
        children = self.crossover_parents(gen, parents)

        # complete the generation
        parents.extend(children)
        self._local_pop = parents


    def test_termination (self, gen):
        """evaluate the terminating condition for this generation and report progress"""
        # find the mean squared error (MSE) of fitness for a population
        mse = sum([ count * (1.0 - bin) ** 2.0 for bin, count in self._fit_hist.items() ]) / float(self.n_pop)

        # report the progress for one generation
        print gen, "%.2e" % mse, filter(lambda x: x[1] > 0, sorted(self._fit_hist.items(), reverse=True))

        # stop when a "good enough" solution is found
        return mse <= self.limit


    def evolve (self):
        """iterate N times or until a 'good enough' solution is found"""
        for gen in xrange(self.n_gen):
            self.run_generation(gen)

            if self.test_termination(gen):
                break


    def report_summary (self):
        """report a summary of the evolution"""
        for indiv in sorted(self._local_pop, key=lambda x: x.fitness, reverse=True):
            print self.get_storage_path(indiv)
            print indiv.gen, indiv.features, "%f" % indiv.fitness


class Individual (object):
    # feature set parameters (customize this part)
    target = 231
    length = 5
    min = 0
    max = 100


    def __init__ (self, pop, gen):
        """create a member of the population"""
        self.pop = pop
        self.gen = gen
        self.features = None
        self.key = None
        self.fitness = None


    def get_json_features (self):
        """dump the feature set as a JSON string"""
        return json.dumps(tuple(self.features))


    def get_unique_key (self):
        """create a unique key by taking a SHA-3 digest of the JSON representing this feature set"""
        m = hashlib.sha224()
        m.update(self.get_json_features())
        return m.hexdigest()


    def calc_fitness (self):
        """determine the fitness ranging [0.0, 1.0]; higher is better"""
        self.fitness = 1.0 - abs(sum(self.features) - Individual.target) / float(Individual.target)


    def tally (self, increment):
        """increment/decrement the histogram tally"""
        self.pop.tally_hist(self.fitness, increment)


    @staticmethod
    def populate (pop, gen):
        """populate values for an Individual"""
        indiv = Individual(pop, gen)
        indiv.features = sorted([ randint(Individual.min, Individual.max) for x in xrange(Individual.length) ])
        indiv.key = indiv.get_unique_key()

        # failure semantics: must filter nulls from initial population
        if pop.reify(indiv):
            return indiv
        else:
            return None


    def mutate (self):
        """attempt to mutate some of its features"""
        pos_to_mutate = randint(0, len(self.features) - 1)
        mutated_features = self.features
        mutated_features[pos_to_mutate] = randint(Individual.min, Individual.max)

        mutant = Individual(self.pop, self.gen)
        mutant.features = sorted(mutated_features)
        mutant.key = mutant.get_unique_key()

        # failure semantics: no prob, mutation rate is approx upper bounds
        if self.pop.reify(mutant):
            self.tally(False)


    def breed (self, mate, gen):
        """breed with a mate to produce a child"""
        half = len(self.features) / 2

        child = Individual(self.pop, gen)
        child.features = sorted(self.features[half:] + mate.features[:half])
        child.key = child.get_unique_key()

        # failure semantics: must filter nulls from "children" list
        if self.pop.reify(child):
            return child
        else:
            return None


if __name__=='__main__':
    print "UUID", uuid.uuid1().hex

    # create a population of unique individuals
    pop = Population(n_pop=20, n_gen=5, limit=1.0e-03)
    pop.populate()

    # iterate N times or until a "good enough" solution is found
    pop.evolve()

    # report summary
    pop.report_summary()
