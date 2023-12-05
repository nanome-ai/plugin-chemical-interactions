#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

image_name="chemical-interactions"
tag="latest"

docker build -f Dockerfile -t $image_name:$tag ..
