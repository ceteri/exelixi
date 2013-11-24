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


from executor import Executor
from ga import APP_NAME
from gevent import monkey
import argparse


if __name__=='__main__':
    parser = argparse.ArgumentParser(prog="Exelixi", usage="one of the operational modes shown below...", add_help=True,
                                     description="Exelixi, a distributed framework for genetic algorithms, based on Apache Mesos")

    group1 = parser.add_argument_group("Mesos Framework", "run as a Framework on an Apache Mesos cluster")
    group1.add_argument("-m", "--master", metavar="HOST:PORT", nargs=1,
                        help="location for one of the masters")
    group1.add_argument("-e", "--executors", nargs=1, type=int, default=1,
                        help="number of Executors to be launched")

    group2 = parser.add_argument_group("Standalone Framework", "run as a Framework in standalone mode")
    group2.add_argument("-s", "--slaves", nargs="+", metavar="HOST:PORT",
                        help="list of slaves (HOST:PORT) on which to run Executors")

    group3 = parser.add_argument_group("Mesos Executor", "run as an Apache Mesos executor (using no arguments)")

    group4 = parser.add_argument_group("Standalone Executor", "run as an Executor in standalone mode")
    group4.add_argument("-p", "--port", nargs=1, metavar="PORT",
                        help="port number to use for this service")

    parser.add_argument("-f", "--feature", nargs=1, metavar="PKG.CLASS", default="run.FeatureFactory",
                        help="extension of FeatureFactory class to use for GA parameters and customizations")

    args = parser.parse_args()
    print args

    # interpret the operational modes

    if args.master:
        print "%s running as a Framework atop an Apache Mesos cluster" % (APP_NAME),
        print "with master %s and %d executor(s)" % (args.master[0], args.executors)

    elif args.slaves:
        print "%s running as a Framework in standalone mode" % (APP_NAME),
        print "with slave(s) %s" % (args.slaves)

    elif args.port:
        print "%s running as an Executor in standalone mode" % (APP_NAME),
        print "on port %s" % (args.port[0])

        # "And now, a public service announcement on behalf of the Greenlet Party..."
        monkey.patch_all()

        # launch service
        exe = Executor(port=int(args.port[0]))
        exe.start()

    else:
        print "%s running as an Executor atop an Apache Mesos cluster" % (APP_NAME)

    if args.feature:
        print "  using %s for the GA parameters and customizations" % (args.feature)
