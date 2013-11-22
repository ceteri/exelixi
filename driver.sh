#!/bin/bash -x

./src/driver.py localhost:9311 shard/config ./test
./src/driver.py localhost:9311 pop/init ./test
./src/driver.py localhost:9311 pop/next ./test
./src/driver.py localhost:9311 stop ./test
