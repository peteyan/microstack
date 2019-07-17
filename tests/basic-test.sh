#!/bin/bash
##############################################################################
#
# This is a "basic" test script for Microstack. It will install the
# microstack snap, spin up a test instance, and verify that the test
# instance is accessible, and can access the Internet.
#
# The basic test accepts two command line arguments:
#
# -u <channel> # First installs a released snap from the named
#              # channel, in order to test basic upgrade functionality.
#
##############################################################################

# Configuration and checks
set -ex

export PATH=/snap/bin:$PATH

UPGRADE_FROM="none"
FORCE_QEMU=false

while getopts u:d:q option
do
    case "${option}"
    in
        u) UPGRADE_FROM=${OPTARG};;
        q) FORCE_QEMU=true
    esac
done

if [ ! -f microstack_rocky_amd64.snap ]; then
   echo "microstack_rocky_amd64.snap not found."
   echo "Please run snapcraft before executing the tests."
   exit 1
fi

# Functions
dump_logs () {
    export DUMP_DIR=/tmp
    if [ $(whoami) == 'zuul' ]; then
        export DUMP_DIR="/home/zuul/zuul-output/logs";
    fi
    sudo tar cvzf $DUMP_DIR/dump.tar.gz \
         /var/snap/microstack/common/log \
         /var/log/syslog
    sudo journalctl -xe --no-pager
}

# Setup
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
echo "++    Starting tests on localhost               ++"
echo "++      Upgrade from: $UPGRADE_FROM             ++"
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"

# Possibly install a release of the snap before running a test.
if [ "${UPGRADE_FROM}" != "none" ]; then
    sudo snap install --classic --${UPGRADE_FROM} microstack
fi

# Install the snap under test
sudo snap install --classic --dangerous microstack*.snap

# Comment out the above and uncomment below to install the version of
# the snap from the store.
# TODO: add this as a flag.
# sudo snap install --classic --edge microstack

# If kvm processor extensions not supported, switch to qemu
# TODO: just do this in the install step of the snap
if ! [ $(egrep "vmx|svm" /proc/cpuinfo | wc -l) -gt 0 ]; then
    FORCE_QEMU=true;
fi
if [ "$FORCE_QEMU" == "true" ]; then
    cat<<EOF > /tmp/hypervisor.conf
[DEFAULT]
compute_driver = libvirt.LibvirtDriver

[workarounds]
disable_rootwrap = True

[libvirt]
virt_type = qemu
cpu_mode = host-model
EOF
    sudo cp /tmp/hypervisor.conf \
         /var/snap/microstack/common/etc/nova/nova.conf.d/hypervisor.conf
    sudo snap restart microstack
fi

# Run microstack.launch
/snap/bin/microstack.launch breakfast || (dump_logs && exit 1)

# Verify that endpoints are setup correctly
# List of endpoints should contain 10.20.20.1
if ! /snap/bin/microstack.openstack endpoint list | grep "10.20.20.1"; then
    echo "Endpoints are not set to 10.20.20.1!";
    exit 1;
fi
# List of endpoints should not contain localhost
if /snap/bin/microstack.openstack endpoint list | grep "localhost"; then
    echo "Endpoints are not set to 10.20.20.1!";
    exit 1;
fi


# Verify that microstack.launch completed
IP=$(/snap/bin/microstack.openstack server list | grep breakfast | cut -d" " -f9)
echo "Waiting for ping..."
PINGS=1
MAX_PINGS=40  # We might sometimes be testing qemu emulation, so we
              # want to give this some time ...
until ping -c 1 $IP &>/dev/null; do
    PINGS=$(($PINGS + 1));
    if test $PINGS -gt $MAX_PINGS; then
        echo "Unable to ping machine!";
        exit 1;
    fi
done;

ATTEMPTS=1
MAX_ATTEMPTS=40  # See above for note about qemu
until ssh -oStrictHostKeyChecking=no -i \
          $HOME/.ssh/id_microstack cirros@$IP -- \
          ping -c 1 91.189.94.250; do
    ATTEMPTS=$(($ATTEMPTS + 1));
    if test $ATTEMPTS -gt $MAX_ATTEMPTS; then
        echo "Unable to access Internet from machine!";
        exit 1;
    fi
    sleep 5
done;

# Cleanup
unset IP
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
echo "++   Completed tests. Uninstalling microstack   ++"
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
sudo snap remove microstack
