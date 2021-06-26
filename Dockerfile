FROM ubuntu:20.04

COPY run.sh /
RUN apt update && apt install -y --no-install-recommends python3 python3-pip ffmpeg aria2 file && rm -rf /var/lib/apt/lists/*
