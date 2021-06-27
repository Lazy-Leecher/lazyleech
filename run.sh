#!/bin/sh
tail -f aria2.log &
aria2c --enable-rpc=true -j5 -x5 > aria2.log 2>&1 &
python3 -m lazyleech
