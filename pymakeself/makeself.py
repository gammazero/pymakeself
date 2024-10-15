"""
Create an executable (self-extracting) installer Python script.

The installer contains a copy of the contents of a specified directory, and it
contains the specified install script.  When the installer is run, it extracts
itself and runs the install script.

The installer is created by first creating a directory, package_name, that
contains a subdirectory called 'install_files'.  The 'install_files'
subdirectory contains a copy of the contents of the specified content_dir.  If
a setup_script is specified, then that setup_script is also copied into the
package_name dir, along with the installtools if those are requested.

    somewhere/
        content_dir/ }---------+
                               |
    someplace/                 |
        setupscript.py }-----+ |
                             | | <copy>
    working_tmp_dir/         | |
        package_name/        | |
            setupscript.py <-+ |
            installtools/      |
            install_files/ <---+
                file1
                file2
                ...


The package_name directory is then archived into a tar file:

    working_tmp_dir/
        +--------------------+
        | package_name/      |
        |     setupscript.py |
        |     installtools/  |
        |     install_files/ |}-----+
        |         file1      |      |
        |         file2      |      |
        |         ...        |      | <archive>
        +--------------------+      | [optionally encrypt]
                                    |
        package_name.tar.gz <-------+


Then the tar file is written into the data portion of a Python install script:

    working_tmp_dir/
        +---------------------+
        | package_name.tar.gz |}----+
        +---------------------+     | <embed>
                                    |
    ~/package_name.py <-------------+


This install script can be run on another machine to extract the archive and
run the setup_script script inside it.

"""
from __future__ import print_function
from __future__ import absolute_import
import os
import sys
import shutil
import tarfile
import tempfile
import stat
import base64
try:
    import lzma
except ImportError:
    pass

__version__ = '0.3.5'

_exe_template = \
b"""
from __future__ import print_function
import base64
import tarfile
import shutil
import tempfile
import os
import sys
import argparse
import datetime


def main():
    ap = argparse.ArgumentParser(description='Self-extracting install script')
    ap.add_argument('--check', action='store_true',
                    help='Check the integrity of the archive.')
    ap.add_argument('--list', action='store_true',
                    help='List the files in the archive')
    ap.add_argument('--extract', action='store_true',
                    help='Extract package contents and exit')
    ap.add_argument('args', nargs=argparse.REMAINDER,
                    help='Arguments to pass to setup script')
    args = ap.parse_args()

    tmp_dir = None
    orig_dir = None
    try:
        # Create a temporary working directory
        tmp_dir = tempfile.mkdtemp()

        # Write the tarfile into the temporary directory
        tar_path = os.path.join(tmp_dir, tar_name)
        with open(tar_path, 'wb') as fp:
            if sys.version_info >= (3, 1) :
                fp.write(base64.decodebytes(PKG_DATA))
            else :
                fp.write(base64.decodestring(PKG_DATA))

        if sha256_sum:
            import hashlib
            BLOCKSIZE = 65536
            sha256 = hashlib.sha256()
            with open(tar_path, 'rb') as tar_file:
                buf = tar_file.read(BLOCKSIZE)
                while buf:
                    sha256.update(buf)
                    buf = tar_file.read(BLOCKSIZE)
            if sha256_sum != sha256.hexdigest():
                raise RuntimeError('SHA256 checksum mismatch.  The file may '
                                   'be corrupted or incomplete.')
            print('===> SHA256 is good')
        else:
            print('===> SHA256 not checked')

        if args.check:
            return 0

        if label:
            print(label)

        if encrypted:
            # Write the aes tarfile to disk.
            aes_path = os.path.join(tmp_dir, 'aes.tar.gz')
            with open(aes_path, 'wb') as fp:
                if sys.version_info >= (3, 1) :
                    fp.write(base64.decodebytes(PKG_DATA))
                else :
                    fp.write(base64.decodestring(PKG_DATA))
            # Unpack the aes tarfile then delete it.
            with tarfile.open(aes_path) as t:
                t.extractall(tmp_dir)
            os.unlink(aes_path)

            # import aes module and decrypt pkg tar file
            sys.path.insert(0, tmp_dir)
            from aes import aesutil
            new_tar_name = tar_name.split('.aes', 1)[0]
            new_tar_path = os.path.join(tmp_dir, new_tar_name)
            with open(tar_path, 'rb') as etar:
                with open(new_tar_path, 'wb') as dtar:
                    err = aesutil.decrypt(None, etar, dtar)
                    if err:
                        raise RuntimeError(err)
            os.unlink(tar_path)
            tar_path = new_tar_path

        # List tarfile contents.
        if args.list:
            with tarfile.open(tar_path) as t:
                max_sz = 0
                n = 0
                for ti in t.getmembers():
                    if n < 2:
                        n += 1
                        continue
                    sz = "%d" % ti.size
                    if len(sz) > max_sz:
                        max_sz = len(sz)

                bits = ['-'] * 10
                j = len(bits) - 1
                fmt = '%%s %%%dd %%s %%s' % max_sz
                n = 0
                for ti in t.getmembers():
                    if n < 2:
                        n += 1
                        continue
                    mt = datetime.datetime.fromtimestamp(ti.mtime)
                    mts = mt.strftime("%b %d %H:%M")
                    name = ti.name.split('install_files/', 1)[-1]
                    i = 0
                    while i < len(bits) - 1:
                        bits[j-i] = 'x' if (ti.mode >> i) & 0x01 else '-'
                        i += 1
                        bits[j-i] = 'w' if (ti.mode >> i) & 0x01 else '-'
                        i += 1
                        bits[j-i] = 'r' if (ti.mode >> i) & 0x01 else '-'
                        i += 1

                    if ti.isfile(): bits[0]= '-'
                    elif ti.isdir(): bits[0] = 'd'
                    elif ti.issym(): bits[0] = 'l'
                    elif ti.islnk(): bits[0] = 'h'
                    elif ti.ischr(): bits[0] = 'c'
                    elif ti.isblk(): bits[0] = 'b'
                    elif ti.isfifo(): bits[0] = 'p'
                    else: bits[0] = '-'
                    print(fmt % (''.join(bits), ti.size, mts, name))
            return 0

        # Unpack the tarfile.
        with tarfile.open(tar_path) as t:
            t.extractall(tmp_dir)
        os.unlink(tar_path)

        pkg_path = os.path.join(tmp_dir, pkg_name)
        if args.extract:
            print('Extracted package:', pkg_path)
            tmp_dir = None
            return 0

        if script_name:
            sys.path.insert(0, pkg_path)
            orig_dir = os.getcwd()
            os.chdir(pkg_path)
            arch_path = os.path.join(pkg_path, 'install_files')
            sys.path.insert(0, arch_path)
            if in_content:
                os.chdir(arch_path)

            sys.argv = [script_name]
            sys.argv.extend(script_args)
            if args.args:
                sys.argv.extend(args.args)
            with open(script_name) as f:
                code = compile(f.read(), script_name, 'exec')

            if not in_content:
                # Setup script expects to be run from in content dir, even if
                # it was not located in archive dir.
                os.chdir(arch_path)

            exec(code, {'__name__': '__main__', '__file__': script_name})
            # *** DO NO EXPECT EXECUTION PAST THIS POINT ***
            # setup script may call sys.exit()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    finally:
        if orig_dir:
            os.chdir(orig_dir)
        # Clean up our temporary working directory
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return 0
"""


def make_package(content_dir, file_name, setup_script, script_args=(),
                 sha256=True, compress='gz', follow=False, tools=False,
                 quiet=False, label=None, password=None):
    """Create a self-extracting archive.

    Arguments:
    content_dir  -- Directory containing files to archive in installer.
    file_name    -- Name for the executable that is created
    setup_script -- Python script executed from within extracted content
    script_args  -- Arguments to pass to setup script when run
    sha256       -- Enable (True) or disable (False) SHA256
    compress     -- Type of compression ('gz', 'bz2', 'xz')
    follow       -- Follow symlinks in the archive if True
    tools        -- Include installtools module if True
    quiet        -- Do not print any messages other than errors if True
    label        -- Text string describing the package
    password     -- Password protect contents if not None

    Return:
    Path to self-extracting installer executable.

    """
    if not content_dir:
        raise RuntimeError('content directory not specified')
    if not os.path.isdir(content_dir):
        raise RuntimeError('content directory not found: ' + content_dir)
    if not file_name:
        raise RuntimeError('installer name not specified')
    if not setup_script:
        raise RuntimeError('setup script not specified')

    in_content = False
    content_dir = os.path.abspath(content_dir)

    if not os.path.dirname(setup_script):
        # If setup_script has no dir in path, then it is in content dir.
        setup_script = os.path.join(content_dir, setup_script)
        in_content = True
    else:
        setup_script = os.path.abspath(setup_script)
        if os.path.dirname(setup_script) == content_dir:
            in_content = True

    if not os.path.isfile(setup_script):
        raise RuntimeError('setup script not found: ' + setup_script)

    # If installer name ends with ".py", then remove the suffix.
    if file_name.endswith('.py'):
        file_name = file_name.rsplit('.py', 1)[0]

    # Create a temporary directory to do work in.
    tmp_dir = tempfile.mkdtemp('_pymakeself')
    pkg_path = os.path.join(tmp_dir, os.path.basename(file_name))
    try:
        _copy_package_files(pkg_path, content_dir, setup_script, in_content,
                            tools, password)
        tar_path, sha256_sum, aes_tar_path = _archive_package(
            pkg_path, compress, sha256, password)
        return _pkg_to_exe(tar_path, file_name, setup_script, script_args,
                           in_content, sha256_sum, label, aes_tar_path)
    finally:
        # Always clean up temporary work directory.
        shutil.rmtree(tmp_dir, True)


def _copy_package_files(pkg_path, install_src, setup_script, in_content,
                        tools, password):
    os.mkdir(pkg_path)
    install_dst = os.path.join(pkg_path, 'install_files')

    print('===> packaging files from', install_src)
    # Copy the install files.
    ignores = shutil.ignore_patterns('*~', '.#*', '.ssh')
    shutil.copytree(install_src, install_dst, ignore=ignores)

    # Copy .ssh/authorized_keys if one exists in source.
    src_dot_ssh = os.path.join(install_src, '.ssh')
    src_auth_keys = os.path.join(src_dot_ssh, 'authorized_keys')
    if os.path.isfile(src_auth_keys):
        print('===> packaging only authorized_keys file from', src_dot_ssh)
        dst_dot_ssh = os.path.join(install_dst, '.ssh')
        os.mkdir(dst_dot_ssh, 0o700)
        dst_dot_ssh = os.path.join(dst_dot_ssh, 'authorized_keys')
        shutil.copyfile(src_auth_keys, dst_dot_ssh)
        shutil.copymode(src_auth_keys, dst_dot_ssh)

    if setup_script:
        if in_content:
            print('===> setup script already included in archived files')
        else:
            print('===> packaging setup script:', setup_script)
            # Copy the installer script to the package dir as install.py
            setup_name = os.path.basename(setup_script)
            shutil.copyfile(setup_script, os.path.join(pkg_path, setup_name))

        if tools:
            print('===> packaging PyMakeSelf install tools')
            # Copy the account utility module to the package dir as well.
            dir_name = 'installtools'
            parent_path = os.path.dirname(os.path.abspath(__file__))
            shutil.copytree(os.path.join(parent_path, dir_name),
                            os.path.join(pkg_path, dir_name))

    if password is not None:
        dir_name = 'aes'
        dst_dir = os.path.dirname(pkg_path)
        parent_path = os.path.dirname(os.path.abspath(__file__))
        shutil.copytree(os.path.join(parent_path, dir_name),
                        os.path.join(dst_dir, dir_name))


def _archive_package(pkg_path, compress, sha256, password):
    tar_path = pkg_path + '.tar.' + compress

    def reset(tarinfo):
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        return tarinfo

    pkg_parent = os.path.dirname(pkg_path)
    orig_dir = os.getcwd()
    os.chdir(pkg_parent)

    print('===> creating tar file:', os.path.basename(tar_path))
    with tarfile.open(tar_path, 'w:' + compress) as tar:
        # Package path must only contain the directory to tar.
        tar.add(os.path.basename(pkg_path), filter=reset)

    aes_tar_path = None
    if password is not None:
        # Package the aes module into its own tarfile.
        aes_pkg_path = os.path.join(pkg_parent, 'aes')
        aes_tar_path = aes_pkg_path + '.tar.gz'
        print('===> packaging aes module:', os.path.basename(aes_tar_path))
        with tarfile.open(aes_tar_path, 'w:gz') as tar:
            # Package path must only contain the directory to tar.
            tar.add(os.path.basename(aes_pkg_path), filter=reset)

        # Encrypt the package tarfile.
        from pymakeself.aes import aesutil
        aes_path = tar_path+'.aes'
        print('===> encrypting', os.path.basename(tar_path), "-->",
              os.path.basename(aes_path))
        with open(tar_path, 'rb') as tar_file:
            with open(aes_path, 'wb') as aes_file:
                aesutil.encrypt(password, tar_file, aes_file)
        os.unlink(tar_path)
        tar_path = aes_path

    os.chdir(orig_dir)

    sha256_sum = None
    if sha256:
        # Import hashlib here, not at top of script, in case user cannot use
        # hashlib on their platform and needs to omit the checksum.
        import hashlib
        BLOCKSIZE = 65536
        sha256 = hashlib.sha256()
        with open(tar_path, 'rb') as tar_file:
            buf = tar_file.read(BLOCKSIZE)
            while buf:
                sha256.update(buf)
                buf = tar_file.read(BLOCKSIZE)
        sha256_sum = sha256.hexdigest()
        print('===> SHA256 (%s) = %s' % (os.path.basename(tar_path), sha256_sum))
    else:
        print('===> skipping SHA256')

    return tar_path, sha256_sum, aes_tar_path


def _pkg_to_exe(tar_path, file_name, setup_script, script_args, in_content,
                sha256_sum, label, aes_tar_path):
    tar_name = os.path.basename(tar_path)
    exe_path = os.path.abspath(file_name) + '.py'
    if os.path.exists(exe_path):
        print('===> removing existing installer:', os.path.relpath(exe_path),
              file=sys.stderr)
        os.unlink(exe_path)

    print('===> writing executable:', os.path.relpath(exe_path))
    with open(exe_path, 'wb') as exe_f:
        # Write interpreter invocation line.
        exe_f.write(b'#!/usr/bin/env python\n')
        # Write comment into executable script.
        exe_f.write(b'#\n# Extracts archive and runs setup script.\n#\n')

        # Write executable logic, from template, into executable script.
        exe_f.write(_exe_template)

        # Write data about install module, tar file, and package into script.
        exe_f.write(("\ntar_name = '%s'\n" % (tar_name,)).encode())
        if sha256_sum:
            exe_f.write(("sha256_sum = '%s'\n" % (sha256_sum,)).encode())
        else:
            exe_f.write(b"sha256_sum = None\n")
        if label:
            exe_f.write(("label = '%s'\n" % (label,)).encode())
        else:
            exe_f.write(b"label = None\n")
        if aes_tar_path:
            exe_f.write(b"encrypted = True\n")
        else:
            exe_f.write(b"encrypted = False\n")
        exe_f.write(
            ("pkg_name = '%s'\n" % (tar_name.rsplit('.tar',1)[0],)).encode())
        if setup_script:
            script_name = os.path.basename(setup_script)
            exe_f.write(("script_name = '%s'\n" % (script_name,)).encode())
            if in_content:
                exe_f.write(b"in_content = True\n")
            else:
                exe_f.write(b"in_content = False\n")
            exe_f.write(
                ('script_args = %s\n' %(repr(tuple(script_args)),)).encode())
        else:
            exe_f.write(b"script_name = None\n")

        # If encrypted, write base64-encoded aes tar into executable script.
        if aes_tar_path:
            exe_f.write(b'\nAES_PKG_DATA = b"""\n')
            with open(aes_tar_path, 'rb') as aes_pkg_f:
                base64.encode(aes_pkg_f, exe_f)
            exe_f.write(b'"""\n')

        # Write base64-encoded tar file into executable script.
        exe_f.write(b'\nPKG_DATA = b"""\n')
        with open(tar_path, 'rb') as pkg_f:
            base64.encode(pkg_f, exe_f)
        exe_f.write(b'"""\n\n')

        exe_f.write(b'if __name__ == "__main__":\n'
                    b'    sys.exit(main())\n')

    # Remove the tar file that was written into the executable script.
    os.unlink(tar_path)

    # Set the permissions on the executable installer script that was created.
    os.chmod(exe_path,
             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |  # rwx user
             stat.S_IRGRP | stat.S_IXGRP |                 # rx group
             stat.S_IROTH | stat.S_IXOTH)                  # rx other

    return exe_path


def main(prg=None):
    import argparse
    ap = argparse.ArgumentParser(
        prog=prg, description='Create executable (self-extracting) installer '
        'Python script.',
        epilog='home page: https://github.com/gammazero/pymakeself')
    ap.set_defaults(compress='gz')

    ap.add_argument('--bzip2', action='store_const', const='bz2',
                    dest='compress',
                    help='Compress using bzip2 instead of gzip.')
    ap.add_argument(
        '--encrypt', '-e', action='store_true',
        help='Encrypt the contents of the archive using a password which is '
        'entered on the terminal in response to a prompt (this will not be '
        'echoed).')
    ap.add_argument('--follow', action='store_true',
                    help='Follow symlinks in the archive.')
    ap.add_argument('--gzip', action='store_const', const='gz',
                    dest='compress', help='Compress using gzip (default).')
    ap.add_argument('--label', metavar='text',
                    help='Arbitrary text string describing the package. It '
                    'will be displayed while extracting the files.')
    ap.add_argument('--nosha256', action='store_false', dest='sha256',
                    help='Do not calculate SHA256 checksum for archive.')
    ap.add_argument(
        '--password', '-P',
        help='Use specified password to encrypt archive. THIS IS INSECURE!  '
        'Many multi-user operating systems provide ways for any user to see '
        'the current command line of any other user. Storing the plaintext '
        'password as part of a command line in an automated script is an even '
        'greater risk.  Whenever possible, use the non-echoing, interactive '
        'prompt to enter passwords.  Specifying a password implies --encrypt.')
    ap.add_argument('--quiet', '-q', action='store_true',
                    help='Do not print any messages other than errors.')
    ap.add_argument(
        '--sshinstall', action='append', metavar='host_addr',
        help='Install on the specified host (i.e. root@devbox1). Multiple OK. '
        'Uses scp to copy the installer to the host and then uses ssh to run '
        'the installer.')
    ap.add_argument('--tools', '-t', action='store_true',
                    help='Include installtools module.')
    ap.add_argument('--version', action='version', version=__version__)
    if 'lzma' in dir():
        ap.add_argument(
            '--xz', action='store_const', const='xz', dest='compress',
            help='Compress using xz instead of gzip. This requires Python3.x '
            'for both creation and extraction.')
    ap.add_argument('content', help='Directory containing files to '
                    'archive in installer.')
    ap.add_argument('installer_name',
                    help='Name for the executable that is created.')
    ap.add_argument(
        'setup_script',
        help='Python script to be executed from within the extracted content '
        'directory, that is run using the same Python interpreter used to run '
        'the installer. If the script is already located inside the content '
        'directory then only specify the name of the script.  Otherwise, '
        'provide a relative or absolute path to the script so that it can be '
        'copied into the installer archive.  The special value "@accountutil" '
        'tells pymakeself to use the UNIX account creation tool, included in '
        'the pymakeself package, as the setup_command')

    ap.add_argument('setup_args', nargs=argparse.REMAINDER,
                    help='Arguments to pass into Python setup script when run '
                    'during execution of the installer.')
    args = ap.parse_args()

    if args.setup_script:
        if args.setup_script == '@accountutil':
            args.setup_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'installtools', 'accountutil.py')
        elif os.path.dirname(args.setup_script):
            args.setup_script = os.path.expanduser(args.setup_script)

    passwd = None
    pw_str = None
    if args.password:
        args.encrypt = True
        passwd = args.password
        pw_str = '<specified, not shown>'

    if args.encrypt:
        if passwd is None:
            passwd = ""

    print('compress:', args.compress)
    print('sha256:', args.sha256)
    print('encrypt:', args.encrypt)
    print('password:', pw_str)
    print('quiet:', args.quiet)
    print('tools:', args.tools)
    print('follow:', args.follow)
    print('label:', args.label)
    print('content_dir: ', args.content, '/', sep='')
    print('installer_name:', args.installer_name)
    if args.setup_script:
        print('setup_script: ', end='')
        if not os.path.dirname(args.setup_script):
            print(os.path.join(args.content, args.setup_script))
        else:
            print(os.path.abspath(args.setup_script))
        print('script args:',
              ' '.join(('"%s"' % (a,) for a in args.setup_args)))
    else:
        print('setup_script:', 'None')

    print()
    try:
        exe_path = make_package(
            args.content, args.installer_name, args.setup_script,
            args.setup_args, args.sha256, args.compress, args.follow,
            args.tools, args.quiet, args.label, passwd)
    except Exception as ex:
        print(ex, file=sys.stderr)
        return 1

    if args.sshinstall:
        from . import installhosts
        if not installhosts.install_on_hosts(exe_path, args.sshinstall, None):
            return 1
    else:
        print('\nRun', os.path.basename(exe_path), 'to extract files and run '
              'the setup script.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
