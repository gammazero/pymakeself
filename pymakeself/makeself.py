"""
Create an executable (self-extracting) installer Python script.

The installer contains a copy of the contents of a specified directory, and it contains the specified install script.  When the installer is run, it extracts itself and runs the install script.

The installer is created by first creating a directory, package_name, that
contains a subdirectory called 'install_files'.  The 'install_files'
subdirectory contains a copy of the contents of the specified content_dir.  If
a setup_script is specified, then that setup_script also copied into the
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
        +--------------------+      |
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
run the setup_script script packages inside it.

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

__version__ = '0.2.2'

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


def main():
    ap = argparse.ArgumentParser(description='Self-extracting install script')
    ap.add_argument('--check', action='store_true', help='Check hash and exit')
    ap.add_argument('--extract', action='store_true',
                    help='Extract package contents and exit')
    args = ap.parse_args()

    tmp_dir = None
    orig_dir = None
    try:
        # Create a temporary working directory
        tmp_dir = tempfile.mkdtemp()

        # Write the tarfile into the temporary directory
        tar_path = os.path.join(tmp_dir, tar_name)
        with open(tar_path, 'wb') as fp:
            fp.write(base64.decodestring(PKG_DATA))

        if md5_sum:
            import hashlib
            BLOCKSIZE = 65536
            md5 = hashlib.md5()
            with open(tar_path, 'rb') as tar_file:
                buf = tar_file.read(BLOCKSIZE)
                while buf:
                    md5.update(buf)
                    buf = tar_file.read(BLOCKSIZE)
            if md5_sum != md5.hexdigest():
                raise RuntimeError('MD5 checksum mismatch.  The file may be '
                                   'corrupted or incomplete.')
            print('===> MD5 is good')
        else:
            print('===> MD5 not checked')

        if args.check:
            return 0

        if label:
            print(label)

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
            with open(script_name) as f:
                code = compile(f.read(), script_name, 'exec')

            if not in_content:
                # Setup script expects to be run from in content dir, even if
                # it was not located in archive dir.
                os.chdir(arch_path)

            exec(code, {'__name__': '__main__'})
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


def make_package(content_dir, file_name, setup_script=None, script_args=(),
                 target=None, md5=True, compress='gz', follow=False,
                 tools=False, quiet=False, label=None):
    if not os.path.isdir(content_dir):
        raise RuntimeError('content directory not found: ' + content_dir)

    in_content = False
    content_dir = os.path.abspath(content_dir)
    if setup_script:
        if not os.path.dirname(setup_script):
            # If setup_script starts has not dir in path, it is in content dir.
            setup_script = os.path.join(
                content_dir, os.path.basename(setup_script))
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
                            tools)
        tar_path, md5_sum = _archive_package(pkg_path, compress, md5)
        return _pkg_to_exe(tar_path, file_name, setup_script, script_args,
                           in_content, md5_sum, label)
    finally:
        # Always clean up temporary work directory.
        shutil.rmtree(tmp_dir, True)


def _copy_package_files(pkg_path, install_src, setup_script, in_content,
                        tools):
    os.mkdir(pkg_path)
    install_dst = os.path.join(pkg_path, 'install_files')

    print('===> packaging files from', install_src, 'to', install_dst)
    # Copy the install files.
    ignores = shutil.ignore_patterns('*.py?', '*~', '.#*', '.ssh')
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


def _archive_package(pkg_path, compress, md5):
    tar_path = pkg_path + '.tar.' + compress

    def reset(tarinfo):
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        return tarinfo

    pkg_parent = os.path.dirname(pkg_path)
    orig_dir = os.getcwd()
    os.chdir(pkg_parent)

    print('===> creating tar file:', tar_path)
    with tarfile.open(tar_path, 'w:' + compress) as tar:
        # Package path must only contain the directory to tar.
        tar.add(os.path.basename(pkg_path), filter=reset)

    os.chdir(orig_dir)

    md5_sum = None
    if md5:
        # Import hashlib here, not at top of script, incase user cannot use
        # hashlib on their platform and needs to omit the checksum.
        import hashlib
        BLOCKSIZE = 65536
        md5 = hashlib.md5()
        with open(tar_path, 'rb') as tar_file:
            buf = tar_file.read(BLOCKSIZE)
            while buf:
                md5.update(buf)
                buf = tar_file.read(BLOCKSIZE)
        md5_sum = md5.hexdigest()
        print('===> MD5 (%s) = %s' % (os.path.basename(tar_path), md5_sum))
    else:
        print('===> skipping MD5')

    return tar_path, md5_sum


def _pkg_to_exe(tar_path, file_name, setup_script, script_args, in_content,
                md5_sum, label):
    tar_name = os.path.basename(tar_path)
    exe_path = os.path.abspath(file_name) + '.py'
    if os.path.exists(exe_path):
        print('===> removing existing installer:', exe_path, file=sys.stderr)
        os.unlink(exe_path)

    u8 = 'utf-8'
    print('===> writing executable:', exe_path)
    with open(exe_path, 'wb') as exe_f:
        # Write interpreter invocation line.
        exe_f.write(b'#!/usr/bin/env python\n')
        # Write comment into executable script.
        exe_f.write(b'#\n# Extracts archive and runs setup script.\n#\n')

        # Write executable logic, from template, into executable script.
        exe_f.write(_exe_template)

        # Write data about install module, tar file, and package into script.
        s = "\ntar_name = '%s'\n" % (tar_name,)
        exe_f.write(s.encode(u8))
        if md5_sum:
            exe_f.write(("md5_sum = '%s'\n" % (md5_sum,)).encode(u8))
        else:
            exe_f.write(b"md5_sum = None\n")
        if label:
            exe_f.write(("label = '%s'\n" % (label,)).encode(u8))
        else:
            exe_f.write(b"label = None\n")
        exe_f.write(
            ("pkg_name = '%s'\n" % (tar_name.rsplit('.tar',1)[0],)).encode(u8))
        if setup_script:
            script_name = os.path.basename(setup_script)
            exe_f.write(("script_name = '%s'\n" % (script_name,)).encode(u8))
            if in_content:
                exe_f.write(b"in_content = True\n")
            else:
                exe_f.write(b"in_content = False\n")
            exe_f.write(
                ('script_args = %s\n' %(repr(tuple(script_args)),)).encode(u8))
        else:
            exe_f.write(b"script_name = None\n")

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

    ap.add_argument('--label', metavar='text',
                    help='Arbitrary text string describing the package. It '
                    'will be displayed while extracting the files.')
    ap.add_argument('--gzip', action='store_const', const='gz',
                    dest='compress', help='Compress using gzip (default).')
    ap.add_argument('--bzip2', action='store_const', const='bz2',
                    dest='compress',
                    help='Compress using bzip2 instead of gzip.')
    if 'lzma' in dir():
        ap.add_argument('--xz', action='store_const', const='xz',
                        dest='compress',
                        help='Compress using xz instead of gzip.')
    ap.add_argument('--follow', action='store_true',
                    help='Follow symlinks in the archive.')
    ap.add_argument('--tools', '-t', action='store_true',
                    help='Include installtools module.')
    ap.add_argument('--quiet', '-q', action='store_true',
                    help='Do not print any messages other than errors.')
    ap.add_argument('--target', metavar='dir',
                    help='Extract directly to a target directory, instead of '
                    'to a temporary directory (temporary is default).')
    ap.add_argument('--current', action='store_const', const='./',
                    dest='target', help='Extract to current directory, '
                    'instead of to a temporary')
    ap.add_argument('--nomd5', action='store_false', dest='md5',
                    help='Do not calculate MD5 for archive.')
    ap.add_argument('--install', action='append', metavar='host_addr',
                    help='Install on the specified host.  Multiple OK.')
    ap.add_argument('--version', action='version', version=__version__)
    ap.add_argument('content', help='Directory containing files to be '
                    'archived in installer.')
    ap.add_argument('installer_name',
                    help='Name for the executable that is created.')
    ap.add_argument(
        'setup_script', nargs='?',
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
        if args.setup_script =='@accountutil':
            args.setup_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'installtools', 'accountutil.py')
        elif os.path.dirname(args.setup_script):
            args.setup_script = os.path.expanduser(args.setup_script)

    print('compress:', args.compress)
    print('target:', args.target)
    print('md5:', args.md5)
    print('quiet:', args.quiet)
    print('tools:', args.tools)
    print('follow:', args.follow)
    print('label:', args.label)
    print('content_dir: ', args.content, '/', sep='')
    print('installer_name:', args.installer_name)
    print('setup_script:', os.path.relpath(args.setup_script))
    print('script args:', ' '.join(('"%s"' % (a,) for a in args.setup_args)))

    try:
        exe_path = make_package(
            args.content, args.installer_name, args.setup_script,
            args.setup_args, args.target, args.md5, args.compress,
            args.follow, args.tools, args.quiet, args.label)
    except Exception as ex:
        print(ex, file=sys.stderr)
        return 1

    if args.install:
        # Create temporary conf file.
        from . import installhosts
        if not installhosts.install_on_hosts(exe_path, args.install, None):
            return 1
    else:
        print('\nRun', os.path.basename(exe_path), 'to extract files and run '
              'the setup script.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
