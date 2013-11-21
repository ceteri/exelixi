# Exelixi

*Exelixi* is a distributed framework for running [genetic algorithms] at scale.
The framework is based on [Apache Mesos] and the code is mostly implemented in Python.

On the one hand, this project provides a tutorial for building distributed frameworks in [Apache Mesos].
On the other hand, it provides a general-purpose [GA] platform that emphasizes _scalability_ and _fault tolerance_,
while leveraging the wealth of available Python analytics packages.


## Getting Started

More details are given below -- in terms of customizing the [GA] platform for solving specific problems.
However, to get started quickly on a single node (i.e., your laptop) simply follow two steps.

First, launch one Executor locally:

    nohup executor.py 9311 &

Then launch a Framework to run the default [GA]:

    ./driver.py localhost:9311 pop/init ./test
    ./driver.py localhost:9311 stop ./test

Note that it is recommended to use [Anaconda] as the Python version 2.7 platform.


## Background

### Overview

In general a [GA] is a search heuristic that mimics the process of natural selection in biological evolution.
This approach is used to generate candidate solutions for optimization and search problems,
especially in cases where the parameter space is large and complex.
Note that [genetic algorithms] belong to a larger class of [evolutionary algorithms], 
and have an important sub-class of [genetic programming] which is used to synthesize computer programs that perform a user-defined task.

Effectively, a [GA] can be applied for partial automation of "think out of the box" ideation in preliminary design.
While the candidate solutions obtained from a [GA] may not be used directly,
they inform domain experts how to derive novel design from _first principles_, thereby accelerating iterations substantially.
In terms of relationship to [machine learning], this approach approximates a [stochastic gradient descent] where
the parameter space is quite large and a differentiable objective function may not be immediately apparent.

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


### Components

_Individual_:
an candidate solution, represented by a feature set plus a fitness value obtained by applying a fitness function to that feature set

_Population_:
a collection of Individuals, which in turn breed other Individuals

_Fossil Record_:
an archive of Individuals that did not survive, persisted to durable storage and used to limit ergodic behaviors in search --
and also used for analysis after an algorithm run terminates

_Framework_:
a long-running process that maintains state for the system parameters and models parameters,
obtains resources for the Executors, coordinates Executors through successive generations,
and reports results; also handles all of the user interaction

_Executor_:
a service running on a slave node in the cluster, responsible for computing shards of the Population


## Implementation
### Design For Scalability

To implement a [GA] in Exelixi, simply extend two classes in Python.
First, subclass the _FeatureSet_ class to customize the following operations:
* handle codex for serializing/deserializing a feature set
* randomly generate a feature set
* mutate a feature set
* breed a pair of parents to produce a child
* calculate (or approximate) a fitness function

Individuals get represented as key/value pairs.
The value consists of a tuple <code>[fitness value, generation, feature set]</code> 
and a unique key is constructed from a [SHA-3] digest of the JSON representing the feature set. 

Let's consider how to persist an Individual in the Fossil Record given:
* a [UUID] as a job's unique prefix, e.g., <code>048e9fae50c311e3a4cd542696d7e175</code>
* a unique key, e.g., <code>BC19234D</code>
* a fitness value, e.g., <code>0.5654</code>
* a generation number, e.g., <code>231</code>
* JSON representing a feature set, e.g., <code>(1, 5, 2)</code>

In that case, the Individual would be represented in storage in tab-seperated format (TSV) as the pair:

    hdfs://048e9fae50c311e3a4cd542696d7e175/0b799066c39a673d84133a484c2bf9a6b55eae320e33e0cc7a4ade49, [0.5654, 231, [1, 5, 2]]


### Framework

The _framework_ is a long-running process that:
* parses command-line options from the user
* generates a [UUID] for each attempted algorithm run
* generates the [HDFS] directory prefix
* maintains _operational state_ (e.g., system parameters) in [Zookeeper]
  * *prefix*: unique directory prefix in [HDFS] based on generated [UUID]
  * *n_exe*: number of allocated Executors
  * *exe_url*: URL for customized Python classes tarball
  * list of Executor endpoints from [Marathon]
  * *current_gen*: current generation count
* receives _logical state_ (e.g., model parameters) from customized Python classes
  * *n_gen*: maximum number of generations
  * *n_pop*: maximum number of "live" Individuals at any point
  * *max_pop*: maximum number of Individuals explored in the feature space during an algorithm run
  * *term_limit*: a threshold used for testing the terminating condition
  * *hist_granularity*: number of decimal places in fitness values used to construct the _fitness histogram_
  * *selection_rate*: fraction of "most fit" Individuals selected as parents in each generation
  * *mutation_rate*: random variable for applying mutation to an Individual retained for diversity
* initializes the pool of Executors
* iterates through the phases of each generation (selection/mutation, breeding, evaluation)
* restores state for itself or for any Executor after a failure
* enumerates results at any point -- including final results after an algorithm run terminates

Resources allocated for each Executor must be sufficient to support a Population shard of *n_pop* / *n_exe* Individuals.


### Executor

An _executor_ is a service running on a [Apache Mesos] slave that:
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


### Observations about Distributed Systems

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


[Anaconda]: https://store.continuum.io/cshop/anaconda/
[Apache Mesos]: http://mesos.apache.org/
[GA]: http://en.wikipedia.org/wiki/Genetic_algorithm
[HDFS]: http://hadoop.apache.org/
[JSON]: http://www.json.org/
[Marathon]: https://github.com/mesosphere/marathon
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
