#!/bin/bash
set -e

echo "Initializing Microstack."

##############################################################################
#
# Config
#
# Setup env and templates.
#
##############################################################################
echo "Loading config and writing out templates ..."

ospassword=$(snapctl get ospassword)
extgateway=$(snapctl get extgateway)
extcidr=$(snapctl get extcidr)
dns=$(snapctl get dns)

# Check Config
if [ -z "$ospassword" -o -z "$extgateway" -o -z "$dns" -o -z "$extcidr"]; then
    echo "Missing required config value."
    exit 1
fi

# Write out templates and read off of our microstack.rc template
# TODO: any password change hooks would go here, updating the password
# in the db before writing it to the templates and restarting
# services.
snap-openstack setup # Write out templates

# Load openstack .rc into this script's environment. Outside of the
# snap shell, this is handled by a wrapper.
source $SNAP_COMMON/etc/microstack.rc


##############################################################################
#
# System Optimization
#
# Perform some tasks that change the host system in ways to better
# support microstack.
#
##############################################################################


# Open up networking so that instances can route to the Internet (see
# bin/setup-br-ex for more networking setup, executed on microstack
# services start.)
echo "Setting up ipv4 forwarding."
sudo sysctl net.ipv4.ip_forward=1

# TODO: add vm swappiness and increased file handle limits here.
# TODO: make vm swappiness and file handle changes optional.


##############################################################################
#
# RabbitMQ Setup
#
# Configure database and wait for services to start.
#
##############################################################################
echo "Configuring RabbitMQ"

echo "Waiting for rabbitmq to start"
while ! nc -z $extgateway 5672; do sleep 0.1; done;
while :;
do
    grep "Starting broker..." ${SNAP_COMMON}/log/rabbitmq/startup_log && \
        grep "completed" ${SNAP_COMMON}/log/rabbitmq/startup_log && \
        break
    sleep 1;
done
echo "Rabbitmq started."

# Config!
HOME=$SNAP_COMMON/lib/rabbitmq rabbitmqctl add_user openstack rabbitmq || :
HOME=$SNAP_COMMON/lib/rabbitmq rabbitmqctl set_permissions openstack ".*" ".*" ".*"


##############################################################################
#
# Database setup
#
# Create databases and initialize keystone.
#
##############################################################################

# Wait for MySQL to startup
echo "Waiting for MySQL server to start ..."
while ! nc -z $extgateway 3306; do sleep 0.1; done;
while :;
do
    grep "mysqld: ready for connections." \
         ${SNAP_COMMON}/log/mysql/error.log && break;
    sleep 1;
done
echo "Mysql server started."

for db in neutron nova nova_api nova_cell0 cinder glance keystone; do
    echo "CREATE DATABASE IF NOT EXISTS ${db}; GRANT ALL PRIVILEGES ON ${db}.* TO '${db}'@'$extgateway' IDENTIFIED BY '${db}';" \
        | mysql-start-client -u root
done

# Configure Keystone Fernet Keys
echo "Configuring Keystone..."
snap-openstack launch keystone-manage fernet_setup \
               --keystone-user root \
               --keystone-group root
snap-openstack launch keystone-manage db_sync

systemctl restart snap.microstack.keystone-*

openstack user show admin || {
    snap-openstack launch keystone-manage bootstrap \
        --bootstrap-password $ospassword \
        --bootstrap-admin-url http://$extgateway:5000/v3/ \
        --bootstrap-internal-url http://$extgateway:5000/v3/ \
        --bootstrap-public-url http://$extgateway:5000/v3/ \
        --bootstrap-region-id microstack
}

openstack project show service || {
    openstack project create --domain default --description "Service Project" service
}
echo "Keystone configured."

##############################################################################
#
# Nova Setup
#
# Configure database and wait for services to start.
#
##############################################################################
echo "Configuring Nova..."

openstack user show nova || {
    openstack user create --domain default --password nova nova
    openstack role add --project service --user nova admin
}

openstack user show placement || {
    openstack user create --domain default --password placement placement
    openstack role add --project service --user placement admin
}

openstack service show compute || {
    openstack service create --name nova \
      --description "OpenStack Compute" compute

    for endpoint in public internal admin; do
        openstack endpoint create --region microstack \
          compute $endpoint http://$extgateway:8774/v2.1 || :
    done
}

openstack service show placement || {
    openstack service create --name placement \
      --description "Placement API" placement

    for endpoint in public internal admin; do
        openstack endpoint create --region microstack \
          placement $endpoint http://$extgateway:8778 || :
    done
}

# Grant nova user access to cell0
echo "GRANT ALL PRIVILEGES ON nova_cell0.* TO 'nova'@'$extgateway' IDENTIFIED BY 'nova';" \
    | mysql-start-client -u root

snap-openstack launch nova-manage api_db sync
snap-openstack launch nova-manage cell_v2 list_cells | grep cell0 || {
    snap-openstack launch nova-manage cell_v2 map_cell0
}
snap-openstack launch nova-manage cell_v2 list_cells | grep cell1 || {
    snap-openstack launch nova-manage cell_v2 create_cell --name=cell1 --verbose
}
snap-openstack launch nova-manage db sync

systemctl restart snap.microstack.nova-*

while ! nc -z $extgateway 8774; do sleep 0.1; done;

sleep 5

openstack flavor show m1.tiny || {
    openstack flavor create --id 1 --ram 512 --disk 1 --vcpus 1 m1.tiny
}
openstack flavor show m1.small || {
    openstack flavor create --id 2 --ram 2048 --disk 20 --vcpus 1 m1.small
}
openstack flavor show m1.medium || {
    openstack flavor create --id 3 --ram 4096 --disk 20 --vcpus 2 m1.medium
}
openstack flavor show m1.large || {
    openstack flavor create --id 4 --ram 8192 --disk 20 --vcpus 4 m1.large
}
openstack flavor show m1.xlarge || {
    openstack flavor create --id 5 --ram 16384 --disk 20 --vcpus 8 m1.xlarge
}

##############################################################################
#
# Neutron Setup
#
# Configure database and wait for services to start.
#
##############################################################################
echo "Configuring Neutron"

openstack user show neutron || {
    openstack user create --domain default --password neutron neutron
    openstack role add --project service --user neutron admin
}

openstack service show network || {
    openstack service create --name neutron \
      --description "OpenStack Network" network

    for endpoint in public internal admin; do
        openstack endpoint create --region microstack \
          network $endpoint http://$extgateway:9696 || :
    done
}

snap-openstack launch neutron-db-manage upgrade head

systemctl restart snap.microstack.neutron-*

while ! nc -z $extgateway 9696; do sleep 0.1; done;

sleep 5

openstack network show test || {
    openstack network create test
}

openstack subnet show test-subnet || {
    openstack subnet create --network test --subnet-range 192.168.222.0/24 test-subnet
}

openstack network show external || {
    openstack network create --external \
        --provider-physical-network=physnet1 \
        --provider-network-type=flat external
}

openstack subnet show external-subnet || {
    openstack subnet create --network external --subnet-range 10.20.20.0/24 \
        --no-dhcp external-subnet
}

openstack router show test-router || {
    openstack router create test-router
    openstack router add subnet test-router test-subnet
    openstack router set --external-gateway external test-router
}

##############################################################################
#
# Glance Setup
#
# Configure database and wait for services to start.
#
##############################################################################
echo "Configuring Glance"

openstack user show glance || {
    openstack user create --domain default --password glance glance
    openstack role add --project service --user glance admin
}

openstack service show image || {
    openstack service create --name glance --description "OpenStack Image" image
    for endpoint in internal admin public; do
        openstack endpoint create --region microstack \
            image $endpoint http://$extgateway:9292 || :
    done
}

snap-openstack launch glance-manage db_sync

systemctl restart snap.microstack.glance*

while ! nc -z $extgateway 9292; do sleep 0.1; done;

sleep 5

# Setup the cirros image, which is used by the launch app
echo "Grabbing cirros image."
openstack image show cirros || {
    [ -f $SNAP_COMMON/images/cirros-0.4.0-x86_64-disk.img ] || {
        mkdir -p $SNAP_COMMON/images
        wget \
          http://download.cirros-cloud.net/0.4.0/cirros-0.4.0-x86_64-disk.img \
          -O ${SNAP_COMMON}/images/cirros-0.4.0-x86_64-disk.img
    }
    openstack image create \
        --file ${SNAP_COMMON}/images/cirros-0.4.0-x86_64-disk.img \
        --public --container-format=bare --disk-format=qcow2 cirros
}

##############################################################################
#
# Post-setup tasks.
#
# Clean up hanging threads and wait for services to restart.
#
##############################################################################

# Restart libvirt and virtlogd to get logging
# TODO: figure out why this doesn't Just Work initially
systemctl restart snap.microstack.*virt*

echo "Complete. Marking microstack as initialized!"
snapctl set initialized=true
