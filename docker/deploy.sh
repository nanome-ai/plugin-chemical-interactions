#!/bin/bash

if [ -n "$(docker ps -aqf name=nanome-chemical-interactions)" ]; then
    echo "removing exited container"
    docker rm -f nanome-chemical-interactions
fi

docker run -d \
--name nanome-chemical-interactions \
--restart unless-stopped \
-e ARGS="$*" \
nanome-chemical-interactions
