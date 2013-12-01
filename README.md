# Exelixi

<b>Exelixi</b> is a distributed framework for running [genetic algorithms] at scale.
The framework is based on [Apache Mesos] and the code is mostly implemented in Python.

Please see the [project wiki](https://github.com/ceteri/exelixi/wiki) for more details.


### Quick Start

To check out the [GA] on a laptop (with Python 2.7 installed), simply run:

    ./src/ga.py

For help with command line options:

    ./src/exelixi.py -h

Otherwise, to run at scale, the following steps will help you get <b>Exelixi</b> running on [Apache Mesos].
First, launch an [Apache Mesos] cluster.
The following instructions are based on using the [Elastic Mesos] service,
which uses Ubuntu Linux servers running on [Amazon AWS].
Even so, the basic outline of steps shown here apply in general.

Once you have confirmation that your cluster is running --
[Elastic Mesos] sends you an email messages with a list of masters and slaves --
then use <code>ssh</code> to login on any of the masters:

    ssh -A -l ubuntu <master-public-ip>

You must install the [Python bindings](https://github.com/apache/mesos/tree/master/src/python) for [Apache Mesos],
In this instance the [Apache Mesos] version is *0.14.0-rc4*, so you must install the [Python egg] for that exact release.
Also, you need to install the <b>Exelixi</b> source.

On the master, download the <code>master</code> branch of the <b>Exelixi</b> code repo on GitHub and install the required libraries:

    wget https://github.com/ceteri/exelixi/archive/master.zip ; \
    unzip master.zip ; \
    cd exelixi-master ; \
    ./bin/local_install.sh

Next, run the installation commands on each of the slaves:

    ./src/exelixi.py -n localhost:5050 | ./bin/install.sh

Now launch the Framework, which in turn launches the Executors remotely on slave nodes.
In the following case, it runs on two slave nodes:

    ./src/exelixi.py -m localhost:5050 -e 2

If everything gets set up successfully, the log should conclude with a final line:

    all executors launched and init tasks completed

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
