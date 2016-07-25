from pymeta import builder, grammar
from pymeta.runtime import OMetaBase, _MaybeParseError
from pymeta.builder import TreeBuilder, moduleFromGrammar
import os, sys
import re
from mypy.nodes import MemberExpr, NameExpr
from mypy.types import AnyType
from functools import partial
from token import OP
from .tokenizer import tokenize, untokenize
from io import BytesIO

pg = grammar.OMetaGrammar(open(os.path.join(os.path.dirname(__file__),"pattern_grammar.g")).read())
tree = pg.parseGrammar('Patcher', builder.TreeBuilder)
Parser = moduleFromGrammar(tree, 'Patcher', OMetaBase, {})


class CodeTransformer(object):
    def __init__(self):
        self.transformers = {'import': [], 'import_all': [], 'import_from': [], 'name': [], 'member': [], 'call': []}

    def transform_import(self, visitor, varname, mypy_node, source_lines):
        for tr in self.transformers['import']:
            tr(visitor, varname, mypy_node, source_lines)

    def transform_func_def(self, visitor, mypy_node, source_lines):
        pass

    def transform_import_from(self, visitor, varname, mypy_node, source_lines):
        for tr in self.transformers['import_from']:
            tr(visitor, varname, mypy_node, source_lines)

    def transform_import_all(self, visitor, mypy_node, source_lines):
        for tr in self.transformers['import_all']:
            tr(visitor, varname, mypy_node, source_lines)

    def transform_return_stmt(self, visitor, mypy_node, source_lines):
        pass

    def transform_class_def(self, visitor, mypy_node, source_lines):
        pass

    def transform_decorator(self, visitor, mypy_node, source_lines):
        pass

    def transform_call_expr(self, visitor, mypy_node, source_lines):
        for tr in self.transformers['call']:
            tr(visitor, mypy_node, source_lines)

    def transform_name(self, visitor, varname, mypy_node, source_lines):
        for tr in self.transformers['name']:
            tr(visitor, varname, mypy_node, source_lines)

    def transform_member(self, visitor, l, r, mypy_node, source_lines):
        for tr in self.transformers['member']:
            tr(visitor, l, r, mypy_node, source_lines)


## Actions functions
def warning_action(message, visitor, mypy_node, source_lines, *_):
    print("WARNING " + visitor.file_path + ":" + str(mypy_node.line) + " - " + message)


def _substitute_token(old_value, new_value, line):

    def tokens_match(old, tk):
        for idx, t in enumerate(old):
            if t.type != tk[idx].type or t.string != tk[idx].string:
                return False
        return True

    result = []
    tks = [t for t in tokenize(BytesIO(line.encode('utf-8')).readline)]
    old_tks = [t for t in tokenize(BytesIO(old_value.encode('utf-8')).readline)][1:-1]
    new_tks = [t for t in tokenize(BytesIO(new_value.encode('utf-8')).readline)][1:-1]

    idx = 0
    prev_is_dot = False
    while idx < len(tks):
        if not prev_is_dot and tokens_match(old_tks, tks[idx:]):
            result.extend([(tkn, tstr) for tkn, tstr, _, _, _ in new_tks])
            idx += len(old_tks)
            prev_is_dot = False
        else:
            result.append((tks[idx].type, tks[idx].string))
            if tks[idx].type == OP and tks[idx].string == '.':
                prev_is_dot = True
            else:
                prev_is_dot = False
            idx += 1

    return untokenize(result).decode('utf-8')



def _subst_call(visitor, mypy_node, lines, name, pyid, largs, rargs):
    has_var_arg = any([x['vararg'] for x in largs])
    line_offset = 0
    while True:
        parser = Parser(lines[line_offset:])
        try:
            res, err = parser.apply("python_line", name, len(largs), has_var_arg)
            break
        except _MaybeParseError:
            # skip an element of the input and try again
            Parser(lines[line_offset:])
            line_offset += parser.apply('python_skip_element')[0]
    begin, end, margs = res
    bound_args = {} # associate $K with values found in margs and the visitor.current_function_parameters
    for idx, a in enumerate(largs):
        if a['vararg']:
            bound_args['rest'] = margs[idx:]
        elif 'vid' in a:
            # the following check for keyword arg is very fishy, but seems safe
            if ('key' in a and '=' in margs[idx] and a['key'] == margs[idx].split('=')[0]):
                bound_args[a['vid']] = margs[idx].split('=')[1]
            elif 'key' not in a and '=' not in margs[idx]:
                bound_args[a['vid']] = margs[idx]
            else:
                return lines # failed to match kwarg, e.g. "foo(key=$x)" with "foo($x). ignore it
        else:
            raise Exception("?")
    res_args = []
    for idx, a in enumerate(rargs):
        if a['vararg']:
            res_args.extend(bound_args['rest'])
        elif 'vid' in a and a['vid'].isdigit():
            res_args.append(visitor.get_parameter(int(a['vid'])))
        elif 'vid' in a:
            if 'key' in a:
                res_args.append(a['key'] + '=' + bound_args[a['vid']])
            else:
                res_args.append(bound_args[a['vid']])
        else:
            raise Exception('?')
    return lines[0:begin+line_offset] + '{}({})'.format(pyid, ', '.join(res_args)) + lines[line_offset+end:]

##########################

def subst_member_fqe_action(lfqe, pyid, visitor, mypy_node, source_lines, l, r):
    full_name = l + '.' + r
    line = source_lines[mypy_node.line-1]
    source_lines[mypy_node.line-1] = _substitute_token(l + '.' + r, l + '.' + pyid, line)

def subst_name_fqe_action(lfqe, pyid, visitor, mypy_node, source_lines):
    name = lfqe.split('.')[-1]
    line = source_lines[mypy_node.line-1]
    source_lines[mypy_node.line-1] = _substitute_token(name, pyid, line)


def subst_call_action(lfqe, pyid, largs, rargs, visitor, mypy_node, source_lines, target_term):

    # if we are looking for "foo.bar", substitute it for "foo.<pyid>"
    if '.' in target_term:
        pyid = '.'.join(target_term.split('.')[:-1]) + '.' + pyid

    if len(largs) == 0 and len(rargs) == 0:
        # substitute the callee term
        # subst_name_fqe_action(lfqe, pyid, visitor, mypy_node, source_lines)
        # name = lfqe.split('.')[-1]
        line = source_lines[mypy_node.line-1]
        source_lines[mypy_node.line-1] = _substitute_token(target_term, pyid, line)
    else:
        lines = '\n'.join(source_lines[mypy_node.line-1:])
        new_lines = _subst_call(visitor, mypy_node, lines, target_term, pyid, largs, rargs)
        del source_lines[mypy_node.line-1:]
        for i, line in enumerate(new_lines.split('\n')):
            source_lines.append(line)

## stage 2 matching functions

def name_fqe_template(action, fqe, visitor, varname, mypy_node, source_lines):
    if not visitor.is_local(varname) and varname in visitor.imports.keys() and visitor.imports[varname] == fqe:
        action(visitor, mypy_node, source_lines)

def member_fqe_template(action, fqe, visitor, l, r, mypy_node, source_lines):
    full_name = visitor.imports[l] + '.' + r
    if not visitor.is_local(l) and l in visitor.imports.keys() and full_name == fqe:
        action(visitor, mypy_node, source_lines, l, r)


def call_template(action, fqe, min_arity, arity, visitor, mypy_node, source_lines, star_pos=None, star_star_pos=None):
    if isinstance(mypy_node.callee, MemberExpr) and hasattr(mypy_node.callee.expr, 'name'): # call in the format 'foo.bar()' -- e.g. not in (a+b).bar()
        local_name = str(mypy_node.callee.expr.name)
        callee = str(mypy_node.callee.name)
        full = local_name + '.' + callee

        node_star = [idx for idx, arg_kind in enumerate(mypy_node.arg_kinds) if arg_kind == 2]
        if node_star:
            node_star_pos = node_star[0]
        else:
            node_star_pos = None

        node_star_star = [idx for idx, arg_kind in enumerate(mypy_node.arg_kinds) if arg_kind == 4]
        if node_star_star:
            node_star_star_pos = node_star_star[0]
        else:
            node_star_star_pos = None

        if (not visitor.is_local(local_name)) and \
           local_name in visitor.imports.keys() and \
           full == fqe and \
           (len(mypy_node.args) == arity or len(mypy_node.args) >= min_arity) and\
           star_pos == node_star_pos and \
           star_star_pos == node_star_star_pos:
            action(visitor, mypy_node, source_lines, fqe)
    elif isinstance(mypy_node.callee, NameExpr): # call in the format 'foo()'
        local_name = str(mypy_node.callee.name)

        node_star = [idx for idx, arg_kind in enumerate(mypy_node.arg_kinds) if arg_kind == 2]
        if node_star:
            node_star_pos = node_star[0]
        else:
            node_star_pos = None

        node_star_star = [idx for idx, arg_kind in enumerate(mypy_node.arg_kinds) if arg_kind == 4]
        if node_star_star:
            node_star_star_pos = node_star_star[0]
        else:
            node_star_star_pos = None

        if (not visitor.is_local(local_name)) and \
           local_name in visitor.imports.keys() and \
           (len(mypy_node.args) == arity or len(mypy_node.args) >= min_arity) and\
           star_pos == node_star_pos and \
           star_star_pos == node_star_star_pos:
            action(visitor, mypy_node, source_lines, local_name)


def typed_call_template(action, ltype, method_name, min_arity, arity, visitor, mypy_node, source_lines):
    if isinstance(mypy_node.callee, MemberExpr) and hasattr(mypy_node.callee.expr, 'name'): # call in the format 'foo.bar()' -- e.g. not in (a+b).bar()
        rec_type = mypy_node.callee.expr.node.type
        if type(rec_type) == AnyType:
            rec_type_name = 'Any'
        else:
            rec_type_name = rec_type.type.fullname()

        callee = str(mypy_node.callee.name)
        if callee == method_name and \
           ltype == rec_type_name and \
           (len(mypy_node.args) == arity or len(mypy_node.args) >= min_arity):
            action(visitor, mypy_node, source_lines)




class Generator(object):
    def __init__(self):
        self.tr = CodeTransformer()

    def _add_method(self, name, f):
        self.tr.transformers[name].append(f)

    def warning_for_fqe(self, fqe, msg):
        warning_f = partial(warning_action, msg)
        self._add_method('import', partial(name_fqe_template, warning_f, fqe))
        self._add_method('import_from', partial(name_fqe_template, warning_f, fqe))
        self._add_method('import_all', partial(name_fqe_template, warning_f, fqe))
        self._add_method('name', partial(name_fqe_template, warning_f, fqe))
        self._add_method('member', partial(member_fqe_template, warning_f, fqe))

    def subst_fqe(self, fqe, pyid):
        self._add_method('import', partial(name_fqe_template, partial(subst_name_fqe_action, fqe, pyid), fqe))
        self._add_method('import_from', partial(name_fqe_template, partial(subst_name_fqe_action, fqe, pyid), fqe))
        self._add_method('import_all', partial(name_fqe_template, partial(subst_name_fqe_action, fqe, pyid), fqe))
        self._add_method('name', partial(name_fqe_template, partial(subst_name_fqe_action, fqe, pyid), fqe))
        self._add_method('member', partial(member_fqe_template, partial(subst_member_fqe_action, fqe, pyid), fqe))

    def warning_for_fqe_call(self, fqe, args, msg):
        warning_f = partial(warning_action, msg)

        star_args = [idx for idx, arg in enumerate(args) if arg['qualifier'] == '*']
        star_star_args = [idx for idx, arg in enumerate(args) if arg['qualifier'] == '**']
        if star_args:
            star_pos = star_args[0]
        else:
            star_pos = None

        if star_star_args:
            star_star_pos = star_star_args[0]
        else:
            star_star_pos = None

        if any([x['vararg'] for x in args]):
            # -1: don't count the vararg itself
            self._add_method('call', partial(call_template, warning_f, fqe, len(args)-1, len(args), star_pos=star_pos, star_star_pos=star_star_pos))
        else:
            self._add_method('call', partial(call_template, warning_f, fqe, float('+inf'), len(args), star_pos=star_pos, star_star_pos=star_star_pos))


    def warning_for_typed_call(self, ltype, method_name, args, msg):
        warning_f = partial(warning_action, msg)

        if any([x['vararg'] for x in args]):
            # -1: don't count the vararg itself
            self._add_method('call', partial(typed_call_template, warning_f, ltype, method_name, len(args)-1, len(args)))
        else:
            self._add_method('call', partial(typed_call_template, warning_f, ltype, method_name, float('+inf'), len(args)))


    def subst_fqe_call(self, lfqe, pyid, largs, rargs):
        star_args = [idx for idx, arg in enumerate(largs) if arg['qualifier'] == '*']
        star_star_args = [idx for idx, arg in enumerate(largs) if arg['qualifier'] == '**']
        if star_args:
            star_pos = star_args[0]
        else:
            star_pos = None

        if star_star_args:
            star_star_pos = star_star_args[0]
        else:
            star_star_pos = None

        subst_f = partial(subst_call_action, lfqe, pyid, largs, rargs)
        if any([x['vararg'] for x in largs]):
            # -1: don't count the vararg itself
            self._add_method('call', partial(call_template, subst_f, lfqe, len(largs)-1, len(largs), star_pos=star_pos, star_star_pos=star_star_pos))
        else:
            self._add_method('call', partial(call_template, subst_f, lfqe, float('+inf'), len(largs), star_pos=star_pos, star_star_pos=star_star_pos))


def get_transformer_for(ypatch_file):

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

if __name__ == '__main__':
    import sys
    print(repr(sys.argv[1]), repr(sys.argv[2]), int(sys.argv[3]))

    parser = Parser(sys.argv[1])
    print(parser.apply("python_line", sys.argv[2], int(sys.argv[3])))
