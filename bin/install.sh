#!/bin/bash -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

read slave_list
arr=$(echo $slave_list | tr " " "\n")

for slave in $arr
do
  echo $slave
  ssh $slave 'bash -s' < $DIR/local_install.sh
  ssh $slave 'bash -s' < $DIR/local_deploy.sh
  shift
done
