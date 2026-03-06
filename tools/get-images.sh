#!/bin/bash
#
# This script returns list of container images that are managed by the charms in this repository
#
# dynamic list

set -xe

IMAGE_LIST=()
IMAGE_LIST+=($(find -type f -name metadata.yaml -exec yq '.resources | to_entries | .[] | .value | ."upstream-source"' {} \; | tr -d '"'))
printf "%s\n" "${IMAGE_LIST[@]}"
