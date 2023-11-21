#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

container_name="chemical-interactions"
tag="latest"

docker build -f Dockerfile -t $container_name:$tag ..
