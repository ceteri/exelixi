#!/bin/bash -x

echo "deploying Exelixi..."
rm -rf exelixi.tgz exelixi-master
hadoop fs -get /exelixi/exelixi.tgz
tar xvzf exelixi.tgz
