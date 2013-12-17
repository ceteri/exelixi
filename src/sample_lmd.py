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


from collections import namedtuple
from copy import deepcopy
from random import randint, sample
from uow import UnitOfWorkFactory
import logging
import sys


######################################################################
## class definitions

OPS = ( "rend", "turn", "sup", "loop" )

Point = namedtuple('Point', 'x y')

DIR_W = Point(1, 0)	# DIR_N
DIR_S = Point(0, 1)	# DIR_W
DIR_E = Point(-1, 0)	# DIR_S
DIR_N = Point(0, -1)	# DIR_E


class Drone (object):
    def __init__ (self, x, y):
        self.pos = Point(x, y)
        self.dir = Point(1, 0)


    def _mod_math (self, pos, dir, mod):
        result = pos + dir

        if result < 0:
            result += mod
        else:
            result %= mod

        return result


    def exec_op_sup (self, mod, sup):
        x = self._mod_math(self.pos.x, sup.x, mod)
        y = self._mod_math(self.pos.y, sup.y, mod)
        self.pos = Point(x, y)
        return x, y


    def exec_op_move (self, mod):
        x = self._mod_math(self.pos.x, self.dir.x, mod)
        y = self._mod_math(self.pos.y, self.dir.y, mod)
        self.pos = Point(x, y)
        return x, y


    def exec_op_turn (self):
        if self.dir.x == DIR_W.x and self.dir.y == DIR_W.y:
            self.dir = DIR_N
        elif self.dir.x == DIR_S.x and self.dir.y == DIR_W.y:
            self.dir = DIR_W
        elif self.dir.x == DIR_E.x and self.dir.y == DIR_E.y:
            self.dir = DIR_S
        elif self.dir.x == DIR_N.x and self.dir.y == DIR_N.y:
            self.dir = DIR_E


class LMDFactory (UnitOfWorkFactory):
    """UnitOfWork definition for Lawnmower Drone GP"""

    def __init__ (self):
        #super(UnitOfWorkFactory, self).__init__()
        self.n_pop = 300
        self.n_gen = 200
        self.max_indiv = 20000
        self.selection_rate = 0.3
        self.mutation_rate = 0.3
        self.term_limit = 5.0e-02
        self.hist_granularity = 3

        self.grid = [
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ],
            ]

        # sampling parameters
        self.length = len(self.grid) ** 2
        self.min = 0
        self.max = len(OPS) - 1


    def generate_features (self):
        """generate a new feature set for the lawnmower grid"""
        rand_len = randint(1, self.length)
        feature_set = []

        while len(feature_set) < rand_len:
            op = randint(self.min, self.max)

            if op == OPS.index("sup"):
                feature_set.append(op)
                feature_set.append(randint(0, len(self.grid) - 1))
                feature_set.append(randint(0, len(self.grid) - 1))
            elif op == OPS.index("loop"):
                if len(feature_set) > 2:
                    offset = randint(1, len(feature_set) - 1)
                    feature_set.append(op)
                    feature_set.append(offset)
            else:
                feature_set.append(op)

        return feature_set


    def mutate_features (self, feature_set):
        """mutate a copy of the given feature set"""
        pos_to_mutate = randint(0, len(feature_set) - 1)
        mutated_feature_set = list(feature_set)
        mutated_feature_set[pos_to_mutate] = randint(self.min, self.max)
        return mutated_feature_set


    def breed_features (self, f_feature_set, m_feature_set):
        """breed two feature sets to produce a child"""
        split = randint(1, min(len(f_feature_set), len(m_feature_set)))
        return f_feature_set[split:] + m_feature_set[:split]


    def _simulate (self, grid, code, drone):
        """simulate the lawnmower grid"""
        sp = 0
        mod = len(self.grid)
        num_ops = 0
        max_ops = self.length
        result = None

        try:
            while sp < len(code) and num_ops < max_ops:
                num_ops += 1
                op = code[sp]

                if op == OPS.index("rend"):
                    x, y = drone.exec_op_move(mod)
                    grid[y][x] = 0

                elif op == OPS.index("turn"):
                    drone.exec_op_turn()

                elif op == OPS.index("sup"):
                    sup = Point(code[sp + 1], code[sp + 2])
                    sp += 2

                    if sup.x == 0 and sup.y == 0:
                        return None

                    x, y = drone.exec_op_sup(mod, sup)
                    grid[y][x] = 0

                elif op == OPS.index("loop"):
                    offset = code[sp + 1]

                    if offset == 0 or offset > sp:
                        return None

                    sp -= offset

                else:
                    return None

                #print num_ops, sp, "pos", drone.pos, "dir", drone.dir
                sp += 1

            result = grid

        finally:
            return result


    def get_fitness (self, feature_set):
        """determine the fitness ranging [0.0, 1.0]; higher is better"""
        drone = Drone(randint(0, len(self.grid)), randint(0, len(self.grid)))
        grid = self._simulate(deepcopy(self.grid), feature_set, drone)
        fitness = 0.0

        if grid:
            terrorists = 0

            for row in grid:
                #print row
                terrorists += sum(row)

            fitness = round((self.length - terrorists) / float(self.length), 4)

            if len(feature_set) > 5:
                penalty = len(feature_set) / 10.0
                fitness /= penalty

        #print fitness, feature_set
        return fitness


if __name__=='__main__':
    uow = LMDFactory()

    print uow.grid
