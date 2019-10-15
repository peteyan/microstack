import json

from flask import Flask, request

from cluster.shell import check, check_output, write_tunnel_config


app = Flask(__name__)


class Unauthorized(Exception):
    pass


def join_info(password, ip_address):
    our_password = check_output('snapctl', 'get', 'config.cluster.password')

    if password.strip() != our_password.strip():
        raise Unauthorized()

    # Load config
    # TODO: be selective about what we return. For now, we just get everything.
    config = json.loads(check_output('snapctl', 'get', 'config'))

    # Write out tunnel config and restart neutron openvswitch agent.
    write_tunnel_config(config['network']['control-ip'])
    check('snapctl', 'restart', 'microstack.neutron-openvswitch-agent')

    info = {'config': config}
    return info


@app.route('/')
def home():
    status = {
        'status': 'running',
        'info': 'Microstack clustering daemon.'

    }
    return json.dumps(status)


@app.route('/join', methods=['POST'])
def join():
    req = request.json  # TODO: better error messages on failed parse.

    password = req.get('password')
    ip_address = req.get('ip_address')
    if not password:
        return 'No password specified', 500

    try:
        return json.dumps(join_info(password, ip_address))
    except Unauthorized:
        return (json.dumps({'error': 'Incorrect password.'}), 500)
