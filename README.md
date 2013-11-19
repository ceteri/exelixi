# Exelixi

*Exelixi* is a distributed framework for running [genetic algorithms] at scale.
The framework is based on [Apache Mesos] and the code is mostly implemented in Python.

On the one hand, this project provides a tutorial for building distributed frameworks in [Apache Mesos].
On the other hand, it provides a general-purpose [GA] platform that emphasizes _scalability_ and _fault tolerance_,
while leveraging the wealth of available Python analytics packages.


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

Evolution starts with randomly generated Individuals, then iterates through successive _generations_.
During each generation, a stochastic process called _selection_ preserves the better fit Individuals as _parents_ for the next generation.
Some are randomly altered, based on a _mutation_ operation.
Pairs of parents selected at random (with replacement) from the Population are used to "breed" new Individuals,
based on a _crossover_ operation.

The algorithm terminates when the Population reaches some user-defined condition.
For example: 
* maximum number of generations
* acceptable fitness for some Individual
* threshold aggregate error for the Population overall


### Components

_Individual_:
an candidate solution, represented by a feature set plus a fitness value obtained by applying a fitness function to that feature set

_Population_:
a collection of Individuals, which in turn breed other Individuals

_Fossil Record_:
an archive of Individuals that did not survive, persisted to durable storage and used to limit ergodic behaviors in search --
and also used for analysis after an algorithm run terminates

_Framework_:
a long-running process that maintains state for the system parameters and models parameters, obtains resources for the Executors, coordinates Executors through successive generations, and reports results; also handles all of the user interaction

_Executor_:
a service running on a slave node in the cluster, responsible for computing a subset of the Population


## Implementation
### Design For Scalability

To implement a [GA] in Exelixi, simply extend two classes in Python.
First, subclass the _Individual_ class to customize the following operations:
* randomly generate a feature set
* handle codex for serializing/deserializing a feature set
* mutate a feature set
* breed a pair of parents to produce a child
* calculate (or approximate) a fitness function

Individuals get represented as key/value pairs.
The value consists of a tuple <code>[fitness value, generation]</code> 
and a unique key is constructed from a [SHA-3] digest of the JSON representing the feature set. 

Let's consider how to persist an Individual in the Fossil Record given:
* a [UUID] as a job's unique prefix, e.g., <code>048e9fae50c311e3a4cd542696d7e175</code>
* a unique key, e.g., <code>BC19234D</code>
* a fitness value, e.g., <code>0.5654</code>
* a generation number, e.g., <code>231</code>
* JSON representing a feature set, e.g., <code>(1, 5, 2)</code>

In that case, the Individual would be represented as the pair:

    hdfs://048e9fae50c311e3a4cd542696d7e175/0b799066c39a673d84133a484c2bf9a6b55eae320e33e0cc7a4ade49, [0.5654, 231, [1, 5, 2]]


### Framework

The _framework_ is a long-running process that:
* parses command-line options from the user
* generates a [UUID] for each attempted algorithm run
* maintains _operational state_ (e.g., system parameters) in [Zookeeper]
  * *prefix*: unique directory prefix in [HDFS] 
  * *n_exe*: number of allocated Executors
  * *exe_url*: URL for customized Python classes tarball
  * list of Executor endpoints from [Marathon]
  * *current_gen*: current generation count
* receives _logical state_ (e.g., model parameters) from customized Python classes
  * *n_pop*: maximum number of "live" Individuals at any point
  * *n_gen*: maximum number of generations
  * *limit*: a threshold used for testing the terminating condition
  * *resolution*: number of decimal places in fitness values used to construct the _fitness histogram_
  * *selection_rate*: fraction of "most fit" Individuals selected as parents in each generation
  * *diversity_rate*: random variable for selecting "less fit" Individuals retained for diversity
  * *mutation_rate*: random variable for applying mutation to an Individual retained for diversity
* generates the [HDFS] directory prefix
* initializes the pool of Executors
* iterates through the phases of each generation (selection/mutation, breeding, evaluation, reporting, shuffle)
* restores state for itself or for any Executor after a failure
* reports results at any point -- including final results after an algorithm run terminates

Resources allocated for each Executor must be sufficient to support a Population subset of *n_pop* / *n_exe* Individuals.


### Executor

An _executor_ is a service running on a [Apache Mesos] slave that:
* implements an in-memory distributed cache backed by [HDFS] (with snapshots)
* generates a pool of "live" Individuals at initialization or recovery
* maintains "live" Individuals in memory
* provides a lookup service for the feature space vs. fitness of known attempts
* persists serialized Individuals to durable storage
* calculates a partial histogram for the distribution of fitness
* shuffles the local Population among neighboring Executors
* applies a filter to "live" Individuals to select parents for the next generation
* handles mutation, breeding, and evaluation of "live" Individuals


### Observations about Distributed Systems

Effectively, a [GA] implements a stochastic process over a [content addressable memory], to optimize a convex search space.
Given use of [HDFS] for distributed storage, then much of the architecture resembles a [distributed hash table] which tolerates data loss.

Note that feature set serialization (key construction) and fitness function calculation only need to be performed once per Individual.
In other words, there is no mutable "state" in the Individuals, if mutation is considered as replacement.
This allows for _idempotence_ in the overall data collection,
e.g., append-only updates to [HDFS], which can be used to reconstruct state following a node or process failure.

Also, the algorithm is tolerant of several factors that often hinder distributed systems:
* _eventual consistency_ in the durable storage
* _race conditions_ in the lookup of Individuals (having some duplicates/overlap adds minor performance overhead)
* _data loss_ of partial solutions (e.g., when an Executor fails)

In the latter case, when an Executor process is lost, the Framework can simply launch another Executor on the cluster 
(via [Marathon]) and have it generate new Individuals.
That contingency adds another stochastic component to the search, and in some cases may help accelerate evolution.


[Apache Mesos]: http://mesos.apache.org/
[GA]: http://en.wikipedia.org/wiki/Genetic_algorithm
[HDFS]: http://hadoop.apache.org/
[JSON]: http://www.json.org/
[Marathon]: https://github.com/mesosphere/marathon
[SHA-3]: http://en.wikipedia.org/wiki/SHA-3
[UUID]: http://tools.ietf.org/html/rfc4122.html
[Zookeeper]: http://zookeeper.apache.org/
[content addressable memory]: http://en.wikipedia.org/wiki/Content-addressable_memory
[distributed hash table]: http://en.wikipedia.org/wiki/Distributed_hash_table
[evolutionary algorithms]: http://en.wikipedia.org/wiki/Evolutionary_algorithm
[genetic algorithms]: http://en.wikipedia.org/wiki/Genetic_algorithm
[genetic programming]: http://en.wikipedia.org/wiki/Genetic_programming
[machine learning]: http://en.wikipedia.org/wiki/Machine_learning
[stochastic gradient descent]: http://en.wikipedia.org/wiki/Stochastic_gradient_descent
