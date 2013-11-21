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


from ga import FeatureFactory, Individual, Population
from hashring import HashRing
from json import loads
from uuid import uuid1
import sys


######################################################################
## class definitions

class Framework (object):
    def __init__ (self, prefix="/tmp/exelixi/", n_gen=9):
        # system parameters, for representing operational state
        self.uuid = uuid1().hex
        self.prefix = prefix + self.uuid

        # model parameters, for representing logical state
        self.n_gen = n_gen


if __name__=='__main__':
    ## Framework operations:

    # parse command line options
    print "Exelixi: framework launching..."

    fra = Framework(n_gen=5)
    print fra.prefix

    # initialize a Population of unique Individuals at generation 0
    pop = Population(Individual(), FeatureFactory(), prefix=fra.prefix, n_pop=11, term_limit=9.0e-03)
    pop.populate(0)

    # iterate N times or until a "good enough" solution is found

    for current_gen in xrange(fra.n_gen):
        fitness_cutoff = pop.get_fitness_cutoff(selection_rate=0.2)
        pop.next_generation(current_gen, fitness_cutoff, mutation_rate=0.02)

        if pop.test_termination(current_gen):
            break

    # report summary
    pop.report_summary()
