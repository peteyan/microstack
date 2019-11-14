import logging
import json
import unittest
import os
import subprocess
import time
import xvfbwrapper
from typing import List

import petname
from selenium import webdriver
from selenium.webdriver.common.by import By


# Setup logging
log = logging.getLogger("microstack_test")
log.setLevel(logging.DEBUG)
stream = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream.setFormatter(formatter)
log.addHandler(stream)


def check(*args: List[str]) -> int:
    """Execute a shell command, raising an error on failed excution.

    :param args: strings to be composed into the bash call.

    """
    return subprocess.check_call(args)


def check_output(*args: List[str]) -> str:
    """Execute a shell command, returning the output of the command.

    :param args: strings to be composed into the bash call.

    Include our env; pass in any extra keyword args.
    """
    return subprocess.check_output(args, universal_newlines=True).strip()


def call(*args: List[str]) -> bool:
    """Execute a shell command.

    Return True if the call executed successfully (returned 0), or
    False if it returned with an error code (return > 0)

    :param args: strings to be composed into the bash call.
    """
    return not subprocess.call(args)


def gui_wrapper(func):
    """Start up selenium drivers, run a test, then tear them down."""

    def wrapper(cls, *args, **kwargs):

        # Setup Selenium Driver
        cls.display = xvfbwrapper.Xvfb(width=1280, height=720)
        cls.display.start()
        cls.driver = webdriver.PhantomJS()

        # Run function
        try:
            return func(cls, *args, **kwargs)

        finally:
            # Tear down driver
            cls.driver.quit()
            cls.display.stop()

    return wrapper


class Host():
    """A host with MicroStack installed."""

    def __init__(self):
        self.prefix = []
        self.dump_dir = '/tmp'
        self.machine = ''
        self.distro = 'bionic'
        self.snap = 'microstack_stein_amd64.snap'
        self.horizon_ip = '10.20.20.1'
        self.host_type = 'localhost'

        if os.environ.get('MULTIPASS'):
            self.host_type = 'multipass'
            print("Booting a Multipass VM ...")
            self.multipass()

    def install(self, snap=None, channel='dangerous'):
        if snap is None:
            snap = self.snap
        print("Installing {}".format(snap))

        check(*self.prefix, 'sudo', 'snap', 'install', '--classic',
              '--{}'.format(channel), snap)

    def init(self, flag='auto'):
        print("Initializing the snap with --{}".format(flag))
        check(*self.prefix, 'sudo', 'microstack.init', '--{}'.format(flag))

    def multipass(self):
        self.machine = petname.generate()
        self.prefix = ['multipass', 'exec', self.machine, '--']
        distro = os.environ.get('distro') or self.distro

        check('sudo', 'snap', 'install', '--classic', '--edge', 'multipass')

        check('multipass', 'launch', '--cpus', '2', '--mem', '8G', distro,
              '--name', self.machine)
        check('multipass', 'copy-files', self.snap, '{}:'.format(self.machine))

        # Figure out machine's ip
        info = check_output('multipass', 'info', self.machine, '--format',
                            'json')
        info = json.loads(info)
        self.horizon_ip = info['info'][self.machine]['ipv4'][0]

    def dump_logs(self):
        # TODO: make unique log name
        if check_output('whoami') == 'zuul':
            self.dump_dir = "/home/zuul/zuul-output/logs"

        check(*self.prefix,
              'sudo', 'tar', 'cvzf',
              '{}/dump.tar.gz'.format(self.dump_dir),
              '/var/snap/microstack/common/log',
              '/var/snap/microstack/common/etc',
              '/var/log/syslog')
        if 'multipass' in self.prefix:
            check('multipass', 'copy-files',
                  '{}:/tmp/dump.tar.gz'.format(self.machine), '.')
        print('Saved dump.tar.gz to local working dir.')

    def teardown(self):
        if 'multipass' in self.prefix:
            check('sudo', 'multipass', 'delete', self.machine)
            check('sudo', 'multipass', 'purge')
        else:
            check('sudo', 'snap', 'remove', '--purge', 'microstack')


class Framework(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.HOSTS = []

    def get_host(self):
        if self.HOSTS:
            return self.HOSTS[0]
        host = Host()
        self.HOSTS.append(host)
        return host

    def add_host(self):
        host = Host()
        self.HOSTS.append(host)
        return host

    def verify_instance_networking(self, host, instance_name):
        """Verify that we have networking on an instance

        We should be able to ping the instance.

        And we should be able to reach the Internet.

        """
        prefix = host.prefix

        # Ping the instance
        print("Testing ping ...")
        ip = None
        servers = check_output(*prefix, '/snap/bin/microstack.openstack',
                               'server', 'list', '--format', 'json')
        servers = json.loads(servers)
        for server in servers:
            if server['Name'] == instance_name:
                ip = server['Networks'].split(",")[1].strip()
                break

        self.assertTrue(ip)

        pings = 1
        max_pings = 600  # ~10 minutes!
        while not call(*prefix, 'ping', '-c1', '-w1', ip):
            pings += 1
            if pings > max_pings:
                self.assertFalse(True, msg='Max pings reached!')

        print("Testing instances' ability to connect to the Internet")
        # Test Internet connectivity
        attempts = 1
        max_attempts = 300  # ~10 minutes!
        username = check_output(*prefix, 'whoami')

        while not call(
                *prefix,
                'ssh',
                '-oStrictHostKeyChecking=no',
                '-i', '/home/{}/.ssh/id_microstack'.format(username),
                'cirros@{}'.format(ip),
                '--', 'ping', '-c1', '91.189.94.250'):
            attempts += 1
            if attempts > max_attempts:
                self.assertFalse(
                    True,
                    msg='Unable to access the Internet!')
            time.sleep(1)

    @gui_wrapper
    def verify_gui(self, host):
        """Verify that Horizon Dashboard works

        We should be able to reach the dashboard.

        We should be able to login.

        """
        # Test
        print('Verifying GUI for (IP: {})'.format(host.horizon_ip))
        # Verify that our GUI is working properly
        self.driver.get("http://{}/".format(host.horizon_ip))
        # Login to horizon!
        self.driver.find_element(By.ID, "id_username").click()
        self.driver.find_element(By.ID, "id_username").send_keys("admin")
        self.driver.find_element(By.ID, "id_password").send_keys("keystone")
        self.driver.find_element(By.CSS_SELECTOR, "#loginBtn > span").click()
        # Verify that we can click something on the dashboard -- e.g.,
        # we're still not sitting at the login screen.
        self.driver.find_element(By.LINK_TEXT, "Images").click()

    def setUp(self):
        self.passed = False  # HACK: trigger (or skip) cleanup.

    def tearDown(self):
        """Clean hosts up, possibly leaving debug information behind."""

        print("Tests complete. Cleaning up.")
        while self.HOSTS:
            host = self.HOSTS.pop()
            if not self.passed:
                print("Dumping logs for {}".format(host.machine))
                host.dump_logs()
            host.teardown()
