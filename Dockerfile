FROM ubuntu:20.04

COPY run.sh requirements.txt testwatermark.jpg /app/
COPY lazyleech /app/lazyleech/
RUN apt update && apt install -y --no-install-recommends python3 python3-pip ffmpeg aria2 file && rm -rf /var/lib/apt/lists/*
RUN echo "Etc/UTC" > /etc/timezone
RUN pip3 install -r /app/requirements.txt
COPY . .
CMD ["bash","run.sh"]
