#!/bin/bash

set -ex

export PATH=/snap/bin:$PATH

sudo apt update
sudo apt install -y snapd

sudo snap install --classic snapcraft
sudo snap install --classic lxd
sudo lxd init --auto

sudo snapcraft --use-lxd
