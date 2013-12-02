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
from collections import OrderedDict
from ga import APP_NAME
from json import loads
from service import Framework, Worker
from urllib2 import urlopen
import psutil
import socket
import sys


######################################################################
## utilities

def get_telemetry ():
    """get system resource telemetry on a Mesos slave via psutil"""
    telemetry = OrderedDict()

    telemetry["ip_addr"] = socket.gethostbyname(socket.gethostname())

    telemetry["mem_free"] =  psutil.virtual_memory().free

    telemetry["cpu_num"] = psutil.NUM_CPUS

    x = psutil.cpu_times()
    telemetry["cpu_times"] = OrderedDict([ ("user", x.user), ("system", x.system), ("idle", x.idle) ])

    x = psutil.disk_usage('/tmp')
    telemetry["disk_usage"] = OrderedDict([ ("free", x.free), ("percent", x.percent) ])

    x = psutil.disk_io_counters()
    telemetry["disk_io"] = OrderedDict([ ("read_count", x.read_count), ("write_count", x.write_count), ("read_bytes", x.read_bytes), ("write_bytes", x.write_bytes), ("read_time", x.read_time), ("write_time", x.write_time) ])

    x = psutil.network_io_counters()
    telemetry["network_io"] = OrderedDict([ ("bytes_sent", x.bytes_sent), ("bytes_recv", x.bytes_recv), ("packets_sent", x.packets_sent), ("packets_recv", x.packets_recv), ("errin", x.errin), ("errout", x.errout), ("dropin", x.dropin), ("dropout", x.dropout) ])

    return telemetry


def get_master_state (master_uri):
    """get current state, represented as JSON, from the Mesos master"""
    response = urlopen("http://" + master_uri + "/master/state.json")
    return loads(response.read())


def get_master_leader (master_uri):
    """get the host:port for the Mesos master leader"""
    state = get_master_state(master_uri)
    return state["leader"].split("@")[1]


def report_slave_list (master_uri):
    """report a list of slave IP addr, one per line"""
    state = get_master_state(get_master_leader(master_uri))

    for s in state["slaves"]:
        print s["pid"].split("@")[1].split(":")[0] 


######################################################################
## command line arguments

def parse_cli_args ():
    parser = ArgumentParser(prog="Exelixi", usage="one of the operational modes shown below...", add_help=True,
                            description="Exelixi, a distributed framework for genetic algorithms, based on Apache Mesos")

    group1 = parser.add_argument_group("Mesos Framework", "run as a Framework on an Apache Mesos cluster")
    group1.add_argument("-m", "--master", metavar="HOST:PORT", nargs=1,
                        help="location for one of the masters")
    group1.add_argument("-e", "--executors", nargs=1, type=int, default=[1],
                        help="number of Executors to be launched")

    group1.add_argument("--cpu", nargs=1, type=int, default=[1],
                        help="CPU allocation per Executor, as CPU count")
    group1.add_argument("--mem", nargs=1, type=int, default=[32],
                        help="MEM allocation per Executor, as MB/shard")

    group2 = parser.add_argument_group("Standalone Framework", "run as a Framework in standalone mode")
    group2.add_argument("-s", "--slaves", nargs="+", metavar="HOST:PORT",
                        help="list of slaves (HOST:PORT) on which to run Executors")

    group3 = parser.add_argument_group("Mesos Executor", "run as an Apache Mesos executor (using no arguments)")

    group4 = parser.add_argument_group("Standalone Executor", "run as an Executor in standalone mode")
    group4.add_argument("-p", "--port", nargs=1, metavar="PORT",
                        help="port number to use for this service")

    group5 = parser.add_argument_group("Nodes", "enumerate the slave nodes in an Apache Mesos cluster")
    group5.add_argument("-n", "--nodes", nargs="?", metavar="HOST:PORT",
                        help="location for one of the masters")

    parser.add_argument("--feature", nargs=1, metavar="PKG.CLASS", default=["run.FeatureFactory"],
                        help="extension of FeatureFactory class to use for GA parameters and customizations")
    parser.add_argument("--prefix", nargs=1, default=["hdfs://exelixi"],
                        help="path prefix for durable storage")

    return parser.parse_args()


if __name__=='__main__':
    # interpret CLI arguments
    args = parse_cli_args()
    #print args

    if args.nodes:
        # query and report the slave list, then exit
        report_slave_list(args.nodes)
        sys.exit(0)

    # report settings for optional features
    opts = []

    if args.feature:
        opts.append(" ...using %s for the GA parameters and customizations" % (args.feature[0]))

    if args.prefix:
        opts.append(" ...using %s for the path prefix in durable storage" % (args.prefix[0]))

    # handle the different operational modes
    if args.master:
        print "%s: running a Framework atop an Apache Mesos cluster" % (APP_NAME),
        print "with master %s and %d executor(s)" % (args.master[0], int(args.executors[0]))

        for x in opts:
            print x

        from sched import MesosScheduler

        master_uri = get_master_leader(args.master[0])
        ## NB: TODO make path relative
        exe_path = "/home/ubuntu/exelixi-master/src/exelixi.py"

        # run Mesos driver to launch Framework and manage resource offers
        driver = MesosScheduler.start_framework(master_uri, exe_path, int(args.executors[0]), args.feature[0], args.prefix[0], args.cpu[0], args.mem[0])
        MesosScheduler.stop_framework(driver)

    elif args.slaves:
        print "%s: running a Framework in standalone mode" % (APP_NAME),
        print "with slave(s) %s" % (args.slaves)

        for x in opts:
            print x

        # run Framework orchestration via REST endpoints on the Executors
        fra = Framework(args.feature, args.prefix)
        fra.set_exe_list(args.slaves)
        fra.orchestrate()

    elif args.port:
        print "%s: running a service on port %s" % (APP_NAME, args.port[0])

        try:
            svc = Worker(port=int(args.port[0]))
            svc.start()
        except KeyboardInterrupt:
            pass

    else:
        print "%s: running an Executor on an Apache Mesos slave" % (APP_NAME)

        from sched import MesosExecutor

        try:
            MesosExecutor.run_executor()
        except KeyboardInterrupt:
            pass
