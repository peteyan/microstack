import os
import pymysql
import subprocess


def sql(cmd) -> None:
    """Execute some SQL!

    Really simply wrapper around a pymysql connection, suitable for
    passing the limited CREATE and GRANT commands that we need to pass
    here.

    :param cmd: sql to execute.

    # TODO: move this into a shared shell library.

    """
    mysql_conf = '${SNAP_USER_COMMON}/etc/mysql/my.cnf'.format(**os.environ)
    connection = pymysql.connect(host='localhost', user='root',
                                 read_default_file=mysql_conf)

    with connection.cursor() as cursor:
        cursor.execute(cmd)


def check_output(*args):
    """Execute a shell command, returning the output of the command."""
    return subprocess.check_output(args, env=os.environ,
                                   universal_newlines=True).strip()


def check(*args):
    """Execute a shell command, raising an error on failed excution.

    :param args: strings to be composed into the bash call.

    """
    return subprocess.check_call(args, env=os.environ)
