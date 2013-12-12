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

For help with command line options:

    ./src/exelixi.py -h

Otherwise, to run at scale, the following steps will help you get **Exelixi** running on [Apache Mesos].
First, launch an [Apache Mesos] cluster.
The following instructions are based on using the [Elastic Mesos] service,
which uses Ubuntu Linux servers running on [Amazon AWS].
Even so, the basic outline of steps shown here apply in general.

Once you have confirmation that your cluster is running --
[Elastic Mesos] sends you an email messages with a list of masters and slaves --
then use `ssh` to login on any of the masters:

    ssh -A -l ubuntu <master-public-ip>

You must install the [Python bindings](https://github.com/apache/mesos/tree/master/src/python) for [Apache Mesos],
In this instance the [Apache Mesos] version is *0.14.0-rc4*, so you must install the [Python egg] for that exact release.
Also, you need to install the **Exelixi** source.

On the master, download the `master` branch of the **Exelixi** code repo on GitHub and install the required libraries:

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
