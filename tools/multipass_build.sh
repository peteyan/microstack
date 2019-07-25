#!/bin/bash

set -ex

export PATH=/snap/bin:$PATH

sudo snap install --classic snapcraft
sudo snap install --classic --beta multipass

snapcraft --debug
