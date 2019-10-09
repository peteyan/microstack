import logging
import json
import unittest
import os
import subprocess
from typing import List

import petname


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


class Framework(unittest.TestCase):

    PREFIX = []
    DUMP_DIR = '/tmp'
    MACHINE = ''
    DISTRO = 'bionic'
    SNAP = 'microstack_stein_amd64.snap'
    HORIZON_IP = '10.20.20.1'
    INIT_FLAG = 'auto'

    def install_snap(self, channel='dangerous', snap=None):
        if snap is None:
            snap = self.SNAP

        check(*self.PREFIX, 'sudo', 'snap', 'install', '--classic',
              '--{}'.format(channel), snap)

    def init_snap(self, flag='auto'):
        check(*self.PREFIX, 'sudo', 'microstack.init', '--{}'.format(flag))

    def multipass(self):

        self.MACHINE = petname.generate()
        self.PREFIX = ['multipass', 'exec', self.MACHINE, '--']

        check('sudo', 'snap', 'install', '--classic', '--edge', 'multipass')

        check('multipass', 'launch', '--cpus', '2', '--mem', '8G', self.DISTRO,
              '--name', self.MACHINE)
        check('multipass', 'copy-files', self.SNAP, '{}:'.format(self.MACHINE))

        # Figure out machine's ip
        info = check_output('multipass', 'info', self.MACHINE, '--format',
                            'json')
        info = json.loads(info)
        self.HORIZON_IP = info['info'][self.MACHINE]['ipv4'][0]

    def dump_logs(self):
        if check_output('whoami') == 'zuul':
            self.DUMP_DIR = "/home/zuul/zuul-output/logs"

        check(*self.PREFIX,
              'sudo', 'tar', 'cvzf',
              '{}/dump.tar.gz'.format(self.DUMP_DIR),
              '/var/snap/microstack/common/log',
              '/var/snap/microstack/common/etc',
              '/var/log/syslog')
        if 'multipass' in self.PREFIX:
            check('multipass', 'copy-files',
                  '{}:/tmp/dump.tar.gz'.format(self.MACHINE), '.')
        print('Saved dump.tar.gz to local working dir.')

    def setUp(self):
        self.passed = False  # HACK: trigger (or skip) cleanup.
        if os.environ.get('MULTIPASS'):
            print("Booting a Multipass VM ...")
            self.multipass()
        print("Installing {}".format(self.SNAP))
        self.install_snap()
        print("Initializing the snap with --{}".format(self.INIT_FLAG))
        self.init_snap(self.INIT_FLAG)

    def tearDown(self):
        """Either dump logs in the case of failure, or clean up."""

        if not self.passed:
            # Skip teardown in the case of failures, so that we can
            # inspect them.
            # TODO: I'd like to use the errors and failures list in
            # the test result, but I was having trouble getting to it
            # from this routine. Need to do more digging and possibly
            # elimiate the self.passed hack.
            print("Tests failed. Dumping logs and exiting.")
            return self.dump_logs()

        print("Tests complete. Tearing down.")
        if 'multipass' in self.PREFIX:
            check('sudo', 'multipass', 'delete', self.MACHINE)
            check('sudo', 'multipass', 'purge')
        else:
            check('sudo', 'snap', 'remove', '--purge', 'microstack')
