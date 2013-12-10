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


from argparse import ArgumentParser
from os.path import abspath
from service import Framework, Worker
from util import get_master_leader, get_master_state, pipe_slave_list
import logging
import sys


######################################################################
## globals

APP_NAME = "Exelixi"


######################################################################
## command line arguments

def parse_cli_args ():
    parser = ArgumentParser(prog="Exelixi", usage="one of the operational modes shown below...", add_help=True,
                            description="Exelixi, a distributed framework for genetic algorithms, based on Apache Mesos")

    group1 = parser.add_argument_group("Mesos Framework", "run as a distributed framework on an Apache Mesos cluster")
    group1.add_argument("-m", "--master", metavar="HOST:PORT", nargs=1,
                        help="location for one of the masters")
    group1.add_argument("-w", "--workers", nargs=1, type=int, default=[1],
                        help="number of workers to be launched")

    group1.add_argument("--cpu", nargs=1, type=int, default=[1],
                        help="CPU allocation per worker, as CPU count")
    group1.add_argument("--mem", nargs=1, type=int, default=[32],
                        help="MEM allocation per worker, as MB/shard")

    group2 = parser.add_argument_group("Mesos Executor", "run as an Apache Mesos executor (using no arguments)")

    group3 = parser.add_argument_group("Standalone Framework", "run as a test framework in standalone mode")
    group3.add_argument("-s", "--slaves", nargs="+", metavar="HOST:PORT",
                        help="list of slaves (HOST:PORT) on which to run workers")

    group4 = parser.add_argument_group("Standalone Worker", "run as a test worker in standalone mode")
    group4.add_argument("-p", "--port", nargs=1, metavar="PORT",
                        help="port number to use for this service")

    group5 = parser.add_argument_group("Nodes", "enumerate the slave nodes in an Apache Mesos cluster")
    group5.add_argument("-n", "--nodes", nargs="?", metavar="HOST:PORT",
                        help="location for one of the Apache Mesos masters")

    parser.add_argument("--uow", nargs=1, metavar="PKG.CLASS", default=["uow.UnitOfWorkFactory"],
                        help="subclassed UnitOfWork definition")

    parser.add_argument("--prefix", nargs=1, default=["hdfs://exelixi"],
                        help="path prefix for durable storage")

    parser.add_argument("--log", nargs=1, default=["DEBUG"],
                        help="logging level: INFO, DEBUG, WARNING, ERROR, CRITICAL")

    return parser.parse_args()


if __name__=='__main__':
    # interpret CLI arguments
    args = parse_cli_args()

    if args.nodes:
        # query and report the slave list, then exit...
        # NB: one per line, to handle large clusters gracefully
        pipe_slave_list(args.nodes)
        sys.exit(0)

    # set up logging
    numeric_log_level = getattr(logging, args.log[0], None)

    if not isinstance(numeric_log_level, int):
        raise ValueError("Invalid log level: %s" % loglevel)

    logging.basicConfig(format="%(asctime)s\t%(levelname)s\t%(message)s", 
                        filename="exelixi.log", 
                        filemode="w",
                        level=numeric_log_level
                        )
    logging.debug(args)

    # report settings for options
    opts = []

    if args.uow:
        opts.append(" ...using %s for the UnitOfWork definitions" % (args.uow[0]))

    if args.prefix:
        opts.append(" ...using %s for the path prefix in durable storage" % (args.prefix[0]))

    # handle the different operational modes
    if args.master:
        logging.info("%s: running a Framework atop an Apache Mesos cluster", APP_NAME)
        logging.info(" ...with master %s and %d workers(s)", args.master[0], args.workers[0])

        for x in opts:
            logging.info(x)

        try:
            from resource import MesosScheduler

            master_uri = get_master_leader(args.master[0])
            exe_path = abspath(sys.argv[0])

            # run Mesos driver to launch Framework and manage resource offers
            driver = MesosScheduler.start_framework(master_uri, exe_path, args.workers[0], args.uow[0], args.prefix[0], args.cpu[0], args.mem[0])
            MesosScheduler.stop_framework(driver)
        except ImportError as e:
            logging.critical("Python module 'mesos' has not been installed", exc_info=True)
            raise

    elif args.slaves:
        logging.info("%s: running a Framework in standalone mode", APP_NAME)
        logging.info(" ...with slave(s) %s", args.slaves)

        for x in opts:
            logging.info(x)

        # run UnitOfWork orchestration via REST endpoints on the workers
        fra = Framework(args.uow[0], args.prefix[0])
        fra.set_worker_list(args.slaves)
        fra.orchestrate_uow()

    elif args.port:
        logging.info("%s: running a worker service on port %s", APP_NAME, args.port[0])

        try:
            svc = Worker(port=int(args.port[0]))
            svc.shard_start()
        except KeyboardInterrupt:
            pass

    else:
        logging.info("%s: running an Executor on an Apache Mesos slave", APP_NAME)

        try:
            from resource import MesosExecutor
            MesosExecutor.run_executor()
        except ImportError as e:
            logging.critical("Python module 'mesos' has not been installed", exc_info=True)
            raise
        except KeyboardInterrupt:
            pass
