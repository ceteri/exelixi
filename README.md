# Exelixi

<b>Exelixi</b> is a distributed framework for running [genetic algorithms] at scale.
The framework is based on [Apache Mesos] and the code is mostly implemented in Python.

Why build *yet another framework* for this purpose?
[Apache Hadoop](http://hadoop.apache.org/) would be quite a poor fit, due to requirements for in-memory iteration.
[Apache Spark](http://spark.incubator.apache.org/index.html) could fit the problem more closely, in terms of iterative tasks.
However, task overhead can become high in proportion to tasks being performed ("small file problem"), 
plus there is a considerable amount of configuration required at scale.
Server-side operations and coprocessors in [Apache Cassandra](http://cassandra.apache.org/) or [Apache HBase](http://hbase.apache.org/)
might also provide a good fit for [GA] processing, but both of those also require lots of configuration.
Moreover, many of the features for these more heavyweight frameworks are not needed.

On the one hand, <b>Exelixi</b> provides the basis for a tutorial for building distributed frameworks in [Apache Mesos].
On the other hand, it provides a general-purpose [GA] platform that emphasizes _scalability_ and _fault tolerance_,
while leveraging the wealth of available Python analytics packages.


## Quick Start

More details are given below about customizing this framework for solving specific [GA] problems.
The following instructions will help you get started quickly, 
running <b>Exelixi</b> either on [Apache Mesos] or in *standalone mode*.


### System Dependencies

* [Apache Mesos] 0.14.0 rc4
* Python version 2.7, with [Anaconda] as the recommended Python platform
* Python [Setuptools](https://pypi.python.org/pypi/setuptools)
* Python [Protobuf](https://pypi.python.org/pypi/protobuf)


### Usage for [Apache Mesos] launch

First, launch an [Apache Mesos] cluster.
The following instructions are based on using the [Elastic Mesos] service,
which uses Ubuntu Linux servers running on [Amazon AWS].
However, the basic outline of steps should apply in the general case.

Once you have confirmation that your cluster is running --
[Elastic Mesos] sends you an email messages with a list of masters and slaves --
then use <code>ssh</code> to login on any of the masters:

    ssh -A -l ubuntu <master-public-ip>

You must install the [Python bindings](https://github.com/apache/mesos/tree/master/src/python) for [Apache Mesos],
In this instance the [Apache Mesos] version is *0.14.0-rc4*, so you must install the [Python egg] for that exact release.
Also, you need to install the <b>Exelixi</b> source.

On the master, run this sequence of commands:

    sudo aptitude -y install python-setuptools ; \
    sudo aptitude -y install python-protobuf ; \
    wget http://downloads.mesosphere.io/master/ubuntu/12.10/mesos_0.14.0-rc4_amd64.egg ; \
    sudo easy_install mesos_0.14.0-rc4_amd64.egg ; \
    wget https://github.com/ceteri/exelixi/archive/master.zip ; \
    unzip master.zip

Login to each of the slaves, using:

    ssh <slave-public-ip>

Repeat the sequence of commands listed above.
You can test the installation simply by attempting to import the <code>mesos</code> package into Python:

    $ python
    >>> import mesos
    >>>

If there is no exception thrown, then your installation should be complete and ready to roll!
Connect into the directory for the <b>Exelixi</b> distribution and launch the Framework,
which in turn launches the Executors remotely:

    python test_framework.py localhost:5050

If everything runs successfully, the log should conclude with a final line:

    all tasks done, and all messages received; exiting

See a [GitHub gist](https://gist.github.com/ceteri/7609046) for an example of a successful run.


### Usage for Standalone Mode

To get started quickly on a single node (i.e., your laptop) simply follow two steps.

First, launch one Executor locally:

    nohup ./src/executor.py 9311 &

Then launch a Framework to run the default [GA] as an example:

    ./src/driver.py localhost:9311 shard/config ./test
    ./src/driver.py localhost:9311 pop/init ./test
    ./src/driver.py localhost:9311 pop/next ./test
    ./src/driver.py localhost:9311 stop ./test


## Background
### Overview

In general a [GA] is a search heuristic that mimics the process of natural selection in biological evolution.
This approach is used to generate candidate solutions for optimization and search problems,
especially in cases where the parameter space is large and complex.
Note that [genetic algorithms] belong to a larger class of [evolutionary algorithms], 
and have an important sub-class of [genetic programming] which is used to synthesize computer programs that perform a user-defined task.

Effectively, a [GA] can be applied for partial automation of "think out of the box" ideation in preliminary design.
While the candidate solutions obtained from a [GA] may not be used directly,
they inform domain experts how to derive novel designs from first principles, thereby accelerating design iterations substantially.
In terms of relationship to [machine learning], this approach approximates a [stochastic gradient descent] where
the parameter space is quite large and a differentiable objective function may not be feasible.

### Operation

In a [GA], a _Population_ of candidate solutions (called _Individuals_) to an optimization problem gets evolved toward improved solutions.
Each candidate solution has a _feature set_ -- i.e., its "chromosomes", if you will -- which can be altered and recominbed.
The _fitness_ for each Individual gets evaluated (or approximated) using a _fitness function_ applied to its feature set.

Evolution starts with a set of randomly generated Individuals, then iterates through successive _generations_.
A stochastic process called _selection_ preserves the Individuals with better fitness as _parents_ for the next generation.
Some get randomly altered, based on a _mutation_ operation.
Pairs of parents selected at random (with replacement) from the Population are used to "breed" new Individuals,
based on a _crossover_ operation.

The algorithm terminates when the Population reaches some user-defined condition.
For example: 
* acceptable fitness for some Individual
* threshold aggregate error for the Population overall
* maximum number of generations iterated
* maximum number of Individuals evalutated


## Implementation
### Components

_FeatureFactory_:
a base class for configuration and customization of the [GA] problem to be solved, which generates and evaluates feature sets

_Individual_:
an candidate solution, represented by a feature set plus a fitness value obtained by applying a fitness function to that feature set

_Population_:
a collection of Individuals, which in turn breed other Individuals

_FossilRecord_:
an archive of Individuals that did not survive, persisted to durable storage and used to limit ergodic behaviors in search --
and also used for analysis after an algorithm run terminates

_Executor_:
a service running on a slave node in the cluster, responsible for computing shards of the Population

_Framework_:
a long-running process that maintains state for the system parameters and models parameters,
obtains resources for the Executors, coordinates Executors through successive generations,
and reports results; also handles all of the user interaction


### Class: FeatureFactory

To implement a [GA] in <b>Exelixi</b>,
subclass the _FeatureFactory_ class (in <code>src/run.py</code>) to customize the following operations:
* handle serializing/deserializing a feature set
* randomly generate a feature set
* calculate (or approximate) a fitness function
* mutate a feature set
* crossover a pair of parents to produce a child
* test the terminating condition

Then customize the model parameters:
  * *n_gen*: maximum number of generations
  * *n_pop*: maximum number of "live" Individuals at any point
  * *max_pop*: maximum number of Individuals explored in the feature space during an algorithm run
  * *term_limit*: a threshold used for testing the terminating condition
  * *hist_granularity*: number of decimal places in fitness values used to construct the _fitness histogram_
  * *selection_rate*: fraction of "most fit" Individuals selected as parents in each generation
  * *mutation_rate*: random variable for applying mutation to an Individual retained for diversity

In general, the other classes cover most use cases and rarely need modifications.


### Class: Individual

An _Individual_ represents a candidate solution.
Individuals get persisted in durable storage as key/value pairs.
The value consists of a tuple <code>[fitness value, generation, feature set]</code> 
and a unique key is constructed from a [SHA-3] digest of the JSON representing the feature set. 

Let's consider how to persist an Individual in the Fossil Record given:
* a [UUID] as a job's unique prefix, e.g., <code>048e9fae50c311e3a4cd542696d7e175</code>
* a unique key, e.g., <code>BC19234D</code>
* a fitness value, e.g., <code>0.5654</code>
* a generation number, e.g., <code>231</code>
* JSON representing a feature set, e.g., <code>(1, 5, 2)</code>

In that case, the Individual would be represented in tab-separated format (TSV) as the pair:

    hdfs://048e9fae50c311e3a4cd542696d7e175/0b799066c39a673d84133a484c2bf9a6b55eae320e33e0cc7a4ade49, [0.5654, 231, [1, 5, 2]]


### Class: Framework

A _Framework_ is a long-running process that:
* parses command-line options from the user
* generates a [UUID] for each attempted algorithm run
* maintains _operational state_ (e.g., system parameters) in [Zookeeper]
  * *prefix*: unique directory prefix in [HDFS] based on generated [UUID]
  * *n_exe*: number of allocated Executors
  * *exe_url*: download URL for Executor tarball (customized Python classes)
  * list of Executor endpoints from [Marathon]
  * *current_gen*: current generation count
* receives _logical state_ (e.g., model parameters) from customized Python classes
* initializes the pool of Executors
* iterates through the phases of each generation (selection/mutation, breeding, evaluation)
* restores state for itself or for any Executor after a failure
* enumerates results at any point -- including final results after an algorithm run terminates

Resources allocated for each Executor must be sufficient to support a Population shard of *n_pop* / *n_exe* Individuals.


### Class: Executor

An _Executor_ is a service running on a [Apache Mesos] slave that:
* maintains _operational state_ (e.g., system parameters) in memory
  * *prefix*: unique directory prefix in [HDFS] based on generated [UUID]
  * *shard_id*: unique identifier for this shard
* implements an in-memory distributed cache backed by [HDFS] (with write-behinds and checkpoints)
* provides a lookup service for past/present Individuals in the feature space via a [bloom filter]
* generates a shard as a pool of "live" Individuals at initialization or recovery
* maintains a shard of "live" Individuals in memory
* enumerates the Individuals in the shard of the Population at any point
* calculates a partial histogram for the distribution of fitness
* shuffles the local Population among neighboring Executors via a [hash ring]
* applies a filter to "live" Individuals to select parents for the next generation
* handles mutation, breeding, and evaluation of "live" Individuals
* persists serialized Individuals to durable storage (write-behinds)
* recovers a shard from the last checkpoint, after failures

The lookup service which implements the [distributed hash table] in turn leverages 
a [hash ring] to distribute Individuals among neighboring shards of the Population and a [bloom filter] for 
a fast, space-efficient, probabilistic set membership function which has no false negatives but allows rare false positives.
The [hash ring] helps to "shuffle" the genes of the Population among different shards, to enhance the breeding pair selection.
In essence, this aspect allows for [GA] problems to scale-out horizontally.
The [bloom filter] introduces a small rate of false positives in the Individual lookup (data loss), 
as a trade-off for large performance gains.
This also forces a pre-defined limit on the number of Individuals explored in the feature space during an algorithm run.

[REST] services and internal tasks for the Executors are implement using [gevents],
a coroutine library that provides concurrency on top of _libevent_.


## Observations about Distributed Systems

Effectively, a [GA] implements a stochastic process over a [content addressable memory], to optimize a non-convex search space.
Given use of [HDFS] for distributed storage, then much of the architecture resembles a [distributed hash table] which tolerates data loss.

Note that feature set serialization (key construction) only needs to be performed once per Individual,
and the fitness function calculation only needs to be performed on "live" Individuals in the current Population.
Consequently, if mutation is considered as "replacement", then there is a limited amount of mutable state in the Individuals.
This allows for some measure of _idempotence_ in the overall data collection,
e.g., append-only updates to [HDFS], which can be used to reconstruct state following a node or process failure.

Also, the algorithm is tolerant of factors that often hinder distributed systems:
* _eventual consistency_ in the durable storage
* _data loss_ of partial solutions, e.g., a [bloom filter] false positive, or when an Executor fails, etc.

In the latter case when an Executor process is lost, the Framework can simply launch another Executor on the cluster 
(via [Marathon]) and have it restore its shard of Individuals from its last good checkpoint.
In general, limited amounts of data loss serve to add stochastic aspects to the search, and may help accelerate evolution.


## Acknowledgements

[Bill Worzel](http://www.linkedin.com/pub/bill-worzel/12/9b4/4b3),
[Niklas Nielsen](https://github.com/nqn),
[Jason Dusek](https://github.com/solidsnack),
[Alek Storm](https://github.com/alekstorm),
[Erich Nachbar](https://github.com/enachb),
[Tobi Knaup](https://github.com/guenter),
[Flo Leibert](https://github.com/florianleibert).


## Current Status

* 2013-11-23 first successful launch of customized framework/executor on [Elastic Mesos]
* 2013-11-21 running one master/one slave only (e.g., on a laptop)


### TODO

* remote shell script to manage all master/slave installations
* integrate [Apache Mesos] <code>test_framework.py</code> and <code>test_executor.py</code>
* articulate all of the [REST] endpoint services
* support for multiple Executors in the [hash ring]
* shard checkpoint to [HDFS]
* shard recovery from [HDFS]
* saving/recovering Framework state in [Zookeeper]
* optimize [bloom filter] settings as a function of the *max_pop* and *n_exe* parameters
* <code>Makefile</code> to build tarball for Executor downloads


[Amazon AWS]: http://aws.amazon.com/
[Anaconda]: https://store.continuum.io/cshop/anaconda/
[Apache Mesos]: http://mesos.apache.org/
[Elastic Mesos]: https://elastic.mesosphere.io/
[GA]: http://en.wikipedia.org/wiki/Genetic_algorithm
[HDFS]: http://hadoop.apache.org/
[JSON]: http://www.json.org/
[Marathon]: https://github.com/mesosphere/marathon
[Python egg]: https://wiki.python.org/moin/egg
[REST]: http://www.ics.uci.edu/~taylor/documents/2002-REST-TOIT.pdf
[SHA-3]: http://en.wikipedia.org/wiki/SHA-3
[UUID]: http://tools.ietf.org/html/rfc4122.html
[Zookeeper]: http://zookeeper.apache.org/
[bloom filter]: http://code.activestate.com/recipes/577684-bloom-filter/
[content addressable memory]: http://en.wikipedia.org/wiki/Content-addressable_memory
[distributed hash table]: http://en.wikipedia.org/wiki/Distributed_hash_table
[evolutionary algorithms]: http://en.wikipedia.org/wiki/Evolutionary_algorithm
[genetic algorithms]: http://en.wikipedia.org/wiki/Genetic_algorithm
[genetic programming]: http://en.wikipedia.org/wiki/Genetic_programming
[gevents]: http://www.gevent.org/gevent.wsgi.html
[hash ring]: http://amix.dk/blog/post/19367
[machine learning]: http://en.wikipedia.org/wiki/Machine_learning
[stochastic gradient descent]: http://en.wikipedia.org/wiki/Stochastic_gradient_descent
