import os
import sys
import tempfile
import shutil

dst_dir = os.path.join(tempfile.gettempdir(), 'pymakeselftest_installed')
os.mkdir(dst_dir)
for fname in ('foo.txt', 'bar.txt', 'baz.txt'):
    shutil.copyfile(fname, os.path.join(dst_dir, fname))

with open(os.path.join(dst_dir, 'params.txt'), 'w') as fout:
    fout.write(','.join(sys.argv[1:]))
