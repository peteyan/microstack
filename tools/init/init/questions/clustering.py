from getpass import getpass

from init.questions.question import Question, InvalidAnswer
from init.shell import check, check_output, fetch_ip_address


class Role(Question):
    _type = 'string'
    config_key = 'config.cluster.role'
    _question = "What is this machines' role? (control/compute)"
    _valid_roles = ('control', 'compute')
    interactive = True

    def _input_func(self, prompt):
        if not self.interactive:
            return

        for _ in range(0, 3):
            role = input("{} > ".format(self._question))
            if role in self._valid_roles:
                return role

            print('Role must be either "control" or "compute"')

        raise InvalidAnswer('Too many failed attempts.')


class Password(Question):
    _type = 'string'  # TODO: type password support
    config_key = 'config.cluster.password'
    _question = 'Please enter a cluster password > '
    interactive = True

    def _input_func(self, prompt):
        if not self.interactive:
            return

        # Get rid of 'default=' string the parent class has added to prompt.
        prompt = self._question

        for _ in range(0, 3):
            password0 = getpass(prompt)
            password1 = getpass('Please re-enter password > ')
            if password0 == password1:
                return password0

            print("Passwords don't match!")

        raise InvalidAnswer('Too many failed attempts.')


class ControlIp(Question):
    _type = 'string'
    config_key = 'config.network.control-ip'
    _question = 'Please enter the ip address of the control node'
    interactive = True

    def _load(self):
        if check_output(
                'snapctl', 'get', 'config.cluster.role') == 'control':
            return fetch_ip_address() or super()._load()

        return super()._load()


class ComputeIp(Question):
    _type = 'string'
    config_key = 'config.network.compute-ip'
    _question = 'Please enter the ip address of this node'
    interactive = True

    def _load(self):
        if check_output(
                'snapctl', 'get', 'config.cluster.role') == 'compute':
            return fetch_ip_address() or super().load()

        return super()._load()

    def ask(self):
        # If we are a control node, skip this question.
        role = check_output('snapctl', 'get', Role.config_key)
        if role == 'control':
            ip = check_output('snapctl', 'get', ControlIp.config_key)
            check('snapctl', 'set', '{}={}'.format(self.config_key, ip))
            return

        return super().ask()
