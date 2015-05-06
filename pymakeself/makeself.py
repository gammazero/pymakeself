"""
Create an executable (self-extracting) installer Python script.

The installer contains a copy of the contents of a specified directory, and it contains the specified install script.  When the installer is run, it extracts itself and runs the install script.

The installer is created by first creating a directory, package_name, that
contains a subdirectory called 'install_files'.  The 'install_files'
subdirectory contains a copy of the contents of the specified archive_dir.  If
a setup_script is specified, then that setup_script also copied into the
package_name dir, along with the installtools if those are requested.

    somewhere/
        archive_dir/ }---------+
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


The package_name directory is they archived into a tar file:

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

__version__ = '1.0.0'
__author__ = 'Andrew J. Gillis'
__maintainer__ = 'Andrew J. Gillis'
__email__ = 'andrew.gillis@gmail.com'

_exe_template = \
"""
import base64
import tarfile
import shutil
import tempfile
import os
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h', '-?'):
        print('Usage: python', sys.argv[0], '[--check] [--extract]')
        print('    --check   : Check hash and exit')
        print('    --extract : Extract package contents and exit')
        print()
        return 0

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

        if len(sys.argv) > 1 and sys.argv[1] == '--check':
            return 0

        # Unpack the tarfile.
        with tarfile.open(tar_path) as t:
            t.extractall(tmp_dir)
        os.unlink(tar_path)

        pkg_path = os.path.join(tmp_dir, pkg_name)
        if len(sys.argv) > 1 and sys.argv[1] == '--extract':
            print('Extracted package:', pkg_path)
            tmp_dir = None
            return 0

        if script_name:
            sys.path.insert(0, pkg_path)
            orig_dir = os.getcwd()
            if archive_name:
                arch_path = os.path.join(pkg_path, archive_name)
                sys.path.insert(0, arch_path)
                # Just in case setup script expects to be in archive dir.
                os.chdir(arch_path)
            else:
                os.chdir(pkg_path)
            sys.argv = [script_name]
            sys.argv.extend(script_args)
            with open(script_name) as f:
                code = compile(f.read(), script_name, 'exec')
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


if __name__ == '__main__':
    sys.exit(main())
"""


def make_package(archive_dir, file_name, setup_script=None, script_args=(),
                 target=None, md5=True, compress='gz', follow=False,
                 tools=False, quiet=False):
    if not os.path.isdir(archive_dir):
        raise RuntimeError('archive directory not found: ' + archive_dir)

    in_archive = False
    archive_dir = os.path.abspath(archive_dir)
    if setup_script:
        if os.path.dirname(setup_script) == '.':
            # If setup_script starts with ./ this means it is in archive dir.
            setup_script = os.path.join(
                archive_dir, os.path.basename(setup_script))
            in_archive = True
        else:
            setup_script = os.path.abspath(setup_script)
            if os.path.dirname(setup_script) == archive_dir:
                in_archive = True

        if not os.path.isfile(setup_script):
            raise RuntimeError('setup script not found: ' + setup_script)

    # If installer name ends with ".py", then remove the suffix.
    if file_name.endswith('.py'):
        file_name = file_name.rsplit('.py', 1)[0]

    # Create a temporary directory to do work in.
    tmp_dir = tempfile.mkdtemp('_pymakeself')
    pkg_path = os.path.join(tmp_dir, os.path.basename(file_name))
    try:
        _copy_package_files(pkg_path, archive_dir, setup_script, in_archive,
                            tools)
        tar_path, md5_sum = _archive_package(pkg_path, compress, md5)
        archive_name = os.path.basename(archive_dir) if in_archive else None
        return _pkg_to_exe(tar_path, file_name, setup_script, script_args,
                           archive_name, md5_sum)
    finally:
        # Always clean up temporary work directory.
        shutil.rmtree(tmp_dir, True)


def _copy_package_files(pkg_path, install_src, setup_script, in_archive,
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
        if in_archive:
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


def _pkg_to_exe(tar_path, file_name, setup_script, script_args, archive_name,
                md5_sum):
    tar_name = os.path.basename(tar_path)
    exe_path = os.path.abspath(file_name) + '.py'
    if os.path.exists(exe_path):
        print('===> removing existing installer:', exe_path, file=sys.stderr)
        os.unlink(exe_path)

    print('===> writing executable:', exe_path)
    with open(exe_path, 'w') as exe_f:
        # Write interpreter invocation line.
        exe_f.write('#!/usr/bin/env python\n#\n')
        # Write comment into executable script.
        exe_f.write('#\n')
        exe_f.write('# Extracts archive %s and runs setup script.' % tar_name)
        exe_f.write('\n#\n')
        exe_f.write('from __future__ import print_function\n')
        # Write base64-encoded tar file into executable script.
        exe_f.write('PKG_DATA = b"""\n')
        with open(tar_path) as pkg_f:
            base64.encode(pkg_f, exe_f)
        # Write data about install module, tar file, and package into script.
        exe_f.write('"""\n\n')
        exe_f.write("tar_name = '%s'\n" % (tar_name,))
        if md5_sum:
            exe_f.write("md5_sum = '%s'\n" % (md5_sum,))
        else:
            exe_f.write("md5_sum = None\n" % (md5_sum,))
        exe_f.write("pkg_name = '%s'\n" % (tar_name.rsplit('.tar', 1)[0],))
        if setup_script:
            script_name = os.path.basename(setup_script)
            #script_name = script_name.rsplit('.py', 1)[0]
            exe_f.write("script_name = '%s'\n" % (script_name,))
            if archive_name:
                exe_f.write("archive_name = '%s'\n" % (archive_name,))
            else:
                exe_f.write("archive_name = None\n")
            exe_f.write('script_args = %s\n' % (repr(tuple(script_args)),))
        else:
            exe_f.write("script_name = None\n")

        # Write executable logic, from template, into executable script.
        exe_f.write(_exe_template)

    # Remove the tar file that was written into the executable script.
    os.unlink(tar_path)

    # Set the permissions on the executable installer script that was created.
    os.chmod(exe_path,
             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |  # rwx user
             stat.S_IRGRP | stat.S_IXGRP |                 # rx group
             stat.S_IROTH | stat.S_IXOTH)                  # rx other

    return exe_path


def _usage(prg):
    print('Usage: python', prg, '[options] archive_dir file_name setup_script '
          '[args]')
    print('\nOptions:')
    print('  --version    : Print out PyMakeSelf version number and exit.')
    print('  --help, -h   : Print out this help message.')
    print('  --quiet, -q  : Do not print any messages other than errors.')
    print('  --tools, -t  : Include installtools module.')
    print('  --gzip       : Compress using gzip (default).')
    print('  --bzip2      : Compress using bzip2 instead of gzip.')
    if 'lzma' in dir():
        print('  --xz         : Compress using xz instead of gzip.')
    print('  --current    : Extract to current directory, instead of to a '
          'temporary')
    print('                 directory (temporary is default).  This is the '
          'same as ')
    print('                 specifying --target ./')
    print('  --target dir : Extract directly to a target directory, '
          'instead of to a ')
    print('                 temporary directory (temporary is default).')
    print('  --nomd5      : Do not calculate MD5 for archive.')
    print('  --follow     : Follow symlinks in the archive.')
    print('  --install    : Install on the specified host.  Multiple OK.')
    print()
    print('Do not forget to give a fully qualified startup script name')
    print('(i.e. with a ./ prefix if inside the archive).')
    print()
    print('\nExample:')
    print('python', prg, '/storage/myfiles install_stuff setup.py x y z')
    print()


def main(prg=None):
    compress = 'gz'
    quiet = False
    tools = False
    md5 = True
    follow = False
    target = None
    archive_dir = file_name = setup_script = None
    script_args = ()
    install = []

    args = list(sys.argv)
    if prg:
        args.pop(0)
    else:
        prg = os.path.basename(args.pop(0))

    missing_msg = 'missing argument following'
    while args:
        arg = args.pop(0)
        if arg in ('--version', '-v'):
            print('PyMakeSelf version', __version__)
            return 0
        elif arg == '--gzip':
            compress = 'gz'
        elif arg == '--bzip2':
            compress = 'bz2'
        elif arg == '--xz' and 'lzma' in dir():
            compress = 'xz'
        elif arg in ('--tools', '-t'):
            tools = True
        elif arg in ('--quiet', '-q'):
            quiet = True
        elif arg == '--target':
            if not args:
                raise RuntimeError(missing_msg, arg)
            target = args.pop(0)
        elif arg == '--current':
            target = './'
        elif arg == '--nomd5':
            md5=False
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
        elif not archive_dir:
            archive_dir = os.path.abspath(os.path.expanduser(arg))
        elif not file_name:
            file_name = os.path.expanduser(arg)
        else:
            if arg == 'accountutil':
                setup_script = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    'installtools', 'accountutil.py')
            else:
                setup_script = os.path.expanduser(arg)
            script_args = tuple(args)
            break

    if not (archive_dir and file_name):
        print('missing one or more required arguments', file=sys.stderr)
        print('see:', prg, '--help', file=sys.stderr)
        return 1

    print('compress:', compress)
    print('target:', target)
    print('md5:', md5)
    print('quiet:', quiet)
    print('tools:', tools)
    print('follow:', follow)
    print('archive_dir:', archive_dir)
    print('file_name:', file_name)
    print('setup_script:', setup_script)
    print('script args:', ' '.join(('"%s"' % (a,) for a in script_args)))

    try:
        exe_path = make_package(
            archive_dir, file_name, setup_script, script_args, target, md5,
            compress, follow, tools, quiet)
    except Exception as ex:
        print(ex, file=sys.stderr)
        return 1

    if install:
        # Create temporary conf file.
        import installhosts
        if not installhosts.install_on_hosts(exe_path, install, None):
            return 1
    else:
        print('\nRun', os.path.basename(exe_path), 'to extract files and run '
              'the setup script.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
