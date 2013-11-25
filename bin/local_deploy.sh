#!/bin/bash -x

echo "deploying Exelixi..."
rm -rf master.zip exelixi-master
wget https://github.com/ceteri/exelixi/archive/master.zip
unzip master.zip
