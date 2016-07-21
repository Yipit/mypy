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
    proc = subprocess.Popen(["mypy", '--check-untyped-defs', py_file, "-P", ypatch_file], stdout=subprocess.PIPE)
    out = proc.communicate()[0]
    with open(py_file, "r") as f:
        content = f.read()
    return out.decode('utf-8'), content


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
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:3 - foo\nWARNING {}:4 - foo\n'.format(py_file, py_file)


################# testing warnings #################

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
            output, _ = execute_mypy(py_file, ypatch_file)
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
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:4 - foo\nWARNING {}:5 - foo\n'.format(py_file, py_file)


def test_fqe_call_star_arg_warning():
    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
sys.exit(2, *args)
a = sys.exit
"""

    ypatch = """
on * sys.exit($x, *$y) warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:6 - foo\n'.format(py_file)


def test_fqe_call_double_star_arg_warning():
    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
sys.exit(2, *args)
sys.exit(*args, **kw)
sys.exit(2, *args, **kw)
a = sys.exit
"""

    ypatch = """
on * sys.exit($x, *$y, **$kw) warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:8 - foo\n'.format(py_file)


def test_typed_call_args_warning():
    code = """
class X(object):
    def foo(self):
        self.bar()
        self.baz()
        self.bar(1)
        self.bar(1,2)
        self.bar(1,2,3)
"""

    ypatch = """
on * [__main__.X].bar($x, $y) warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:7 - foo\n'.format(py_file)


def test_typed_call_varargs_warning():
    code = """
class X(object):
    def foo(self):
        self.bar()
        self.baz()
        self.bar(1)
        self.bar(1,2)
        self.bar(1,2,3)
"""

    ypatch = """
on * [__main__.X].bar($x, $y, ...) warn "foo";
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:7 - foo\nWARNING {}:8 - foo\n'.format(py_file, py_file)


################# testing substitutions #################


def test_fqe_subst_regular_import():
    code = """
import sys
sys.exit
foo.sys.exit
print( 1, \
    sys.exit)
print(sys.exit + nonsys.exit + sys.exiting)
def bar(sys):
    return sys.exit
def baz(x):
    return sys.exit
"""

    ypatch = """
on * sys.exit => new_exit;
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
import sys
sys.new_exit
foo.sys.exit
print( 1, \
    sys.new_exit)
print(sys.new_exit + nonsys.exit + sys.exiting)
def bar(sys):
    return sys.exit
def baz(x):
    return sys.new_exit
"""


def test_fqe_subst_import_as():
    code = """
import sys as foo
foo.exit
print( 1, \
    foo.exit)
print(foo.exit + nonfoo.exit + foo.exiting)
def bar(foo):
    return foo.exit
def baz(x):
    return foo.exit
"""

    ypatch = """
on * sys.exit => new_exit;
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
import sys as foo
foo.new_exit
print( 1, \
    foo.new_exit)
print(foo.new_exit + nonfoo.exit + foo.exiting)
def bar(foo):
    return foo.exit
def baz(x):
    return foo.new_exit
"""


def test_fqe_subst_import_from():
    code = """
from sys import exit
exit
print( 1, \
    exit + sys.exit)
print(sys.exit + nonsys.exit + sys.exiting + exit)
def bar(sys, exit):
    return sys.exit, exit
def baz(x):
    return sys.exit, exit
"""

    ypatch = """
on * sys.exit => new_exit;
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import new_exit
new_exit
print( 1, \
    new_exit + sys.exit)
print(sys.exit + nonsys.exit + sys.exiting + new_exit)
def bar(sys, exit):
    return sys.exit, exit
def baz(x):
    return sys.exit, new_exit
"""