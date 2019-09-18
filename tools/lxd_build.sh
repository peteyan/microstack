#!/bin/bash

set -ex

export PATH=/snap/bin:$PATH

sudo apt update

# Install the X virtual framebuffer, which is required for selenium
# tests of the horizon dashboard.
sudo apt install -y xvfb npm libfontconfig1
sudo npm install -g phantomjs-prebuilt
# Verify that PhantomJS, our selenium web driver, works.
phantomjs -v

# Setup snapd and snapcraft
sudo apt install -y snapd
sudo snap install --classic snapcraft
sudo snap install --classic lxd
sudo lxd init --auto

# Build our snap!
sudo snapcraft --use-lxd
