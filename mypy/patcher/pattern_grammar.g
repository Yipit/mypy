C = " #################### elementary rules ############################ "

letter_or_ = letter
           | "_"

letter_or_digit_or_ = letter_or_ | digit

quoted_string  = spaces '"' (lit_escaped | ~'"' :x)*:xs '"' -> ["string", ''.join(xs)]

lit_escaped = ~'"' '\\' :x -> "\\" + x

quoted_string_single  = spaces '\'' (lit_escaped_single | ~'\'' :x)*:xs '\'' -> ["string", ''.join(xs)]

lit_escaped_single = ~'\'' '\\' :x -> "\\" + x

py_name = spaces pyid:x ("." pyid:y -> "." + y)*:xs -> ''.join([x] + xs)

pyid = letter_or_:x letter_or_digit_or_*:xs -> ''.join([x] + xs)


C = " #################### patching rules ############################ "


start = stmt+:rs -> ["rules", rs]

stmt = spaces token("on") where:w pattern:p action:a token(";") -> ["rule", w, p, a]

where = token("*") -> "anywhere"
      | token("decorated by") decorator:d -> ["decorator", d]
      | token("subclass") py_name:s -> ["subclass", s]

decorator = token("@") py_name

pattern = typed_pattern
        | return_pattern
        | lhs_fully_qualified_call:e -> ['fqe_call', e]
        | fully_qualified_pattern:e -> ["fqe", e]

lhs_fully_qualified_call = py_name:id token("(") lhs_args:a token(")") -> ['call', id, a]

fully_qualified_pattern = py_name

typed_pattern = token("[") py_name:t token("].") lhs_method_call:c -> ['typed', t, c]
              | token("[") py_name:t token("].") attribute_ref:r  -> ['typed', t, r]

return_pattern = token("return") token("(") lhs_args:a token(")") -> ['return', a]

lhs_method_call = py_name:id token("(") lhs_args:a token(")") -> ['call', id, a]

attribute_ref = py_name

lhs_args = lhs_arg_el:x (token(",") lhs_arg_el)*:xs -> [x] + xs
         | -> []

lhs_arg_el = varargs_qualifier:q lhs_arg:x -> ['arg', q, x]
           | token("[") lhs_args:x  token("]") -> ['pylist', x]

varargs_qualifier = token("**")
                  | token("*")
                  |

lhs_arg = token("$") letter+:x -> ['vid', ''.join(x)]
        | py_name:x -> ['pyid', x]
        | token("...") -> 'arg_rest'

action = token("warn") quoted_string:s -> ["warning", s]
       | token("delete") -> ["delete"]
       | token("=>") rhs_method_call
       | token("=>") return_pattern
       | token("=>") spaces pyid:e -> ['pyid', e]

rhs_method_call = py_name:id token("(") rhs_args:a token(")") -> ['call', id, a]

rhs_args = rhs_arg_el:x (token(",") rhs_arg_el)*:xs -> [x] + xs
         | -> []

rhs_arg_el = varargs_qualifier:q rhs_arg:x -> ['arg', q, x]
           | token("[") rhs_args:x  token("]") -> ['pylist', x]

rhs_arg = token("$") letter+:x -> ['vid', ''.join(x)]
        | token("$") digit+:x -> ['vparam', ''.join(x)]
        | py_name:x -> ['pyid', x]
        | digit+:d -> ['number', ''.join(d)]
        | token("...") -> 'arg_rest'



C = " #################### ast rules ############################ "

ast_start = ['rules' [ast_rule+]]

ast_rule = ['rule' 'anywhere' ['fqe' :fqe] fqe_action(fqe)]
         | ['rule' 'anywhere' ['fqe_call' ['call' :fqe ast_lhs_args:a]] fqe_call_action(fqe, a)]
         | ['rule' 'anywhere' ['typed' :type ['call' :method ast_lhs_args:a]] typed_call_action(type, method, a)]


ast_lhs_args = [ast_lhs_arg*:a] -> a

ast_lhs_arg = ['arg' :qualifier 'arg_rest'] -> {'vararg': True, 'qualifier': qualifier}
            | ['arg' :qualifier ['vid' :name]] -> {'vararg': False, 'vid': name, 'qualifier': qualifier}


fqe_action :lfqe = ['warning' ['string' :msg]] -> self.g.warning_for_fqe(lfqe, msg)
                 | ['pyid' :pyid] -> self.g.subst_fqe(lfqe, pyid)

fqe_call_action :lfqe :la =  ['warning' ['string' :msg]] -> self.g.warning_for_fqe_call(lfqe[0], la, msg)
                          | ['call' :rfqe ast_rhs_args:ra] -> self.g.subst_fqe_call(lfqe[0], rfqe, la, ra)


typed_call_action :type :lm :la = ['warning' ['string' :msg]] -> self.g.warning_for_typed_call(type[0], lm[0], la, msg)
                                | ['call' :rfqe ast_rhs_args:ra] -> self.g.subst_for_typed_call(type[0], lm[0], la, rfqe, ra)

ast_rhs_args = [ast_rhs_arg*:a] -> a

ast_rhs_arg = ['arg' :qualifier 'arg_rest'] -> {'vararg': True, 'qualifier': qualifier}
            | ['arg' :qualifier ['vid' :name]] -> {'vararg': False, 'vid': name, 'qualifier': qualifier}
            | ['arg' :qualifier ['pyid' :name]] -> {'vararg': False, 'pyid': name, 'qualifier': qualifier}



C = " #################### python line parsing rules ############################ "
C = " format:  python_line(str_line, name, arity) => [(initial_pos, final_pos, [arg_str])] "
C = "                                                                   "
C = " example: python_line('sys.exit(a,b) exit(c) exit(d.e,f(1))', 'exit', 2) => [(22, 36, ['d.e','f(1)'])]"

python_line :name :arity :has_varg = python_line_term(name, arity, has_varg)

python_skip_element = spaces py_name  -> self.input.position-1
                    | spaces anything -> self.input.position

python_line_term :name :arity :has_varg = spaces !(self.input.position):p py_name:t ?(name[0] == t) python_line_sig:a
                                  !(print('match', t, a, ((not has_varg and arity[0] == len(a)) or (has_varg and (arity[0]-1) <= len(a)))))
                                  ?((not has_varg and arity[0] == len(a)) or (has_varg and (arity[0]-1) <= len(a))) -> [p, self.input.position, a]

python_line_sig = token("(") python_line_args:a token(")") -> a

python_line_args = python_line_arg:x (token(',') python_line_arg)*:xs -> [x]+xs
                 | -> [None]

python_line_arg = quoted_string:x -> repr(x[1])
   | quoted_string_single:x -> repr(x[1])
   | python_square_bracket_arg
   | python_curly_bracket_arg
   | python_paren_bracket_arg
   | (~(token('(') | token(')') | token('[') | token(']') | token('{') | token('}') | token(',')) anything:a -> a.strip())+:x python_line_sig:e -> ''.join(x) + '(' + ', '.join(e) + ')'
   | (~(token('(') | token(')') | token('[') | token(']') | token('{') | token('}') | token(',')) anything:a -> a.strip())+:x  -> ''.join(x)

python_square_bracket_arg = token('[') python_list_contents:a token(']') -> '[' + ', '.join(a) + ']'
python_list_contents = python_line_args

python_paren_bracket_arg = token('(') python_tuple_contents:a token(')') -> '(' + ', '.join(a) + ')'
python_tuple_contents = python_line_args


python_curly_bracket_arg = token('{') python_curly_contents:a token('}') -> '{' + ', '.join(a) + '}'
python_curly_contents = python_curly_content:x (token(",") python_curly_content)*:xs -> [x] + xs

python_curly_content = python_line_arg:a token(':') python_line_arg:b -> a + ': ' + b
                     | python_line_arg
