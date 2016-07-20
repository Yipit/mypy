letter_or_ = letter
           | "_"

letter_or_digit_or_ = letter_or_ | digit

py_name = spaces pyid:x ("." pyid:y -> "." + y)*:xs -> ''.join([x] + xs)

pyid = letter_or_:x letter_or_digit_or_*:xs -> ''.join([x] + xs)


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
        | token("...") -> 'arg_rest'


quoted_string  = spaces '"' (lit_escaped | ~'"' :x)*:xs '"' -> ["string", ''.join(xs)]

lit_escaped = ~'"' '\\' :x -> "\\" + x



ast_start = ['rules' [ast_rule+]]

ast_rule = ['rule' 'anywhere' ['fqe' :fqe] fqe_action(fqe)]
         | ['rule' 'anywhere' ['fqe_call' ['call' :fqe ast_lhs_args:a]] fqe_call_action(fqe, a)]
         | ['rule' 'anywhere' ['typed' :type ['call' :method ast_lhs_args:a]] ['warning' ['string' :msg]]] -> self.g.warning_for_typed_call(type, method, a, msg)

ast_lhs_args = [ast_lhs_arg*:a] -> a

ast_lhs_arg = ['arg' :qualifier 'arg_rest'] -> {'vararg': True, 'qualifier': qualifier}
            | ['arg' :qualifier ['vid' :name]] -> {'vararg': False, 'vid': name, 'qualifier': qualifier}


fqe_action :lfqe = ['warning' ['string' :msg]] -> self.g.warning_for_fqe(lfqe, msg)
                 | ['pyid' :pyid] -> self.g.subst_fqe(lfqe, pyid)

fqe_call_action :lfqe :la =  ['warning' ['string' :msg]] -> self.g.warning_for_fqe_call(lfqe[0], la, msg)
                          | ['call' :rfqe ast_rhs_args:ra] -> self.g.subst_fqe_call(lfqe[0], rfqe, la, ra)

ast_rhs_args = [ast_rhs_arg*:a] -> a

ast_rhs_arg = ['arg' :qualifier 'arg_rest'] -> {'vararg': True, 'qualifier': qualifier}
            | ['arg' :qualifier ['vid' :name]] -> {'vararg': False, 'vid': name, 'qualifier': qualifier}
            | ['arg' :qualifier ['pyid' :name]] -> {'vararg': False, 'pyid': name, 'qualifier': qualifier}
