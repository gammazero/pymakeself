#
# Run with py.test
#
import os
import subprocess
import tempfile
import shutil

# Uncomment to import from repo instead of site-packages.
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from pymakeself import makeself


class TestSimpleInstall(object):

    @classmethod
    def setup_class(cls):
        cls.installer_name = 'installtestpymakeself.py'
        cls.dst_dir = os.path.join(tempfile.gettempdir(),
                                   'pymakeselftest_installed')
        cls.setup_args = ['squeemish', 'ossifrage', 'fortezza']

    @classmethod
    def teardown_class(cls):
        if os.path.isfile(cls.installer_name):
            try:
                os.unlink(cls.installer_name)
            except:
                pass
        if os.path.isdir(cls.dst_dir):
            shutil.rmtree(cls.dst_dir, True)

    def test_make_installer(self):
        """Test creating sefl-extracting installer."""
        label = 'This is a test of pymakeself.'
        compress='gz'
        password = None
        follow = False
        tools = False
        quiet = False
        sha256 = True
        install = []
        content = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'content')
        setup_script = 'install.py'
        setup_args = []

        exe_path = makeself.make_package(
            content, self.installer_name, setup_script, self.setup_args,
            sha256, compress, follow, tools, quiet, label, password)

        # Check that installer was created.
        assert os.path.isfile(exe_path)
        print('Created installer:', exe_path)

    def test_check_installer(self):
        """Test SHA256 check."""
        subprocess.check_call(('python3', self.installer_name, '--check'))

    def test_list_installer(self):
        """Test files list."""
        files = []
        kwargs = {}
        if sys.version_info.major >= 3:
            kwargs = {"text": True}
        o = subprocess.check_output(('python3', self.installer_name, '--list'),
                                    **kwargs)
        for line in o.split('\n'):
            if line and line[0] == '-':
                files.append(line.split()[-1])
        assert len(files) == 4
        assert 'foo.txt' in files
        assert 'bar.txt' in files
        assert 'baz.txt' in files
        assert 'install.py' in files

    def test_run_installer(self):
        """Test running installer."""
        # Run the installer.
        subprocess.check_call(('python3', self.installer_name,
                               "hello", "world", "--xyz"))
        print('Ran', self.installer_name)

        # Make sure all the expected files are in the install dir.
        assert os.path.isdir(self.dst_dir)
        for fname in ('foo.txt', 'bar.txt', 'baz.txt'):
            assert os.path.isfile(os.path.join(self.dst_dir, fname))
            data_ref = fname.split('.', 1)[0]
            with open(os.path.join(self.dst_dir, fname)) as fin:
                data = fin.read().strip()
                assert data == data_ref
        params_path = os.path.join(self.dst_dir, 'params.txt')
        assert os.path.isfile(params_path)
        print('All expected files are present.')

        # Make sure there are no extra files in install dir.
        assert len(list(os.listdir(self.dst_dir))) == 4, 'unexpected files'
        print('There are no unexpected files.')

        # Check that setup args were correctly received by installer.
        with open(params_path) as fin:
            params_data = fin.read().strip()
        assert params_data
        params = params_data.split(',')
        assert params == self.setup_args + ["hello", "world", "--xyz"]
        print('Setup arguments were correctly supplied to installer.')
