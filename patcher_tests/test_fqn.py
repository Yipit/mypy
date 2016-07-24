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
    ypatch = """
on * sys.exit warn "foo";
"""


    code = """
import sys
sys.exit(1)
a = sys.exit
"""
    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:3 - foo\nWARNING {}:4 - foo\n'.format(py_file, py_file)


################# testing warnings #################

def test_fqe_call_fixed_arg_warning():
    ypatch = """
on * sys.exit($x) warn "foo";
"""

    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
a = sys.exit
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:4 - foo\n'.format(py_file)


def test_fqe_call_var_arg_warning():
    ypatch = """
on * sys.exit($x, ...) warn "foo";
"""

    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
a = sys.exit
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:4 - foo\nWARNING {}:5 - foo\n'.format(py_file, py_file)


def test_fqe_call_star_arg_warning():
    ypatch = """
on * sys.exit($x, *$y) warn "foo";
"""

    code = """
import sys
sys.exit()
sys.exit(1)
sys.exit(1,2)
sys.exit(2, *args)
a = sys.exit
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:6 - foo\n'.format(py_file)


def test_fqe_call_double_star_arg_warning():
    ypatch = """
on * sys.exit($x, *$y, **$kw) warn "foo";
"""

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

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:8 - foo\n'.format(py_file)


def test_typed_call_args_warning():
    ypatch = """
on * [__main__.X].bar($x, $y) warn "foo";
"""

    code = """
class X(object):
    def foo(self):
        self.bar()
        self.baz()
        self.bar(1)
        self.bar(1,2)
        self.bar(1,2,3)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:7 - foo\n'.format(py_file)


def test_typed_call_varargs_warning():
    ypatch = """
on * [__main__.X].bar($x, $y, ...) warn "foo";
"""

    code = """
class X(object):
    def foo(self):
        self.bar()
        self.baz()
        self.bar(1)
        self.bar(1,2)
        self.bar(1,2,3)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            output, _ = execute_mypy(py_file, ypatch_file)
            assert output == 'WARNING {}:7 - foo\nWARNING {}:8 - foo\n'.format(py_file, py_file)


################# testing substitutions #################


def test_fqe_subst_regular_import():
    ypatch = """
on * sys.exit => new_exit;
"""

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
    ypatch = """
on * sys.exit => new_exit;
"""

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
    ypatch = """
on * sys.exit => new_exit;
"""

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


def test_fqe_call_subst_noargs():
    ypatch = """
on * sys.exit() => new_exit();
"""

    code = """
from sys import exit
a = exit
exit()
exit(1)
exit(1,2)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
new_exit()
exit(1)
exit(1,2)
"""

def test_fqe_call_subst_fully_qualified_name_noargs():
    ypatch = """
on * sys.exit() => sys.new_exit();
"""

    code = """
import sys
a = sys.exit
sys.exit()
sys.exit(1)
sys.exit(1,2)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
import sys
a = sys.exit
sys.new_exit()
sys.exit(1)
sys.exit(1,2)
"""

def test_fqe_call_subst_fully_qualified_name_with_args():
    ypatch = """
on * sys.exit($x, $y) => sys.new_exit($y, $x);
"""

    code = """
import sys
a = sys.exit
sys.exit()
sys.exit(1)
sys.exit(1, 2)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
import sys
a = sys.exit
sys.exit()
sys.exit(1)
sys.new_exit(2, 1)
"""

def test_fqe_call_subst_args_simple():
    ypatch = """
on * sys.exit($x, $y) => new_exit($y, $x);
"""

    code = """
from sys import exit
a = exit
exit()
exit(1)
exit(1, 2)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
exit()
exit(1)
new_exit(2, 1)
"""

def test_fqe_call_subst_args_with_calls():
    ypatch = """
on * sys.exit($x, $y, $z) => new_exit($z, $y, $x);
"""

    code = """
from sys import exit
a = exit
exit()
exit(f(g(self, "exit")), "foo", bar.baz)
exit(1,2)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
exit()
new_exit(bar.baz, 'foo', f(g(self, 'exit')))
exit(1,2)
"""

def test_fqe_call_many_substs_args_with_calls():
    ypatch = """
on * sys.exit($x, $y, $z) => new_exit($z, $y, $x);
"""

    code = """
from sys import exit
a = exit
exit()
exit(f(g(a,b)), exit(1,2,3), bar.baz)
exit(1,2)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
exit()
new_exit(bar.baz, new_exit(3, 2, 1), f(g(a, b)))
exit(1,2)
"""


def test_fqe_call_subst_spaning_many_lines_with_dict():
    ypatch = """
on * sys.exit($x, $y) => new_exit($y, $x);
"""

    code = """
from sys import exit
a = exit
exit()
exit({"a": 1,
      "b": 2},
       3, exit(a,b))
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
exit()
exit({"a": 1,
      "b": 2},
       3, new_exit(b, a))
"""


def test_fqe_call_subst_spaning_many_lines_with_nested_dict():
    ypatch = """
on * sys.exit($x, $y, $z) => new_exit($z, $x, $y);
"""

    code = """
from sys import exit
a = exit
exit()
exit({"a": 1,
      "b": {"c": 4, "d": 5}},
      2, 3)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
exit()
new_exit(3, {'a': 1, 'b': {'c': 4, 'd': 5}}, 2)
"""

def test_fqe_call_subst_spaning_many_lines_with_nested_list_dict_and_tuple():
    ypatch = """
on * sys.exit($x, $y, $z) => new_exit($z, $x, $y);
"""

    code = """
from sys import exit
a = exit
exit()
exit([k,"a", 1,
      "b", {"c": (4, 7, 8),
            "d": 5}],
      2, 3)
"""

    with using_tmp_file(code) as py_file:
        with using_tmp_file(ypatch) as ypatch_file:
            _, content = execute_mypy(py_file, ypatch_file)
            assert content == """
from sys import exit
a = exit
exit()
new_exit(3, [k, 'a', 1, 'b', {'c': (4, 7, 8), 'd': 5}], 2)
"""



# def test_fqe_call_subst_varargs():
#     ypatch = """
# on * sys.exit($x, ...) => new_exit($x, ...);
# """

#     code = """
# from sys import exit
# a = exit
# exit()
# exit(1)
# exit(1,2)
# """

#     with using_tmp_file(code) as py_file:
#         with using_tmp_file(ypatch) as ypatch_file:
#             output, _ = execute_mypy(py_file, ypatch_file)
#             assert content == """
# from sys import exit
# a = exit
# exit()
# new_exit(1)
# new_new_exit(2,1)
# """


## remaining tests

## on * [__main__.X].write($x, $y) => write($x, key=$y)
## on * [__main__.X].bar(z=$x) =>bar(k=$x);
## on * [__main__.X].bar($x) =>bar($x, $1);
## on * [__main__.X].bar(...) => bar2(...);
## on * [__main__.X].bar($x) delete;
## on * [__main__.X].write($x) => write(*$x);
## on [__main__.X].bar($m) => bar(*$m);
## on subclass __main__.X def foo(...) warn "foobar";
## on requirements +python-dateutil==1.5
## on * return $x => return $1, $x;

#### TODO
# - python calls may span many lines:
#    e.g.
#         foo(very_long_arg,
#             very_long_arg2)
#
#   We need to translate the entire box: just working on the single line of the node doesn't work.
#   -we may be able to do this by checking the .line of the arg nodes
#
