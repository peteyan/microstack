#!/bin/bash

set -ex

export PATH=/snap/bin:$PATH

sudo apt update
# install Firefox which will be used for Web UI testing in a headless mode.
sudo apt install -y firefox-geckodriver python3-petname python3-selenium

# Setup snapd and snapcraft
sudo apt install -y snapd

# Build our snap!
sudo snap install --classic snapcraft
sudo snap install lxd

sudo usermod -a -G lxd ${USER}

# Since the current shell does not have the lxd group gid, use newgrp.
newgrp lxd << END
set -ex
lxd init --auto
snapcraft --use-lxd
END