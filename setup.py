try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from pymakeself.makeself import __version__

# This is not zip_safe because the installer creation logic needs access to the
# raw source files in installtools/
#
def main():
    setup(
        name='pymakeself',
        version=__version__,
        author='Andrew Gillis',
        author_email='gillis.andrewj@gmail.com',
        url='https://github.com/gammmazero/pymakeself',
        description='pymakeself: make self-extracting archives',
        long_description = open('README.md').read(),
        license='http://www.opensource.org/licenses/mit-license.php',
        platforms=['unix', 'linux', 'osx', 'cygwin', 'win32'],
        keywords='archive installation tar',
        classifiers=['Development Status :: 3 - Alpha',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Operating System :: POSIX',
                     'Operating System :: MacOS :: MacOS X',
                     'Operating System :: Microsoft :: Windows',
                     'Topic :: Software Development :: Libraries',
                     'Topic :: Utilities',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 2.7',
                     'Programming Language :: Python :: 3'],
        packages=['pymakeself', 'pymakeself.installtools'],
        zip_safe=False,
        )


if __name__ == '__main__':
    main()
