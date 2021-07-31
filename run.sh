#!/bin/sh
touch aria2.log lazyleech.log
tail -f aria2.log &
tail -f lazyleech.log &
# https://unix.stackexchange.com/a/230676
export ARIA2_SECRET=$(tr -dc 'A-Za-z0-9!"#$%&'\''()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 100)
aria2c --enable-rpc=true "--rpc-secret=$ARIA2_SECRET" -j5 -x5 > aria2.log 2>&1 &
python3 -m lazyleech > lazyleech.log 2>&1
