"""
Install an account into all the hosts specified in installhosts.conf.

"""
import os
import sys
import subprocess

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

    if not conf_path:
        # Use default config file.
        conf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'installhosts.conf')
    elif not os.path.isfile(conf_path):
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
                    'scp', script_path, '%s:/tmp/' % (host,)))
                subprocess.check_call(('ssh', '-t', host, cmd))
            except subprocess.CalledProcessError:
                fails.append(host)
        else:
            print('===> skipped', host)

    if fails:
        print('Failed to install on:', ', '.join(fails), file=sys.stderr)
        return False

    return True


def main():
    import argparse
    ap = argparse.ArgumentParser(description='User account creation utility.')
    ap.add_argument('--config', '-c', dest='conf_file',
                    help='Config file path.')
    ap.add_argument('--install', action='append',
                    help='Install on the specified host, (i.e. root@devbox1). '
                    'Multiple OK.')
    ap.add_argument('script', dest='package_script',
                    help='Package install script to run.')
    args = ap.parse_args()

    if not install_on_hosts(args.package_script, args.install, args.conf_file):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
