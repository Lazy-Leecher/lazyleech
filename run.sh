#!/bin/sh
touch aria2.log lazyleech.log
tail -f aria2.log &
tail -f lazyleech.log &
aria2c --enable-rpc=true -j5 -x5 > aria2.log 2>&1 &
python3 -m lazyleech > lazyleech.log 2>&1
