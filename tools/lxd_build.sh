#!/bin/bash

set -ex

export PATH=/snap/bin:$PATH

sudo apt update
# install Firefox which will be used for Web UI testing in a headless mode.
sudo apt install -y firefox-geckodriver python3-petname python3-selenium

# Setup snapd and snapcraft
sudo apt install -y snapd
sudo snap install --classic snapcraft
sudo snap install --classic lxd
sudo lxd init --auto

# Build our snap!
sudo snapcraft --use-lxd
