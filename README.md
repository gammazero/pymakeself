=================================================================
PyMakeSelf - Make self-extracting archives on any OS with Python
=================================================================

makeself.py is a small Python script that generates a self-extractable tar.gz archive from a directory.  The resulting file appears as a Python script, and can be launched as is.  The archive will then uncompress itself to a temporary directory and an optional arbitrary command will be executed (for example an installation script).  Makeself archives also include checksums for integrity self-validation (MD5 checksum).

The makeself.py script itself is used only to create the archives from a directory of files.  The resultant archive is actually a compressed (using gzip or bzip2) TAR archive, with a small Python script stub at the beginning.  This small stub performs all the steps of extracting the files, running the embedded command, and removing the temporary files when it's all over.  All that the user has to do to install the software contained in such an archive is to "run" the archive, i.e python nice-software.py.

This code is intended to be as portable as possible and should run on any system with an installation of python2.7 or later.

As of version 1.0, PyMakeSelf has been tested on the following platforms:

Linux (all distributions)
FreeBSD
Windows7
MacOS X (Darwin)

Usage
=====

The syntax of makeself.py is the following:
makeself.py [args] archive_dir file_name label startup_script [script_args]

args are optional options for Makeself.  The available ones are:
--version : Prints the version number on stdout, then exits immediately

--gzip : Use gzip for compression (is the default on platforms on which gzip is commonly available, like Linux)

--bzip2 : Use bzip2 instead of gzip for better compression. The bzip2 command must be available in the command path. I recommend that you set the prefix to something like '.bz2.run' for the archive, so that potential users know that they'll need bzip2 to extract it.

--nocomp : Do not use any compression for the archive, which will then be an uncompressed TAR.

--notemp : The generated archive will not extract the files to a temporary directory, but in a new directory created in the current directory. This is better to distribute software packages that may extract and compile by themselves (i.e. launch the compilation through the embedded script).

--current : Files will be extracted to the current directory, instead of in a subdirectory. This option implies --notemp above.

--follow : Follow the symbolic links inside of the archive directory, i.e. store the files that are being pointed to instead of the links themselves.

--copy : Upon extraction, the archive will first extract itself to a temporary directory. The main application of this is to allow self-contained installers stored in a Makeself archive on a CD, when the installer program will later need to unmount the CD and allow a new one to be inserted. This prevents "Filesystem busy" errors for installers that span multiple CDs.

--nomd5 : Disable the creation of a MD5 checksum for the archive.  This speeds up the extraction process if integrity checking is not necessary.

archive_dir is the name of the directory that contains the files to be archived

file_name is the name of the archive to be created

label is an arbitrary text string describing the package.  It will be displayed while extracting the files.

startup_script is the command to be executed from within the directory of extracted files.  Thus, if you wish to execute a program contain in this directory, you must prefix your command with "./". For example, ./program will be fine.  The script_args are additionnal arguments for this command.

Here is an example, assuming the user has a package image stored in a /home/joe/mysoft, and he wants to generate a self-extracting package named install_mysoft.py, which will launch the "setup" script initially stored in /home/joe/mysoft :
makeself.py /home/joe/mysoft mysoft "Joe's Nice Software Package" ./setup

Here is also how I created the install_pymakeself.py archive which contains the Makeself distribution :
python makeself.py --notemp PyMakeSelf pymakeself "PyMakeSelf by Andrew Gillis" python ./setup.py

Archives generated with PyMakeSelf 1.0 can be passed the following arguments:

--keep : Prevent the files to be extracted in a temporary directory that will be removed after the embedded script's execution.  The files will then be extracted in the current working directory and will stay here until you remove them.

--verbose : Will prompt the user before executing the embedded command.

--target dir : Allows to extract the archive in an arbitrary place.

--confirm : Prompt the user for confirmation before running the embedded command.

--info : Print out general information about the archive (does not extract).

--lsm : Print out the LSM entry, if it is present.

--list : List the files in the archive.

--check : Check the archive for integrity using the embedded checksums.  Does not extract the archive.

--noexec : Do not run the embedded script after extraction.
Any subsequent arguments to the archive will be passed as additional arguments to the embedded command.  You should explicitly use the -- special command-line construct before any such options to make sure that PyMakeSelf will not try to interpret them.

Examples
========

Create an installer, named install_stuff, that runs setup.py:

  python -m pymakeself /storage/myfiles install_stuff setup.py

Create an installer that runs the accountutil.py tool (one of the modules in the pymakeself installtools) as the setup script, to create the "ajg" user account:

  python -m pymakeself ~/ajg_dot_files create_ajg accountutil \
  -c 'Andrew J. Gillis' -i install_files ajg

Specifying "accountutil" as the install script tells pymakeself to use the UNIX account creation tool, that is included with the pymakeself package.

Notice that the -i argument to accountutil.py specifies "install_files" instead of "ajg_dot_files".  This is because inside the package, the contents of the archive directory are copied into a directory name install_files.

License
=======

Makeself is covered by the GNU General Public License (GPL) version 2 and above.  Archives generated by Makeself does not have to be placed under this license, since the archive itself is merely data for Makeself.

Project Links
=============

 - Downloads: http://pypi.python.org/pypi/pymakeself
 - Documentation: https://bitbucket.org/agillis/pymakeself/wiki/Home
 - Project page: https://bitbucket.org/agillis/pymakeself
 - License: http://www.opensource.org/licenses/mit-license.php

Bugs and Issues
===============

http://bitbucket.org/agillis/pymakeself/issues/

Acknowledgements
================

This script was inspired by, and modeled after, makeself by Stephane Peter.

