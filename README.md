# Exelixi

**Exelixi** is a distributed framework based on [Apache Mesos],
mostly implemented in Python using [gevent] for high-performance concurrency
It is intended to run cluster computing jobs (partitioned batch jobs, which include some messaging) in pure Python.
By default, it runs [genetic algorithms] at scale.
However, it can handle a broad range of other problem domains by 
using `--uow` command line option to override the `UnitOfWorkFactory` class definition.

Please see the [project wiki](https://github.com/ceteri/exelixi/wiki) for more details,
including a [tutorial](https://github.com/ceteri/exelixi/wiki/Tutorial:-Fog-Computing-at-Hella-Scale)
on how to build Mesos-based frameworks.


### Quick Start

To check out the [GA] on a laptop (with Python 2.7 installed), simply run:

    ./src/ga.py

Otherwise, to run at scale, the following steps will help you get **Exelixi** running on [Apache Mesos].
For help in general with command line options:

    ./src/exelixi.py -h

The following instructions are based on using the [Elastic Mesos] service,
which uses Ubuntu Linux servers running on [Amazon AWS].
Even so, the basic outline of steps shown here apply in general.

First, launch an [Apache Mesos] cluster.
Once you have confirmation that your cluster is running
(e.g., [Elastic Mesos] sends you an email messages with a list of masters and slaves)
then use `ssh` to login on any of the masters:

    ssh -A -l ubuntu <master-public-ip>

You must install the [Python bindings](https://github.com/apache/mesos/tree/master/src/python) for [Apache Mesos].
The default version of Mesos changes in this code as there are updates to [Elastic Mesos](https://elastic.mesosphere.io/),
since the tutorials are based on that service.
You can check [http://mesosphere.io/downloads/](http://mesosphere.io/downloads/) for the latest.
If you run Mesos in different environment, 
simply make a one-line change to the `EGG` environment variable in the `bin/local_install.sh` script.
Also, you need to install the **Exelixi** source.

On the Mesos master, download the `master` branch of the **Exelixi** code repo on GitHub and install the required libraries:

    wget https://github.com/ceteri/exelixi/archive/master.zip ; \
    unzip master.zip ; \
    cd exelixi-master ; \
    ./bin/local_install.sh

If you've customized the code by forking your own GitHub code repo, then substitute that download URL instead.
Alternatively, if you've customized by subclassing the `uow.UnitOfWorkFactory` default [GA],
then place that Python source file into the `src/` subdirectory.

Next, run the installation command on the master, to set up each of the slaves:

    ./src/exelixi.py -n localhost:5050 | ./bin/install.sh

Now launch the Framework, which in turn launches the worker services remotely on slave nodes.
In the following case, it runs workers on two slave nodes:

    ./src/exelixi.py -m localhost:5050 -w 2

Once everything has been set up successfully, the log file in `exelixi.log` will show a line:

    all worker services launched and init tasks completed

From there, the [GA] runs.
See a [GitHub gist](https://gist.github.com/ceteri/7609046) for an example of a successful run.


### Blame List

[Paco Nathan](https://github.com/ceteri)


[Amazon AWS]: http://aws.amazon.com/
[Apache Mesos]: http://mesos.apache.org/
[Elastic Mesos]: https://elastic.mesosphere.io/
[GA]: http://en.wikipedia.org/wiki/Genetic_algorithm
[Python egg]: https://wiki.python.org/moin/egg
[genetic algorithms]: http://en.wikipedia.org/wiki/Genetic_algorithm
[gevent]: http://www.gevent.org/
