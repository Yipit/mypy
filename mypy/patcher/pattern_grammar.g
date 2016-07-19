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
        | fully_qualified_pattern:e -> ["fqe", e]

fully_qualified_pattern = py_name

typed_pattern = token("[") py_name:t token("].") method_call:c -> ['typed', t, c]
              | token("[") py_name:t token("].") attribute_ref:r  -> ['typed', t, r]

return_pattern = token("return") token("(") args:a token(")") -> ['return', a]

method_call = py_name:id token("(") args:a token(")") -> ['call', id, a]

attribute_ref = py_name

args = arg_el:x (token(",") arg_el)*:xs -> [x] + xs
    | -> []

arg_el = varargs_qualifier:q arg:x -> ['arg', q, x]
       | token("[") args:x  token("]") -> ['pylist', x]

varargs_qualifier = "**" -> 'py_kwarg'
                  | "*" -> 'py_args'
                  |

arg = token("$") letter+:x -> ['vid', ''.join(x)]
    | token("$") digit+:x -> ['vparam', ''.join(x)]
    | py_name:x -> ['pyid', x]
    | token("...") -> 'arg_rest'

action = token("warn") quoted_string:s -> ["warning", s]
       | token("delete") -> ["delete"]
       | token("=>") method_call
       | token("=>") return_pattern


quoted_string  = spaces '"' (lit_escaped | ~'"' :x)*:xs '"' -> ["string", ''.join(xs)]

lit_escaped = ~'"' '\\' :x -> "\\" + x



ast_start = ['rules' [ast_rule+]]

ast_rule = ['rule' 'anywhere' ['fqe' :x] ['warning' ['string' :msg]]] -> self.g.warning_for_fqe(x, msg)

