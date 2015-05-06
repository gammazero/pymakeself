from __future__ import print_function
import os
import sys
from installtools import accountutil

def install(login, comment, install_src, passwd, home_dir, group, admin):
    print('install files dir:', install_src)
    print('files to install:')
    for f in os.listdir(install_src):
        print(f)

    print('done!!')
    return 'FINISHED RUNNING ' + str(sys.argv)


def main():
    args = list(sys.argv)
    prg = args.pop(0)
    login = comment = passwd = home_dir = group = None
    admin = True
    install_src = None

    missing_msg = 'missing argument following'
    while args:
        arg = args.pop(0)
        if arg == '-n':
            admin = False
        elif arg == '-c':
            if not args:
                raise RuntimeError(missing_msg, arg)
            comment = args.pop(0)
        elif arg == '-d':
            if not args:
                raise RuntimeError(missing_msg, arg)
            home_dir = args.pop(0)
        elif arg == '-g':
            if not args:
                raise RuntimeError(missing_msg, arg)
            group = args.pop(0)
        elif arg == '-p':
            if not args:
                raise RuntimeError(missing_msg, arg)
            passwd = args.pop(0)
        elif arg == '-i':
            if not args:
                raise RuntimeError(missing_msg, arg)
            install_src = os.path.abspath(os.path.expanduser(args.pop(0)))
        elif arg in ('-h', '--help'):
            print('Usage: python', prg, '[options] login')
            print('\nOptions:')
            print('  -c comment : Comment (full name)')
            print('  -d dir     : Home directory.  Use default if not given.')
            print('  -g group   : Primary group.  Use default if not given.')
            print('  -n         : Non-admin account.  Default is admin.')
            print('  -p passwd  : Password.  Default is no password access.')
            print()
            print('  -i dir     : Path to directory containing files and '
                  'directories to install.')
            print()
            print('Example:')
            print("python makeinstaller.py -c 'Andrew J. Gillis' -i dot_files "
                  "ajg")
            print()
            return 0
        elif arg[0] != '-':
            login = arg
        else:
            print('unrecognized argument:', arg, file=sys.stderr)
            print('see:', prg, '--help', file=sys.stderr)
            return 1

    if not login:
        print('missing login', file=sys.stderr)
        print('see:', prg, '--help', file=sys.stderr)
        return 1

    print('Account info:')
    print('  login:', login)
    print('  comment:', comment if comment else '""')
    print('  password:', '*' * 8 if passwd else '<disabled>')
    print('  home:', home_dir if home_dir else '<default>')
    print('  group:', group if group else '<default>')
    print('  admin:', admin)
    print()

    msg = install(login, comment, install_src, passwd, home_dir, group, admin)
    print(msg)
    return 0


if __name__ == '__main__':
    main()
