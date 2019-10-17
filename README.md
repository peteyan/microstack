# microstack

[![Snap Status](https://build.snapcraft.io/badge/CanonicalLtd/microstack.svg)](https://build.snapcraft.io/user/CanonicalLtd/microstack)

OpenStack in a snap that you can run locally on a single machine! Excellent for ...

* Development and Testing of Openstack Workloads
* CI
* Edge Clouds (experimental)

`microstack` currently provides Nova, Keystone, Glance, Horizon and Neutron OpenStack services.

If you want to roll up your sleeves and do interesting things with the services and settings, look in the .d directories in the filesystem tree under `/var/snap/microstack/common/etc`. You can add services with your package manager, or take a look at `CONTRIBUTING.md` and make a code based argument for adding a service to the default list. :-)


## Installation

`microstack` is frequently updated to provide the latest stable updates of the most recent OpenStack release.  The quickest was to get started is to install directly from the snap store.  You can install `microstack` using:

```
sudo snap install microstack --classic --beta
```

## Quickstart
To quickly configure networks and launch a vm, run

`sudo microstack.init`

This will configure various Openstack databases. Then run:

`microstack.launch test`.

This will launch an instance for you, and make it available to manage via the command line, or via the Horizon Dashboard.

To access the Dashboard, visit http://10.20.20.1 in a web browser, and login with the following credentials:

```
username: admin
password: keystone
```

To ssh into the instance, use the username "cirros" and the ssh key written to ~/.ssh/id_microstack:

`ssh -i ~/.ssh/id_microstack cirros@<IP>` (Where 'IP' is listed in the output of `microstack.launch`)

To run openstack commands, run `microstack.openstack <some command>`

For more detail and control, read the rest of this README. :-)

## Accessing OpenStack

`microstack` provides a pre-configured OpenStack CLI to access the local OpenStack deployment; its namespaced using the `microstack` prefix:

```
microstack.openstack server list
```

You can setup this command as an alias for `openstack` if you wish (removing the need for the `microstack.` prefix):

```
sudo snap alias microstack.openstack openstack
```

Alternatively you can access the Horizon OpenStack dashboard on `http://127.0.0.1` with the following credentials:

```
username: admin
password: keystone
```

## Creating and accessing an instance

Create an instance in the usual way:

```
microstack.openstack server create --flavor m1.small --nic net-id=test --key-name microstack --image cirros my-microstack-server
```

For convenience, we've used items that the initialisation step provided
(flavor, network, keypair, and image). You are free to manage your own.

To access the instance, you'll need to assign it a floating IP address:

```
ALLOCATED_FIP=`microstack.openstack floating ip create -f value -c floating_ip_address external`
microstack.openstack server add floating ip my-microstack-server $ALLOCATED_FIP
```

Since MicroStack is just like a normal OpenStack cloud you'll need to enable
SSH and ICMP access to the instance (this may have been done by the
initialisation step):

```
SECGROUP_ID=`microstack.openstack security group list --project admin -f value -c ID`
microstack.openstack security group rule create $SECGROUP_ID --proto tcp --remote-ip 0.0.0.0/0 --dst-port 22
microstack.openstack security group rule create $SECGROUP_ID --proto icmp --remote-ip 0.0.0.0/0
```

You should now be able to SSH to the instance:

```
ssh -i ~/.ssh/id_microstack cirros@$ALLOCATED_FIP
```

Happy `microstack`ing!

## Stopping and starting microstack

You may wish to temporarily shutdown microstack when not in use without un-installing it.

`microstack` can be shutdown using:

```
sudo snap disable microstack
```

and re-enabled latest using:

```
sudo snap enable microstack
```

## Raising a Bug

Please report bugs to the microstack project on launchpad: https://bugs.launchpad.net/microstack
