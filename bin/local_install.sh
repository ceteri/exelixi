#!/bin/bash -x

EGG="mesos_0.15.0-rc4_amd64.egg"

echo "installing Python/Mesos..."
## NB: TODO de-Ubuntu-fy the Python parts of this install, hopefully via Anaconda/conda?
sudo aptitude -y install python-setuptools
sudo aptitude -y install python-protobuf
sudo aptitude -y install python-gevent
sudo aptitude -y install python-psutil 
sudo aptitude -y install python-dev
sudo aptitude -y install python-pip

sudo pip install cython
sudo pip install git+https://github.com/kmike/hat-trie.git#egg=hat-trie

sudo aptitude -y install build-essential python-numpy python-scipy libatlas-dev libatlas3-base
sudo pip install scikit-learn
sudo pip install pandas

rm -rf $EGG
wget http://downloads.mesosphere.io/master/ubuntu/13.10/$EGG
sudo easy_install $EGG

echo "testing Python/Mesos..."
python -c 'import mesos'
