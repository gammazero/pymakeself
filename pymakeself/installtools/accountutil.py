"""
Create new account and install files.

There are three ways to use this module:
1) Import this module and use the AccoutnUtil class to create accounts.
2) Import this module and call its install() function to crate an accout, edit
   the sudoers file, and install files into the account home.
3) Run this file as a script, passing it arguments on the command line.  When
   called as a script, use the '--help' argument for help on available options.

When the account is created, with the parameters specified to the install(), or
from command line arguments, a new accout is created.  If an install_files
directory is specified, then the files in this directory are copied into the
account home directory.  If a .ssh directory is included, then the permissions
on that directory and any files in it are set so only the account has access.

If the account is specified as an admin account, then an entry is added to the
sudoers file to allow the account to execute all commands as superuser.  On
FreeBSD systems, admin accounts are also added to the wheel group.

"""
import os
import sys
import stat
import platform
import subprocess
from pwd import getpwnam
from distutils.dir_util import copy_tree


class AccountUtil(object):

    def __init__(self, login, check_root):
        """Initial instance of AccountUtil.

        Arguments:
        login      -- Login name for account.
        check_root -- True to check that this script is being run as root.

        """
        if check_root and os.getuid() != 0:
            raise RuntimeError('install must be run as root')

        self._user_info = None
        self._login = login

    def get_user_info(self):
        """Return user account infomation.

        Return:
        tuple of (user_id, group_id, home_directory)

        """
        if not self._user_info:
            try:
                uid, gid, cmt, home_dir = getpwnam(self._login)[2:6]
            except KeyError:
                raise KeyError('account not found: ' + self._login)

            self._user_info = (uid, gid, home_dir)
        return self._user_info

    def create_user_account(self, comment, passwd, home_dir, group, admin):
        """Create account and home directory.

        Supported platforms are FreeBSD and Linux.

        Arguments:
        login    -- Login name for account.
        comment  -- Comment (full name) for account.
        passwd   -- Password.  None disables password access'
        home_dir -- Home directory for account.  None to use default.
        group    -- Primary group for account.
        admin    -- True to grant admin rights in sudoers file, and wheel group
                    if applicable.

        Return
        tuple of (user_id, group_id, home_directory)

        """
        login = self._login
        try:
            uid, gid = getpwnam(login)[2:4]
            raise RuntimeError('account "%s" already exists' % login)
        except KeyError:
            pass

        pw_action = 'setting' if passwd else 'disabling'
        print('===> creating', login, 'account and', pw_action, 'password')

        if platform.system().startswith('Linux'):
            cmd = ['/usr/sbin/useradd', '-s', '/bin/bash', '-m']
            if comment:
                cmd.append('-c')
                cmd.append(comment)
            if home_dir:
                cmd.append('-d')
                cmd.append(home_dir)
            if group:
                cmd.append('-g')
                cmd.append(group)
            cmd.append(login)
            subprocess.call(cmd)
            if passwd:
                # Set account password
                p = subprocess.Popen(('chpasswd',), stdin=subprocess.PIPE)
                p.stdin.write('%s:%s\n' % (login, passwd))
                p.stdin.close()
                p.wait()
        elif platform.system().startswith('FreeBSD'):
            cmd = ['/usr/sbin/pw', 'useradd', '-n', login,
                   '-s', '/usr/local/bin/bash', '-k', '/usr/share/skel', '-m',
                   '-M', '750']
            if comment:
                cmd.append('-c')
                cmd.append(comment)
            if home_dir:
                cmd.append('-d')
                cmd.append(home_dir)
            if group:
                cmd.append('-g')
                cmd.append(group)
            if admin:
                cmd.append('-G')
                cmd.append('wheel')
            if passwd:
                cmd.extend(('-w', 'yes', '-h', '0'))
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                p.stdin.write(passwd + '\n')
                p.stdin.close()
                p.wait()
            else:
                cmd.extend(('-w', 'no', '-h', '-'))
                subprocess.call(cmd)
        else:
            raise RuntimeError('Platform not supported.  Manually add user.')

        return self.get_user_info()

    def edit_sudoers(self, no_passwd=False, no_tty=False):
        """Add entry to allow user to run all commands using sudo.

        Arguments:
        login     -- Login name of account.
        no_passwd -- True if user can execute sudo without providing a
                     password.
                     False (default) if user must provide password to sudo.
        no_tty    -- True if user can execute sudo without a tty.  False
                     (default) if user must have a tty to execute sudo.

        Return:
        True if sudoers file modified, False if not modified.

        """
        login = self._login
        comment = '# %s can execute commands with su access.\n' % (login,)
        if no_passwd:
            # User can execute sudo without providing a password.
            content = '%s ALL=(ALL) NOPASSWD: ALL\n' % (login,)
        else:
            # User must provide a password to sudo.
            content = '%s ALL=(ALL) ALL\n' % (login,)

        if no_tty:
            # User can execute sudo without being logged into tty.
            content = 'Defaults:%s !requiretty\n%s' % (login, content)

        if platform.system().startswith('Linux'):
            sudoers_path = '/etc/sudoers'
        elif platform.system().startswith('FreeBSD'):
            sudoers_path = '/usr/local/etc/sudoers'
        else:
            print('*** unknown sudoers location ***', file=sys.stderr)
            print('Manually add the following to sudoers file:',
                  file=sys.stderr)
            print(comment, content, file=sys.stderr)
            return False

        if not os.path.isfile(sudoers_path):
            print('===> no sudoers file to edit.')
            return False

        print('===> editing sudoers')

        edit_sudoers = True
        with open(sudoers_path, 'r') as sudoers_file:
            for line in sudoers_file:
                if line.startswith(comment):
                    edit_sudoers = False
                    break

        if edit_sudoers:
            # Set perms to read-write user and read group (0640).
            os.chmod(sudoers_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
            # Append the qmanager config to sudoers file.
            with open(sudoers_path, 'a') as sudoers_file:
                sudoers_file.write(comment)
                sudoers_file.write(content)
            # Set perms to read group and other (0440).
            os.chmod(sudoers_path, stat.S_IRUSR | stat.S_IRGRP)

        return True

    def install_files(self, src_dir):
        """Install files and set ownership.

        If there is a .ssh directory, then set appropriate permissions for it
        and the files it contains.

        """
        uid, gid, home_dir = self.get_user_info()
        print('===> installing files into', home_dir)
        copy_tree(src_dir, home_dir)

        self.set_file_ownership(home_dir, uid, gid)

        dot_ssh_path = os.path.join(home_dir, '.ssh')
        if not os.path.exists(dot_ssh_path):
            # Create the user's .ssh directory.
            os.mkdir(dot_ssh_path, 0o700)
            os.chown(dot_ssh_path, uid, gid)
        else:
            os.chmod(dot_ssh_path, stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)
            # Set file perms to read-write user (0600) for files in .ssh/
            self.set_file_permissions(dot_ssh_path, stat.S_IRUSR|stat.S_IWUSR)

    def set_file_ownership(self, root_dir, uid=None, gid=None):
        """Recursively set ownership on files and directories.

        Arguments:
        root_dir -- Top-level directory to start in.
        uid      -- Numeric user id.  Use account uid if not given.
        gid      -- Numeric group id.  Use account gid if not given.

        """
        if not (uid and gid):
            acct_uid, acct_gid, home_dir = self.get_user_info()
            if not uid:
                uid = acct_uid
            if not gid:
                gid = acct_gid

        for dirpath, dirnames, filenames in os.walk(root_dir):
            try:
                os.chown(dirpath, uid, gid)
            except:
                pass

            for fname in filenames:
                try:
                    os.chown(os.path.join(dirpath, fname), uid, gid)
                except:
                    pass

    def set_file_permissions(self, directory, mode):
        """Set file permissions in the specified directory.

        This method is not recursive.  It only sets permissions on files and
        not on directories.

        Arguments:
        directory -- Directory to set file permissions in.
        mode      -- Permission to set on files.

        """
        for dirent in os.listdir(directory):
            file_path = os.path.join(directory, dirent)
            if os.path.isfile(file_path):
                os.chmod(file_path, mode)


    def set_file_dir_permissions(root_dir, file_mode, dir_mode):
        """Recursively set file and directory permissions.

        Arguments:
        root_dir  -- Top-level directory to start in.
        file_mode -- Permission to set on files.  None to ignore files.
        dir_mode  -- Permission to set on directories.  None to ignore dirs.

        """
        for dirpath, dirnames, filenames in os.walk(root_dir):
            if dir_mode is not None:
                os.chmod(dirpath, dir_mode)
            if file_mode is not None:
                for fname in filenames:
                    os.chmod(os.path.join(dirpath, fname), file_mode)


def install(login, comment, files_dir=None, passwd=None, home_dir=None,
            group=None, admin=False):
    """Create account, install files, and grant admin rights as specified.

    Arguments:
    login     -- Login name for account.
    comment   -- Comment (full name) for account.
    files_dir -- Directory containing files to install into account home.
    passwd    -- Password.  None disables password access'
    home_dir  -- Home directory for account.  None to use default.
    group     -- Primary group for account.
    admin     -- True to grant admin rights in sudoers file, and wheel group if
                 applicable.

    Return:
    Completion message string.

    """
    acctutil = AccountUtil(login, True)
    try:
        acctutil.create_user_account(comment, passwd, home_dir, group, admin)
        if admin:
            acctutil.edit_sudoers(False, False)
        if files_dir:
            acctutil.install_files(files_dir)
    except Exception as e:
        raise RuntimeError('install failed: ' + str(e))

    return '===> %s account installation complete' % (login,)


def main():
    import argparse
    ap = argparse.ArgumentParser(description='User account creation utility.')
    ap.add_argument('-n', action='store_false', dest='admin')
    ap.add_argument('-c', dest='comment', help='Comment (full name)')
    ap.add_argument('-d', dest='home_dir',
                    help='Home directory.  Use default if not given.')
    ap.add_argument('-g', dest='group',
                    help='Primary group.  Use default if not given.')
    ap.add_argument('-p', dest='passwd',
                    help='Password.  Default is no password access.')
    ap.add_argument('-i', dest='install_src', metavar='directory',
                    help='Path to directory containing files and directories '
                    'to install.')
    ap.add_argument('-s', action='store_true', dest='script',
                    help='Create a script to run accountutil.')
    ap.add_argument('login', help='Account login wsername.')
    args = ap.parse_args()

    print('Account info:')
    print('  login:', args.login)
    print('  comment:', args.comment if args.comment else '""')
    print('  password:', '*' * 8 if args.passwd else '<disabled>')
    print('  home:', args.home_dir if args.home_dir else '<default>')
    print('  group:', args.group if args.group else '<default>')
    print('  admin:', args.admin)
    print()

    if args.script:
        with open('create_script.py', 'w') as cscript:
            sys.argv.remove('-s')
            print('python', ' '.join(sys.argv), file=cscript)
            return 0

    msg = install(args.login, args.comment, args.install_src, args.passwd,
                  args.home_dir, args.group, args.admin)
    print(msg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
