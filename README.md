# pymakeself

Make self-extracting archives with Python, on most operating systems.

## Overview

pymakeself is a Python script that generates a self-extractable tar.gz archive from a directory.  The resulting file appears as a Python script, and can be launched as is.  The archive will then uncompress itself to a temporary directory and run an optional python setup script.  A pymakeself archive also includes a SHA256 checksum for integrity self-validation.

The makeself.py script itself is used only to create the archive from a directory of files.  The resulting archive is a compressed (gzip or bzip2) TAR archive, with a small Python script stub at the beginning.  This script performs all the steps of extracting the files, running the embedded setup script, and cleaning up afterward.  The user only needs to "run" the archive to install its contents, i.e `python install-nice-app.py`.

This code is intended to be as portable as possible and should run on any system with an installation of python2.7 or later.  Other than Python, it does not rely on external utilities such as tar, gzip, bash etc.

## Install

```
sudo pip install pymakeself
```

## Usage

The pymakeself package installs the `pymakeself` command.  This is the same as running `python -m pymakeself`, and has the following syntax:

```
pymakeself [args] content_dir file_name setup_script [setup_args]
```
The `args` beginning with `-` or `--` are optional.  The available options are:

`--help, -h` : Print out this help message.

`--bzip2` : Use bzip2 instead of gzip for better compression.

`--encrypt, -e` :  Encrypt the contents of the archive using a password which is entered on the terminal in response to a prompt (this will not be echoed). The password prompt is repeated to save the user from typing errors.

`--follow` : Follow the symbolic links inside of the archive directory, i.e. store the files that are being pointed to instead of the links themselves.

`--gzip` : Use gzip for compression (is the default)

`--label text` : Arbitrary text string describing the package. It will be displayed while extracting the files. 

`--nosha256` : Disable the creation of a SHA256 checksum for the archive.  This speeds up the extraction process if integrity checking is not necessary.

`--password, -P` : Use specified password to encrypt archive. THIS IS INSECURE! Many multi-user operating systems provide ways for any user to see the current command line of any other user. Storing the plaintext password as part of a command line in an automated script is an even greater risk. Whenever possible, use the non-echoing, interactive prompt to enter passwords. Specifying a password implies --encrypt.

`--quiet, -q` : Do not print any messages other than errors.

`--sshinstall host_addr` : Install on the specified host (i.e. root@devbox1). Multiple OK. Uses scp to copy the installer to the host and then uses ssh to run the installer.

`--tools, -t`  : Include installtools module.

`--version` : Prints the version number on stdout, then exits immediately

`--xz` : Compress using xz instead of gzip.  This requires Python3.x for both creation and extraction.

`content_dir` is the name of the directory that contains the files to be archived.

`file_name` is the name of the installer script to be created.

`setup_script` is a Python script to be executed from within the extracted content directory, that is run using the same Python interpreter used to run the installer.  If the script is already located inside the content directory then only specify the name of the script.  Otherwise, provide a relative or absolute path to the script so that it can be copied into the installer archive.  The special value `@accountutil` tells pymakeself to use the Unix [account creation tool](https://github.com/gammazero/pymakeself/blob/master/pymakeself/installtools/accountutil.py), included in the pymakeself package, as the `setup_script`.

`setup_args` are optional arguments to pass into Python setup script when run during execution of the installer.  Additional arguments can also be specified on the command line when running the installer.

Here is an example, assuming the user has a package image stored in a `/home/jane/mysoft`, and wants to generate a self-extracting package named install_mysoft.py, which will launch the `setup.py` script initially stored in `/home/jane/mysoft`:
```
pymakeself.py --label "Jane's Nice Software Package" /home/jane/mysoft install_mysoft setup.py
```

Here is how I created a `install_pymakeself.py` installer that installs the pymakeself distribution:
```
pymakeself --label "PyMakeSelf by Andrew Gillis" pymakeself install_pymakeself setup.py install
```

Self-extracting archives generated with pymakeself can be passed the following arguments:

`--check` : Check the integrity of the archive by verifying the embedded SHA256 checksum.  Does not extract the archive.

`--list` : List the files in the archive.

`--extract` : Extract package contents to temporary directory and exit.

Any other command line arguments given to the self-extracting archive are passed as arguments to the embedded setup script.

## Examples

### Installer with Setup Script
Create an installer, named install_stuff, that runs setup.py:

```
pymakeself /storage/myfiles install_stuff setup.py
```

Run the installer to install the content and run the setup.py script.  Notice that additional arguments are passed to the setup script at install time:
```
python install_stuff.py --logdir /var/log/mystuff
```

### Install User Account
Create an installer that runs the `accountutil.py` tool (one of the modules in the pymakeself installtools) as the setup script, to create the "ajg" user account:
```
pymakeself ~/ajg_dot_files create_ajg @accountutil \
-c 'Andrew J. Gillis' -i ./ ajg
```
Specifying `@accountutil` as the setup script tells pymakeself to use the UNIX account creation tool, that is included with the pymakeself package.

Notice that the `-i` argument to accountutil (the directory with files to install) specifies `./` instead of `ajg_dot_files`.  This is because the setup file is always run from within the archive directory, so the install directory is the current directory.

## Library

The pymakeself package can also be imported into a python script and used as a library.

```
from pymakeself import makeself

exe_path = makeself.make_package(
    "/home/ajg/stuff", "install_stuff", "setup.py",
    compress="bz2", label="my cool stuff")

```

To see documentation on `make_package()` run: `pydoc pymakeself.makeself.make_package`

## Project Links

- Project page: <https://github.com/gammazero/pymakeself>
- Documentation: <https://github.com/gammazero/pymakeself/wiki>
- License: <http://www.opensource.org/licenses/mit-license.php>

## Bugs and Issues

<https://github.com/gammazero/pymakeself/issues>

## Acknowledgments

This script was inspired by, and modeled after, [makeself](https://makeself.io/) by Stephane Peter.

Pure-Python AES cryptography adapted from [pyaes](https://github.com/ricmoo/pyaes) by Richard Moore
