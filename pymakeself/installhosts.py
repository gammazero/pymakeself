"""
Install an account into all the hosts specified in installhosts.conf.

"""
from __future__ import print_function

import os
import sys
import subprocess

if sys.hexversion < 0x03000000:
    input = raw_input


def _confirm(prompt, default=None):
    if default is not None:
        prompt = '%s (y/n) [%s]: ' % (prompt, 'y' if default else 'n')
    else:
        prompt = '%s (y/n): ' % (prompt,)

    confirmed = None
    while confirmed is None:
        yn = input(prompt).lower()
        if yn in ('y', 'yes'):
            confirmed = True
        elif yn in ('n', 'no'):
            confirmed = False
        else:
            confirmed = default

    return confirmed


def install_on_hosts(script_path, hosts, conf_path):
    if not os.path.isfile(script_path):
        print('install script not found:', script_path, file=sys.stderr)
        return False

    if conf_path:
        # Use default config file.
        conf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'installhosts.conf')
    elif not  os.path.isfile(conf_path):
        print('configuration not found:', conf_path, file=sys.stderr)
        return False

    if not hosts:
        hosts = []

    if os.path.isfile(conf_path):
        print('===> reading hosts from', conf_path)
        # Get hosts list.
        with open(conf_path) as conf_file:
            for line in conf_file:
                if line and line[0] != '#':
                    line = line.strip()
                    if line:
                        hosts.append(line)

    # If not hosts defined, then error.
    if not hosts:
        print('No hosts specified in', conf_path, file=sys.stderr)
        return False

    fails = []
    script_name = os.path.basename(script_path)
    dst_path = '/tmp/' + script_name
    cmd = 'python %s; rm -f %s' % (dst_path, dst_path)
    for host in hosts:
        if _confirm('Run %s on %s' % (script_name, host,), True):
            print('===> installing on', host)
            try:
                subprocess.check_call((
                    'scp', script_path, 'root@%s:/tmp/' % (host,)))
                subprocess.check_call(('ssh', '-t', '-l', 'root', host, cmd))
            except subprocess.CalledProcessError:
                fails.append(host)
        else:
            print('===> skipped', host)

    if fails:
        print('Failed to install on:', ', '.join(fails), file=sys.stderr)
        return False

    return True


def _usage(prg):
    print('Usage: python', prg, '[options] package_script')
    print('\nOptions:')
    print('  --config, -c : Config file path.')
    print('  --help, -h   : Print out this help message.')
    print('  --install    : Install on the specified host.  Multiple OK.')
    print()


def main():
    args = list(sys.argv)
    prg = args.pop(0)
    missing_msg = 'missing argument following'
    install = []
    package_script = None
    conf_file = None
    while args:
        arg = args.pop(0)
        if arg in ('-c', '--config'):
            if not args:
                raise RuntimeError(missing_msg, arg)
            conf_file = args.pop(0)
        elif arg == '--install':
            if not args:
                raise RuntimeError(missing_msg, arg)
            install.append(args.pop(0))
        elif arg in ('--help', '-h', '-?'):
            _usage(prg)
            return 0
        elif arg[0] == '-':
            print('unrecognized argument:', arg, file=sys.stderr)
            print('see:', prg, '--help', file=sys.stderr)
            return 1
        else:
            package_script = arg

    if not package_script:
        print('missing package script', file=sys.stderr)
        print('see:', prg, '--help', file=sys.stderr)
        return 1

    if not install_on_hosts(package_script, install, conf_file):
        return 1


if __name__ == '__main__':
    sys.exit(main())
