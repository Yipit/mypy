import subprocess
import tempfile
import os
from contextlib import contextmanager


# for idx in xrange(1024 + 1):
#     outfd, outsock_path = tempfile.mkstemp()
#     outsock = os.fdopen(outfd,'w')
#     outsock.close()

@contextmanager
def using_tmp_file(source):
    fd, path = tempfile.mkstemp()
    try:
        s = os.fdopen(fd,'w')
        s.write(source)
        s.close()
        yield path
    finally:
        os.remove(path)

def execute_mypy(py_file, ypatch_file):
    proc = subprocess.Popen(["mypy", py_file, "-P", ypatch_file], stdout=subprocess.PIPE)
    out = proc.communicate()[0]
    return out.decode('utf-8')


def test_fqe_warning():
    code = """
import sys
sys.exit(1)
a = sys.exit
"""

    ypatch = """
on * sys.exit warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:3 - foo\nWARNING {}:4 - foo\n'.format(py_file, py_file)


def test_fqe_call_fixed_arg_warning():
    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
a = sys.exit
"""

    ypatch = """
on * sys.exit($x) warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:4 - foo\n'.format(py_file)


def test_fqe_call_var_arg_warning():
    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
a = sys.exit
"""

    ypatch = """
on * sys.exit($x, ...) warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:4 - foo\nWARNING {}:5 - foo\n'.format(py_file, py_file)
