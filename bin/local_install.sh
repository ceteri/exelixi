#!/bin/bash -x

EGG="mesos_0.14.0-rc4_amd64.egg"

echo "installing Python/Mesos..."
sudo aptitude -y install python-setuptools
sudo aptitude -y install python-protobuf
wget http://downloads.mesosphere.io/master/ubuntu/12.10/$EGG
sudo easy_install $EGG

echo "testing Python/Mesos..."
python -c 'import mesos'
