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

class Population (object):
    def __init__ (self, n_pop=10, n_gen=5, limit=0.0, resolution=3):
        self.n_pop = n_pop
        self.n_gen = n_gen
        self.limit = limit
        self.resolution = resolution
        self.pop = {}
        self.hist = {}
        ## assert: population == values in this DHT which have "is_alive" flag true
        self.uniq_d = {}


    def populate (self):
        "initialize the population"
        attempts = [ Individual.populate(0) for x in xrange(self.n_pop) ]
        self.uniq_d = dict([ (indiv.key, indiv) for indiv in filter(lambda x: x, attempts) ])
        self.pop = self.uniq_d.values()


    def is_novel (self, key):
        "test whether a key is novel"
        return not key in self.uniq_d


    def get_bin_threshold (self, selection_rate):
        "determine bin threshold for parent selection filter"
        sum = 0
        break_next = False

        for bin, count in sorted(self.hist.items(), reverse=True):
            if break_next:
                break

            sum += count
            percentile = sum / float(self.n_pop)
            break_next = percentile >= selection_rate

        return bin


    def add_diversity (self, indiv, rand, diversity_rate, mutation_rate):
        "randomly add other individuals to promote genetic diversity"
        if diversity_rate > rand:
            if mutation_rate > rand:
                indiv.mutate()

            return True
        else:
            indiv.tally(False)
            return False


    def select_parents (self, selection_rate=0.2, diversity_rate=0.05, mutation_rate=0.02):
        "select the parents for the next generation"
        bin_lower = self.get_bin_threshold(selection_rate)
        thresh = map(lambda x: (x.fitness > bin_lower, x), self.pop)
        parents = map(lambda x: x[1], filter(lambda x: x[0], thresh))

        # randomly add other individuals to promote genetic diversity
        poor = map(lambda x: (x[1], random()), filter(lambda x: not x[0], thresh))
        diverse = map(lambda x: x[0], filter(lambda x: self.add_diversity(x[0], x[1], diversity_rate, mutation_rate), poor))

        # NB: assert these are the only Individual objects with is_alive=True
        parents.extend(diverse)
        return parents


    def crossover_parents (self, gen, parents):
        "crossover parents to create the children"
        pairs = [ sample(parents, 2) for i in xrange(self.n_pop - len(parents)) ]
        return filter(lambda x: x, [ f.breed(m, gen) for (f, m) in pairs ])


    def tally_hist (self, fitness, increment):
        "tally counts for the distributed histogram"
        bin = round(fitness, self.resolution)

        if bin not in self.hist:
            self.hist[bin] = 0

        if increment:
            self.hist[bin] += 1
        else:
            self.hist[bin] -= 1


    def run_generation (self, gen):
        "select/mutate/crossover to produce a new generation"
        parents = self.select_parents(selection_rate=0.5)
        children = self.crossover_parents(gen, parents)

        ## complete the generation
        parents.extend(children)
        self.pop = parents


    def test_termination (self, gen):
        "evaluate the terminating condition for this generation and report progress"

        ## find the mean squared error (MSE) of fitness for a population
        mse = sum([ count * (1.0 - bin) ** 2.0 for bin, count in self.hist.items() ]) / float(self.n_pop)

        ## report the progress for one generation
        print gen, "%.2e" % mse, filter(lambda x: x[1] > 0, sorted(self.hist.items(), reverse=True))

        ## stop when a "good enough" solution is found
        return mse <= self.limit


    def evolve (self):
        "iterate N times or until a 'good enough' solution is found"

        for gen in xrange(self.n_gen):
            self.run_generation(gen)

            if self.test_termination(gen):
                break


    def report_summary (self):
        "report a summary of the evolution"
        for indiv in sorted(self.pop, key=lambda x: x.fitness, reverse=True):
            print indiv.gen, sorted(indiv.features), "%f" % indiv.fitness


class Individual (object):
    pop = None

    def __init__ (self, gen):
        "create a member of the population"
        self.gen = gen
        self.features = None
        self.key = None
        self.fitness = None
        self.is_alive = True


    @staticmethod
    def get_key (features):
        "determine a unique key for the given feature set"
        return tuple(sorted(features))


    def calc_fitness (self):
        "determine the fitness ranging [0.0, 1.0]; higher is better"
        self.fitness = 1.0 - abs(sum(self.features) - Individual.target) / float(Individual.target)


    @staticmethod
    def populate (gen):
        "populate values for an Individual"
        indiv = Individual(gen)
        indiv.features = [ randint(Individual.min, Individual.max) for x in xrange(Individual.length) ]

        indiv.key = Individual.get_key(indiv.features)

        if Individual.pop.is_novel(indiv.key):
            Individual.pop.uniq_d[indiv.key] = indiv
            indiv.calc_fitness()
            indiv.tally(True)
            return indiv
        else:
            return None


    def mutate (self):
        "attempt to mutate some of its features"
        pos_to_mutate = randint(0, len(self.features) - 1)
        mutated_features = self.features
        mutated_features[pos_to_mutate] = randint(Individual.min, Individual.max)

        mutant = Individual(self.gen)
        mutant.features = mutated_features
        mutant.key = Individual.get_key(mutant.features)

        if Individual.pop.is_novel(mutant.key):
            Individual.pop.uniq_d[mutant.key] = self
            self.tally(False)

            mutant.calc_fitness()
            mutant.tally(True)


    def breed (self, mate, gen):
        "breed with a mate to produce a child"
        half = len(self.features) / 2
        child = Individual(gen)
        child.features = self.features[half:] + mate.features[:half]
        child.key = Individual.get_key(child.features)

        if Individual.pop.is_novel(child.key):
            Individual.pop.uniq_d[child.key] = child

            child.calc_fitness()
            child.tally(True)
            return child
        else:
            return None


    def tally (self, increment):
        "increment/decrement the histogram tally"
        Individual.pop.tally_hist(self.fitness, increment)


if __name__=='__main__':
    ## create a population of individuals
    Individual.target = 231
    Individual.length = 5
    Individual.min = 0
    Individual.max = 100

    ## make initial population unique
    Individual.pop = Population(n_pop=20, n_gen=5, limit=1.0e-03)
    Individual.pop.populate()

    ## iterate N times or until a "good enough" solution is found
    Individual.pop.evolve()

    ## report summary
    Individual.pop.report_summary()
