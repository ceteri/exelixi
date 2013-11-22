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


from ga import instantiate_class, APP_NAME, Individual, Population
from hashring import HashRing
from json import loads
from uuid import uuid1
import sys


######################################################################
## class definitions

class Framework (object):
    def __init__ (self, prefix="/tmp/exelixi/"):
        # system parameters, for representing operational state
        self.uuid = uuid1().hex
        self.prefix = prefix + self.uuid
        self.current_gen = 0


if __name__=='__main__':
    ## Framework operations:

    # parse command line options
    ff_name = sys.argv[1]
    ff = instantiate_class(ff_name)

    fra = Framework(ff_name)
    print "%s: framework launching at %s based on %s..." % (APP_NAME, fra.prefix, ff_name)

    # initialize a Population of unique Individuals at generation 0
    pop = Population(Individual(), ff_name, prefix=fra.prefix, n_pop=ff.n_pop, term_limit=ff.term_limit)
    pop.populate(fra.current_gen)

    # iterate N times or until a "good enough" solution is found

    while fra.current_gen < ff.n_gen:
        ## NB: save state to Zookeeper

        fitness_cutoff = pop.get_fitness_cutoff(selection_rate=ff.selection_rate)

        if pop.test_termination(fra.current_gen):
            break

        pop.next_generation(fra.current_gen, fitness_cutoff, mutation_rate=ff.mutation_rate)
        fra.current_gen += 1

    # report summary
    pop.report_summary()
