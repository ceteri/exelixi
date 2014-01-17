#!/bin/bash -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# build a tarball/container for the Executor

rm -rf /tmp/exelixi.tgz
tar cvzf /tmp/exelixi.tgz ../exelixi-master/bin ../exelixi-master/src ../exelixi-master/dat

# distribute tarball/container to the Mesos slaves via HDFS

hadoop fs -rm -f -R /exelixi
hadoop fs -mkdir /exelixi
hadoop fs -put /tmp/exelixi.tgz /exelixi

# run installer on each of the Mesos slaves

printf "UserKnownHostsFile /dev/null\nStrictHostKeyChecking no\n" >> ~/.ssh/config

while read slave
do
  echo $slave
  ssh $slave 'bash -s' < $DIR/local_install.sh
  ssh $slave 'bash -s' < $DIR/local_deploy.sh

  if [ ! -z $1 ]
  then
    # optional job-specific installations
    ssh $slave 'bash -s' < $1
  fi
done