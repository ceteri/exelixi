#!/bin/bash -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

printf "UserKnownHostsFile /dev/null\nStrictHostKeyChecking no\n" >> ~/.ssh/config

while read slave
do
  echo $slave
  ssh $slave 'bash -s' < $DIR/local_install.sh
  ssh $slave 'bash -s' < $DIR/local_deploy.sh
done