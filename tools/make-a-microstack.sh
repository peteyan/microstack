#!/bin/bash
##############################################################################
#
# Make a microstack!
#
# This is a tool to very quickly spin up a multipass vm, install
# microstack (from the compiled local .snap), and get a shell in
# microstack's environment.
#
# It requires that you have installed petname.
#
##############################################################################

set -ex

DISTRO=18.04
MACHINE=$(petname)

# Make a vm
multipass launch --cpus 2 --mem 16G $DISTRO --name $MACHINE

# Install the snap
multipass copy-files microstack_stein_amd64.snap $MACHINE:
multipass exec $MACHINE -- \
          sudo snap install --classic --dangerous microstack*.snap

# Drop the user into a snap shell, as root.
multipass exec $MACHINE -- \
          sudo snap run --shell microstack.init

