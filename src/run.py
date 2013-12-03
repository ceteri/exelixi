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


from random import randint
from ga import instantiate_class
import logging


######################################################################
## class definitions

class FeatureFactory (object):
    def __init__ (self):
        ## NB: override these GA parameters
        self.n_pop = 23
        self.n_gen = 10
        self.term_limit = 5.0e-03
        self.hist_granularity = 3
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
        n_indiv = sum([ count for bin, count in hist.items() ])
        mse = sum([ count * (1.0 - bin) ** 2.0 for bin, count in hist.items() ]) / float(n_indiv)

        # report the progress for one generation
        logging.debug("test: gen %d size %d mse %.2e %s", current_gen, n_indiv, mse, filter(lambda x: x[1] > 0, hist.items()))

        # stop when a "good enough" solution is found
        return mse <= term_limit


if __name__=='__main__':
    ## a simple test
    ff_name = "run.FeatureFactory"
    ff = instantiate_class(ff_name)

    print ff
