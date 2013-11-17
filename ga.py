#!/usr/bin/env python
# encoding: utf-8

from random import randint, random, sample

class Population (object):
    def __init__ (self, n_pop=10, n_gen=5, mse_limit=0.0):
        self.n_pop = n_pop
        self.n_gen = n_gen
        self.mse_limit = mse_limit

        self.dist_hist = {}
        ## assert: population == values in this DHT which have "is_alive" flag true
        self.uniq_d = {}


    def populate (self):
        "create the initial population"
        self.uniq_d = dict([ (indiv.sign, indiv) for indiv in [ Individual.populate(self, 0) for x in xrange(self.n_pop) ] ])
        self.pop = self.uniq_d.values()


    def grade (self):
        "find the mean squared error (MSE) of fitness for a population"
        return sum((1.0 - indiv.fitness) ** 2.0 for indiv in self.pop) / float(self.n_pop)


    def report_progress (self, gen, mse):
        "report the progress for one generation"
        print gen, "%.2e" % mse, sorted(self.dist_hist.items(), reverse=True)


    def report_summary (self):
        "report the summary for evolution so far"
        for indiv in sorted(self.pop, key=lambda x: x.fitness, reverse=True):
            print indiv.gen, indiv.value, indiv.fitness


    def get_bin_threshold (self, retention_rate):
        "determine bin threshold for parent selection filter"
        h = [ (bin, counter[0]) for (bin, counter) in self.dist_hist.items() ]
        h.sort(reverse=True)
        sum = 0
        break_next = False

        for bin, count in h:
            if break_next:
                break

            sum += count
            percentile = sum / float(self.n_pop)
            break_next = percentile >= retention_rate

        return bin


    def add_diversity (self, indiv, rand, selection_rate, mutation_rate):
        "randomly add other individuals to promote genetic diversity"
        if selection_rate > rand:
            if mutation_rate > rand:
                indiv.mutate(self)

            return True
        else:
            indiv.tally(False, self)
            return False


    def select_parents (self, retention_rate=0.2, selection_rate=0.05, mutation_rate=0.02):
        "select the parents for the next generation"
        bin_lower = self.get_bin_threshold(retention_rate)
        thresh = map(lambda x: (x.fitness > bin_lower, x), self.pop)
        parents = map(lambda x: x[1], filter(lambda x: x[0], thresh))

        # randomly add other individuals to promote genetic diversity
        poor = map(lambda x: (x[1], random()), filter(lambda x: not x[0], thresh))
        diverse = map(lambda x: x[0], filter(lambda x: self.add_diversity(x[0], x[1], selection_rate, mutation_rate), poor))

        # NB: assert these are the only Individual objects with is_alive=True
        parents.extend(diverse)
        return parents


    def crossover_parents (self, gen, parents):
        "crossover parents to create the children"
        pairs = [ sample(parents, 2) for i in xrange(self.n_pop - len(parents)) ]
        return filter(lambda x: x, [ f.breed(m, self, gen) for (f, m) in pairs ])


    def one_generation (self, gen):
        "select/mutate/crossover to produce a new generation"
        parents = self.select_parents(retention_rate=0.5)
        children = self.crossover_parents(gen, parents)

        ## complete the generation
        parents.extend(children)
        self.pop = parents


    def tally_hist (self, bin, increment):
        "tally counts for the distributed histogram"
        if bin in self.dist_hist:
            counter = self.dist_hist[bin]
        else:
            counter = [0, 0]
            self.dist_hist[bin] = counter

        if increment:
            counter[0] += 1
        else:
            counter[0] -= 1
            counter[1] += 1


class Individual (object):
    target = 231

    def __init__ (self, gen):
        "create a member of the population"
        self.gen = gen
        self.is_alive = True
        self.fitness = None
        self.sign = None


    def calc_fitness (self, pop):
        "determine the fitness ranging [0.0, 1.0]; higher is better"
        self.fitness = 1.0 - abs(sum(self.value) - Individual.target) / float(Individual.target)
        self.sign = tuple(self.value)
        pop.uniq_d[self.sign] = self


    def mutate (self, pop):
        "attempt mutate some of its genes"
        pos_to_mutate = randint(0, len(self.value) - 1)
        new_value = self.value
        new_value[pos_to_mutate] = randint(Individual.min, Individual.max)
        new_value.sort()
        self.sign = tuple(new_value)

        if self.sign not in pop.uniq_d:
            self.value = new_value
            self.tally(False, pop)
            self.calc_fitness(pop)
            self.tally(True, pop)


    def breed (self, mate, pop, gen):
        "breed with a mate to produce a child"
        half = len(self.value) / 2
        child = Individual(gen)
        child.value = self.value[half:] + mate.value[:half]
        child.value.sort()
        child.sign = tuple(child.value)

        if child.sign not in pop.uniq_d:
            child.calc_fitness(pop)
            child.tally(True, pop)
            return child
        else:
            return None


    def tally (self, increment, pop):
        "increment/decrement the histogram tally"
        pop.tally_hist(round(self.fitness, 5), increment)


    @staticmethod
    def populate (pop, gen):
        "populate values for an Individual"
        indiv = Individual(gen)
        indiv.value = [ randint(Individual.min, Individual.max) for x in xrange(Individual.length) ]
        indiv.value.sort()
        indiv.calc_fitness(pop)
        indiv.tally(True, pop)
        return indiv


if __name__=='__main__':
    ## create a population of individuals
    Individual.length = 5
    Individual.min = 0
    Individual.max = 100

    ## make initial population unique
    pop = Population(n_pop=20, n_gen=5, mse_limit=1.0e-03)
    pop.populate()

    ## iterate N times or until a "good enough" solution is found
    for gen in xrange(pop.n_gen):
        pop.one_generation(gen)

        ## evaluate MSE for this generation and report progress
        mse = pop.grade()
        pop.report_progress(gen, mse)

        ## stop when a "good enough" solution is found
        if mse <= pop.mse_limit:
            break

    ## report summary
    pop.report_summary()
