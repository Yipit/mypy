from pymeta import builder, grammar
from pymeta.runtime import OMetaBase
from pymeta.builder import TreeBuilder, moduleFromGrammar
import os, sys
from mypy.nodes import MemberExpr
import functools


class CodeTransformer(object):
    def __init__(self):
        self.transformers = {'import': [], 'import_all': [], 'import_from': [], 'name': [], 'member': [], 'call': []}

    def transform_import(self, visitor, varname, mypy_node, redbaron):
        for tr in self.transformers['import']:
            tr(visitor, varname, mypy_node, redbaron)

    def transform_func_def(self, visitor, mypy_node, redbaron):
        pass

    def transform_import_from(self, visitor, varname, mypy_node, redbaron):
        for tr in self.transformers['import_from']:
            tr(visitor, varname, mypy_node, redbaron)

    def transform_import_all(self, visitor, mypy_node, redbaron):
        for tr in self.transformers['import_all']:
            tr(visitor, varname, mypy_node, redbaron)

    def transform_return_stmt(self, visitor, mypy_node, redbaron):
        pass

    def transform_class_def(self, visitor, mypy_node, redbaron):
        pass

    def transform_decorator(self, visitor, mypy_node, redbaron):
        pass

    def transform_call_expr(self, visitor, mypy_node, redbaron):
        for tr in self.transformers['call']:
            tr(visitor, mypy_node, redbaron)

    def transform_name(self, visitor, varname, mypy_node, redbaron):
        for tr in self.transformers['name']:
            tr(visitor, varname, mypy_node, redbaron)

    def transform_member(self, visitor, l, r, mypy_node, redbaron):
        for tr in self.transformers['member']:
            tr(visitor, l, r, mypy_node, redbaron)


def warn_name_fqe_template(fqe, message, visitor, varname, mypy_node, redbaron):
    if not visitor.is_local(varname) and varname in visitor.imports.keys() and visitor.imports[varname] == fqe:
        red_node = redbaron.find_by_position((mypy_node.line,1))
        print("WARNING " + visitor.file_path + ":" + str(mypy_node.line) + " - " + message)


def warn_member_fqe_template(fqe, message, visitor, l, r, mypy_node, redbaron):
    if not visitor.is_local(l) and l in visitor.imports.keys() and (visitor.imports[l] + '.' + r) == fqe:
        red_node = redbaron.find_by_position((mypy_node.line,1))
        print("WARNING " + visitor.file_path + ":" + str(mypy_node.line) + " - " + message)


def warn_call_template(fqe, message, min_arity, arity, visitor, mypy_node, redbaron):
    if isinstance(mypy_node.callee, MemberExpr) and hasattr(mypy_node.callee.expr, 'name'): # call in the format 'foo.bar()' -- e.g. not in (a+b).bar()
        local_name = str(mypy_node.callee.expr.name)
        callee = str(mypy_node.callee.name)
        full = local_name + '.' + callee
        if (not visitor.is_local(local_name)) and \
           local_name in visitor.imports.keys() and \
           full == fqe and \
           (len(mypy_node.args) == arity or len(mypy_node.args) >= min_arity):
            red_node = redbaron.find_by_position((mypy_node.line,1))
            print("WARNING " + visitor.file_path + ":" + str(mypy_node.line) + " - " + message)


class Generator(object):
    def __init__(self):
        self.tr = CodeTransformer()

    def _add_method(self, name, f):
        self.tr.transformers[name].append(f)

    def warning_for_fqe(self, fqe, msg):
        self._add_method('import', functools.partial(warn_name_fqe_template, fqe, msg))
        self._add_method('import_from', functools.partial(warn_name_fqe_template, fqe, msg))
        self._add_method('import_all', functools.partial(warn_name_fqe_template, fqe, msg))
        self._add_method('name', functools.partial(warn_name_fqe_template, fqe, msg))
        self._add_method('member', functools.partial(warn_member_fqe_template, fqe, msg))

    def warning_for_fqe_call(self, fqe, args, msg):
        if any([x['vararg'] for x in args]):
            self._add_method('call', functools.partial(warn_call_template, fqe, msg, len(args)-1, len(args))) # -1: don't count the vararg itself
        else:
            self._add_method('call', functools.partial(warn_call_template, fqe, msg, float('+inf'), len(args)))


def get_transformer_for(ypatch_file):
    pg = grammar.OMetaGrammar(open(os.path.join(os.path.dirname(__file__),"pattern_grammar.g")).read())
    tree = pg.parseGrammar('Patcher', builder.TreeBuilder)
    Parser = moduleFromGrammar(tree, 'Patcher', OMetaBase, {})

    ## debugging pymeta output
    # fp = open(os.path.join(os.path.dirname(__file__), 'compiled.py'), 'w')
    # ometa_grammar = grammar.OMetaGrammar(open(os.path.join(os.path.dirname(__file__),"pattern_grammar.g")).read())
    # tree = ometa_grammar.parseGrammar('Patcher', builder.TreeBuilder)
    # fp.write(builder.writeBoot(tree))
    ###
    with open(ypatch_file) as f:
        parser = Parser(f.read())
        ast, err = parser.apply("start")
        # print(ast)
    parser = Parser([ast])
    parser.g = Generator()
    ast, err = parser.apply("ast_start")
    # print(ast, err)
    return parser.g.tr
