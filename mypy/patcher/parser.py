from pymeta import builder, grammar
from pymeta.runtime import OMetaBase
from pymeta.builder import TreeBuilder, moduleFromGrammar
import os, sys
from types import ModuleType as module


class CodeRewritter(object):
    def transform_import(self, visitor, mypy_node, redbaron):
        pass

    def transform_func_def(self, visitor, mypy_node, redbaron):
        pass

    def transform_import(self, visitor, mypy_node, redbaron):
        pass

    def transform_import_from(self, visitor, mypy_node, redbaron):
        pass

    def transform_import_all(self, visitor, mypy_node, redbaron):
        pass

    def transform_return_stmt(self, visitor, mypy_node, redbaron):
        pass

    def transform_class_def(self, visitor, mypy_node, redbaron):
        pass

    def transform_decorator(self, visitor, mypy_node, redbaron):
        pass

    def transform_call_expr(self, visitor, mypy_node, redbaron):
        pass


class_template = """
class {name}(CodeRewritter):
{methods}
"""

transform_import_template = """
    def transform_import{suffix}(self, visitor, mypy_node, redbaron):
        red_node = redbaron.find_by_position((mypy_node.line,1))
        {action}
"""

warning_template = """print("WARNING " + visitor.file_path + ":" + str(mypy_node.line) + " - " + {message})"""

#  def transform_return_stmt(self, mypy_visitor, mypy_node, redb):
#      if 'app_filter' in mypy_visitor.current_decorators:
#          node = [n for n in redb.find_all('return') if n.absolute_bounding_box.top_left.line == mypy_node.line]
#          assert len(node) == 1
#          node = node[0]
#          import pdb;pdb.set_trace()
#          node.value = 'self ,' + str(node.value)

# def transform_return_stmt(self, mypy_visitor, mypy_node, redb):
#     pass

# def transform_call_expr(self, mypy_visitor, mypy_node, redb):
#     pass



class Generator(object):
    def __init__(self):
        self.methods = []
        modname = "_patcher"
        filename = "dummy"
        self.mod = module(modname)
        self.mod.__dict__['CodeRewritter'] = CodeRewritter


    def warning_for_fqe(self, _, msg):
        self.methods.append(transform_import_template.format(suffix='', action=warning_template.format(message=repr(msg))))
        self.methods.append(transform_import_template.format(suffix='_from', action=warning_template.format(message=repr(msg))))
        self.methods.append(transform_import_template.format(suffix='_all', action=warning_template.format(message=repr(msg))))

    def get_transformer(self):
        source = class_template.format(name="Transformer", methods='\n    '.join(self.methods))
        obj = compile(source, "<eval>", 'exec')
        eval(obj, self.mod.__dict__)
        return self.mod.Transformer()


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
        print(ast)
    parser = Parser([ast])
    parser.g = Generator()
    print(parser.apply("ast_start"))
    return parser.g.get_transformer()


# print(Parser('on * [sheqel.Sheqel].write_if_new => foo();').apply("start"))
# print(Parser('on * return($x) => foo();').apply("start"))
# print(Parser('return ($x, ...)').apply("return_pattern"))
# print(Parser('return (x)').apply("return_pattern"))
# print(Parser('on * return ([$x, $y]) => return (self, $y);').apply("start"))
