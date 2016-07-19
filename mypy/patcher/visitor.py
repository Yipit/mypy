from mypy.visitor import NodeVisitor

from mypy.nodes import (
    MypyFile, TypeInfo, Node, AssignmentStmt, FuncDef, OverloadedFuncDef,
    ClassDef, Var, GDEF, MODULE_REF, FuncItem, Import,
    ImportFrom, ImportAll, Block, LDEF, NameExpr, MemberExpr,
    IndexExpr, TupleExpr, ListExpr, ExpressionStmt, ReturnStmt,
    RaiseStmt, AssertStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, IfStmt, TryStmt, WithStmt, DelStmt,
    GlobalDecl, SuperExpr, DictExpr, CallExpr, RefExpr, OpExpr, UnaryExpr,
    SliceExpr, CastExpr, RevealTypeExpr, TypeApplication, Context, SymbolTable,
    SymbolTableNode, BOUND_TVAR, UNBOUND_TVAR, ListComprehension, GeneratorExpr,
    FuncExpr, MDEF, FuncBase, Decorator, SetExpr, TypeVarExpr,
    StrExpr, BytesExpr, PrintStmt, ConditionalExpr, PromoteExpr,
    ComparisonExpr, StarExpr, ARG_POS, ARG_NAMED, MroError, type_aliases,
    YieldFromExpr, NamedTupleExpr, NonlocalDecl,
    SetComprehension, DictionaryComprehension, TYPE_ALIAS, TypeAliasExpr,
    YieldExpr, ExecStmt, Argument, BackquoteExpr, ImportBase, COVARIANT, CONTRAVARIANT,
    INVARIANT, UNBOUND_IMPORTED
)

from typing import (
    List, Dict, Set, Tuple, cast, Any, overload, TypeVar, Union, Optional, Callable
)

T = TypeVar('T')

from redbaron import RedBaron


class PatcherVisitor(NodeVisitor):
    def __init__(self, fpath, mod, red, tr):
        super(PatcherVisitor, self).__init__()
        self.file_path = fpath
        self.current_path = mod
        self.current_module = mod
        self.red = red
        self.current_module = None
        self.current_class = None
        self.last_decorators = []
        self.current_decorators = []

        self.imports = {}

        # locals
        self.local_scopes = [[]]

        self.tr = tr

    def is_local(self, name):
        for sc in range(len(self.local_scopes)-1, 0, -1):
            if name in self.local_scopes[sc]:
                return True
            for v in self.local_scopes[sc]:
                if hasattr(v, 'name') and v.name() == name:
                    return True
        return False

    def visit_mypy_file(self, o: 'mypy.nodes.MypyFile') -> T:
        for d in o.defs:
            d.accept(self)

    def visit_file(self, file_node: MypyFile, fnam: str) -> None:
        import pdb;pdb.set_trace()

    def visit_func_def(self, defn: FuncDef) -> None:
        prev_path = self.current_path
        self.current_path = self.current_path + "." + defn.name()

        prev_decorators = self.current_decorators
        self.current_decorators = self.last_decorators
        self.last_decorators = []

        # print('on', self.current_path, self.current_decorators)
        self.local_scopes.append([])
        for arg in defn.arguments:
            self.local_scopes[-1].append(arg.variable)

        self.tr.transform_func_def(self, defn, self.red)

        defn.body.accept(self)
        self.local_scopes.pop()
        self.current_path = prev_path
        self.current_decorators = prev_decorators

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> None:
        import pdb;pdb.set_trace()

    def visit_class_def(self, defn: ClassDef) -> None:
        prev_path = self.current_path
        self.current_path = defn.fullname
        self.local_scopes.append([])
        self.tr.transform_class_def(self, defn, self.red)
        defn.defs.accept(self)
        self.local_scopes.pop()
        self.current_path = prev_path

    def visit_import(self, i: Import) -> None:
        for origin, local in i.ids:
            if local is None:
                self.imports[origin] = origin
                self.tr.transform_import(self, origin, i, self.red)
            else:
                self.imports[local] = origin
                self.tr.transform_import(self, local, i, self.red)


    def visit_import_from(self, imp: ImportFrom) -> None:
        if imp.relative:
            if imp.id != '':
                curr = self.current_module + '.' + imp.id
            else:
                curr = self.current_module
            for origin, local in imp.names:
                if local is None:
                    self.imports[origin] = curr + '.' + origin
                    self.tr.transform_import_from(self, origin, imp, self.red)
                else:
                    self.imports[local] = curr + '.' + origin
                    self.tr.transform_import_from(self, local, imp, self.red)
        else:
            for origin, local in imp.names:
                if local is None:
                    self.imports[origin] = imp.id + '.' + origin
                    self.tr.transform_import_from(self, origin, imp, self.red)
                else:
                    self.imports[local] = imp.id + '.' + origin
                    self.tr.transform_import_from(self, local, imp, self.red)



    def visit_import_all(self, i: ImportAll) -> None:
        print("MYPY Warning: can't process import * at {}:{}".format(self.file_path, i.line))

    #
    # Statements
    #

    def visit_block(self, b: Block) -> None:
        for n in b.body:
            n.accept(self)

    def visit_block_maybe(self, b: Block) -> None:
        import pdb;pdb.set_trace()

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        for n in s.lvalues:
            self.local_scopes[-1].append(n.name)
        for n in s.lvalues:
            n.accept(self)
        s.rvalue.accept(self)

    def visit_decorator(self, dec: Decorator) -> None:
        self.tr.transform_decorator(self, dec, self.red)

        for d in dec.decorators:
            d.accept(self)

        self.last_decorators = [x.name for x in dec.decorators]

        dec.func.accept(self)

        self.last_decorators = []

    def visit_expression_stmt(self, st: ExpressionStmt) -> None:
        st.expr.accept(self)

    def visit_return_stmt(self, s: ReturnStmt) -> None:
        # # if expr is 'test3.v1.Pipe.foo()'
        # if expr.callee.expr.node.type.type.fullname() == 'test3.v1.Pipe' and expr.callee.name == 'foo':
        #     node = [n for n in red.find_all('AtomtrailersNode') if n.absolute_bounding_box.top_left.line == expr.line]
        #     assert len(node) == 1
        #     node = node[0]
        #     import pdb;pdb.set_trace()
        #     pass

        self.tr.transform_return_stmt(self, s, self.red)
        s.expr.accept(self)

    def visit_raise_stmt(self, s: RaiseStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_assert_stmt(self, s: AssertStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_while_stmt(self, s: WhileStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_for_stmt(self, s: ForStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_break_stmt(self, s: BreakStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_continue_stmt(self, s: ContinueStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_if_stmt(self, s: IfStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_try_stmt(self, s: TryStmt) -> None:
        import pdb;pdb.set_trace()

    def analyze_try_stmt(self, s: TryStmt, visitor: NodeVisitor,
                         add_global: bool = False) -> None:
        import pdb;pdb.set_trace()

    def visit_with_stmt(self, s: WithStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_del_stmt(self, s: DelStmt) -> None:
        import pdb;pdb.set_trace()

    def is_valid_del_target(self, s: Node) -> bool:
        import pdb;pdb.set_trace()

    def visit_global_decl(self, g: GlobalDecl) -> None:
        import pdb;pdb.set_trace()

    def visit_nonlocal_decl(self, d: NonlocalDecl) -> None:
        import pdb;pdb.set_trace()

    def visit_print_stmt(self, s: PrintStmt) -> None:
        import pdb;pdb.set_trace()

    def visit_exec_stmt(self, s: ExecStmt) -> None:
        import pdb;pdb.set_trace()

    #
    # Expressions
    #

    def visit_name_expr(self, expr: NameExpr) -> None:
        # this is only for references to global imports
        # for now, we assume no `import` statements are mande inside functions
        # in the target code
        if not self.is_local(expr.name) and expr.name in self.imports.keys():
            self.tr.transform_name(self, expr.name, expr, self.red)

    def visit_super_expr(self, expr: SuperExpr) -> None:
        import pdb;pdb.set_trace()

    def visit_tuple_expr(self, expr: TupleExpr) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_list_expr(self, expr: ListExpr) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_set_expr(self, expr: SetExpr) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_dict_expr(self, expr: DictExpr) -> None:
        for key, value in expr.items:
            key.accept(self)
            value.accept(self)

    def visit_star_expr(self, expr: StarExpr) -> None:
        expr.expr.accept(self)

    def visit_yield_from_expr(self, e: YieldFromExpr) -> None:
        if e.expr:
            e.expr.accept(self)

    def visit_call_expr(self, expr: CallExpr) -> None:
        self.tr.transform_call_expr(self, expr, self.red)
        expr.callee.accept(self)
        for a in expr.args:
            a.accept(self)


    def visit_member_expr(self, expr: MemberExpr) -> None:
        if isinstance(expr.expr, NameExpr):
            if not self.is_local(expr.expr.name) and expr.expr.name in self.imports.keys():
                self.tr.transform_member(self, expr.expr.name, expr.name, expr, self.red)
        base = expr.expr
        base.accept(self)

    def visit_op_expr(self, expr: OpExpr) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_comparison_expr(self, expr: ComparisonExpr) -> None:
        for operand in expr.operands:
            operand.accept(self)

    def visit_unary_expr(self, expr: UnaryExpr) -> None:
        expr.expr.accept(self)

    def visit_index_expr(self, expr: IndexExpr) -> None:
        expr.base.accept(self)
        expr.index.accept(self)

    def visit_slice_expr(self, expr: SliceExpr) -> None:
        if expr.begin_index:
            expr.begin_index.accept(self)
        if expr.end_index:
            expr.end_index.accept(self)
        if expr.stride:
            expr.stride.accept(self)

    def visit_cast_expr(self, expr: CastExpr) -> None:
        expr.expr.accept(self)

    def visit_reveal_type_expr(self, expr: RevealTypeExpr) -> None:
        expr.expr.accept(self)

    def visit_type_application(self, expr: TypeApplication) -> None:
        expr.expr.accept(self)

    def visit_list_comprehension(self, expr: ListComprehension) -> None:
        expr.generator.accept(self)

    def visit_set_comprehension(self, expr: SetComprehension) -> None:
        expr.generator.accept(self)

    def visit_dictionary_comprehension(self, expr: DictionaryComprehension) -> None:
        expr.key.accept(self)
        expr.value.accept(self)

    def visit_generator_expr(self, expr: GeneratorExpr) -> None:
        expr.left_expr.accept(self)

    def visit_func_expr(self, expr: FuncExpr) -> None:
        import pdb;pdb.set_trace()
        for arg in defn.arguments:
            if arg.initializer:
                arg.initializer.accept(self)
        for arg in defn.arguments:
            if arg.initialization_statement:
                lvalue = arg.initialization_statement.lvalues[0]
                lvalue.accept(self)

    def visit_conditional_expr(self, expr: ConditionalExpr) -> None:
        expr.if_expr.accept(self)
        expr.cond.accept(self)
        expr.else_expr.accept(self)


    def visit_backquote_expr(self, expr: BackquoteExpr) -> None:
        expr.expr.accept(self)

    def visit__promote_expr(self, expr: PromoteExpr) -> None:
        import pdb;pdb.set_trace()

    def visit_yield_expr(self, expr: YieldExpr) -> None:
        if expr.expr:
            expr.expr.accept(self)
