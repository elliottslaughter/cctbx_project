import sys

from operator_functor_info import *
from generate_af_std_imports import *

def write_copyright():
  print \
"""/* Copyright (c) 2001 The Regents of the University of California through
   E.O. Lawrence Berkeley National Laboratory, subject to approval by the
   U.S. Department of Energy. See files COPYRIGHT.txt and
   cctbx/LICENSE.txt for further details.

   Revision history:
     Jan 2002: Created (Ralf W. Grosse-Kunstleve)

   *****************************************************
   THIS IS AN AUTOMATICALLY GENERATED FILE. DO NOT EDIT.
   *****************************************************

   Generated by:
     %s
 */""" % (sys.argv[0],)

misc_functions_2arg = (
  (["approx_equal_scaled"], 1,
   ["const ElementType& scaled_tolerance", "scaled_tolerance"]),
  (["approx_equal_unscaled"], 1,
   ["const ElementType& tolerance", "tolerance"]),
)

reduction_functions_1arg = (
  "max_index", "min_index",
  "max", "min",
  "sum", "product",
  "mean",
)
reduction_functions_2arg = (
  "weighted_mean",
)

class empty: pass

def format_header(indent, str, max_line_length = 79):
  maxlen = max_line_length - len(indent)
  extra_indent = ""
  lei = len(extra_indent)
  result = ""
  rest = str.strip()
  while (lei + len(rest) > maxlen):
    if (lei == 0):
      i = rest.index("<")
    else:
      i = rest.index(",")
      try: i += rest[i+1:].index(",") + 1
      except: pass
    result += indent + extra_indent + rest[:i+1] + '\n'
    extra_indent = "  "
    lei = 2
    rest = rest[i+1:].strip()
  result += indent + extra_indent + rest
  return result

def format_list(indent, list):
  r = ""
  for line in list[:-1]:
    r += indent + line + "\n"
  return r + indent + list[-1]

def get_template_args(array_type_name):
  result = [["typename", "ElementType"]]
  if (array_type_name in ("tiny", "small")):
    result.append(["std::size_t", "N"])
  elif (array_type_name in ("ref", "versa")):
    result.append(["typename", "AccessorType"])
  return result

def get_numbered_template_args(array_type_name, n_params, equal_element_type):
  single = get_template_args(array_type_name)
  if (n_params == 1): return [single]
  result = []
  for i in xrange(1, n_params+1):
    if (equal_element_type):
      single_numbered = [single[0]]
    else:
      single_numbered = [[single[0][0], single[0][1]+str(i)]]
    if (array_type_name == "tiny"):
      single_numbered.append(single[1])
    else:
      for s in single[1:]:
        single_numbered.append([s[0], s[1]+str(i)])
    result.append(single_numbered)
  return result

def get_template_header_args(numbered_template_args):
  result = []
  for p in numbered_template_args:
    for d in p:
      if (not d in result): result.append(d)
  return result

def get_template_parameter_args(numbered_template_args):
  from string import join
  result = []
  for p in numbered_template_args:
    result.append(join([d[1] for d in p], ", "))
  return result

def get_template_header(numbered_template_args):
  from string import join
  ha = get_template_header_args(numbered_template_args)
  result = "template<" + join([join(x) for x in ha], ", ") + ">"
  return result

def get_template_parameters(array_type_name, template_parameter_args):
  result = []
  for p in template_parameter_args:
    result.append(array_type_name + "<" + p + ">")
  return result

def get_template_header_and_parameters(
  array_type_name, n_params, equal_element_type = 0
):
  result = empty()
  result.nta = get_numbered_template_args(
    array_type_name, n_params, equal_element_type)
  result.tpa = get_template_parameter_args(result.nta)
  result.header = get_template_header(result.nta)
  result.params = get_template_parameters(array_type_name, result.tpa)
  return result

def derive_return_array_type_simple(param):
  if (not param.startswith("small")): return param
  return param.replace("N1", "(N1<N2?N1:N2)")

def wrap_element_type(array_type_name, element_type, addl):
  from string import join
  r = array_type_name + "<" + join([element_type] + addl, ", ") + ">"
  if (r.endswith(">>")): return r[:-1] + " >"
  return r

def special_decl_params(array_type_name, special_def):
  r = empty()
  r.return_elment_type = special_def[0]
  r.function_name = special_def[1]
  r.arg_element_types = special_def[2:]
  r.nta = get_numbered_template_args(array_type_name, 1, 0)
  addl = []
  if (len(r.nta[0]) == 2): addl = [r.nta[0][1][1]]
  r.header = get_template_header(r.nta)
  r.return_array_type = wrap_element_type(
    array_type_name, r.return_elment_type, addl)
  r.arg_array_types = []
  for aet in r.arg_element_types:
    r.arg_array_types.append(wrap_element_type(
      array_type_name, aet, addl))
  r.false_or_true_type_selector = (
    "has_trivial_destructor<%s >::value()" % (special_def[0],))
  if (array_type_name == "tiny"):
    r.false_or_true_type_selector = "true_type()"
  return r

def operator_decl_params(array_type_name, op_type, op_class, type_flags,
  equal_element_type = 0
):
  if (type_flags != (1,1)):
    r = get_template_header_and_parameters(array_type_name, 1,
      equal_element_type)
    r.params.insert(type_flags[0], "ElementType")
    r.return_element_type = ["ElementType"]
    if (op_type == "unary"):
      r.return_element_type = [
        "typename unary_operator_traits<",
        "  ElementType>::" + op_class]
    elif (op_class == "boolean"):
      r.return_element_type = [
        "typename binary_operator_traits<",
        "  ElementType, ElementType>::" + op_class]
  else:
    r = get_template_header_and_parameters(
      array_type_name, 2, equal_element_type)
    r.return_element_type = [r.nta[0][0][1]]
    if (op_class != "n/a"):
      r.return_element_type = [
        "typename binary_operator_traits<",
        "  ElementType1, ElementType2>::" + op_class]
  if (len(r.return_element_type) == 1):
    r.return_array_type = [array_type_name + "<" + r.return_element_type[0]]
  else:
    r.return_array_type = [
      array_type_name + "<",
      "  " + r.return_element_type[0],
      "    " + r.return_element_type[1]]
  if (len(r.nta[0]) == 2):
    if (r.nta[0][1][1] == "N1"):
      r.return_array_type[-1] += ", (N1<N2?N1:N2)"
    else:
      r.return_array_type[-1] += ", " + r.nta[0][1][1]
  r.return_array_type[-1] += ">"
  r.typedef_return_array_type = (["typedef " +  r.return_array_type[0]]
    + r.return_array_type[1:])
  r.false_or_true_type_selector = (
    "has_trivial_destructor<return_element_type>::value()")
  if (array_type_name == "tiny"):
    r.false_or_true_type_selector = "true_type()"
  r.element_types = ["ElementType", "ElementType"]
  if (type_flags == (1,1)):
    r.element_types = ["ElementType1", "ElementType2"]
  return r

def get_result_constructor_args(array_type_name, type_flags = None):
  arg_name = "a"
  if (type_flags != None): arg_name = "a%d" % ((type_flags[0] + 1) % 2 + 1,)
  if (array_type_name == "tiny"): return ""
  if (array_type_name == "versa"):
    return "(%s.accessor(), reserve_flag())" % (arg_name,)
  return "(%s.size(), reserve_flag())" % (arg_name,)

def binary_operator_algo_params(array_type_name, type_flags):
  r = empty()
  r.loop_n = "N"
  r.size_assert = ""
  r.result_constructor_args = ""
  r.set_size_back_door = ""
  if (array_type_name != "tiny"):
    r.loop_n = "a%d.size()" % ((type_flags[0] + 1) % 2 + 1,)
    if (type_flags == (1,1)):
      r.size_assert = """if (a1.size() != a2.size()) throw_range_error();
    """
    r.result_constructor_args = get_result_constructor_args(
      array_type_name, type_flags)
    r.set_size_back_door = """result.set_size_back_door(%s);
    """ % (r.loop_n,)
  r.begin = ["", ""]
  for i in xrange(2):
    if (type_flags[i]): r.begin[i] = ".begin()"
  r.type_flags_code = "sa"[type_flags[0]] + "_" + "sa"[type_flags[1]]
  return r

def set_size_back_door(array_type_name):
  if (array_type_name == "tiny"): return ""
  return """result.set_size_back_door(a.size());
    """

def generate_unary_ops(array_type_name):
  result_constructor_args = get_result_constructor_args(array_type_name)
  for op_class, op_symbol in (("arithmetic", "-"),
                              ("logical", "!")):
    d = operator_decl_params(array_type_name, "unary", op_class, (1,0))
    print """%s
  inline
%s
  operator%s(const %s& a) {
%s
    result_array_type;
    typedef typename result_array_type::value_type return_element_type;
    result_array_type result%s;
    array_operation_unary(functor_%s<
        return_element_type,
        ElementType>(),
      a.begin(), result.begin(), a.size(),
      %s);
    %sreturn result;
  }
""" % (format_header("  ", d.header),
       format_list("  ", d.return_array_type),
       op_symbol, d.params[0],
       format_list("    ", d.typedef_return_array_type),
       result_constructor_args,
       unary_functors[op_symbol],
       d.false_or_true_type_selector,
       set_size_back_door(array_type_name))

def elementwise_binary_op(
      array_type_name, op_class, op_symbol, type_flags, function_name):
  d = operator_decl_params(array_type_name, "binary", op_class, type_flags)
  a = binary_operator_algo_params(array_type_name, type_flags)
  print """%s
  inline
%s
  %s(
    const %s& a1,
    const %s& a2) {
%s
    result_array_type;
    typedef typename result_array_type::value_type return_element_type;
    %sresult_array_type result%s;
    array_operation_binary_%s(functor_%s<
        return_element_type,
        %s,
        %s>(),
      a1%s, a2%s, result.begin(), %s,
      %s);
    %sreturn result;
  }
""" % (format_header("  ", d.header),
       format_list("  ", d.return_array_type),
       function_name, d.params[0], d.params[1],
       format_list("    ", d.typedef_return_array_type),
       a.size_assert,
       a.result_constructor_args,
       a.type_flags_code,
       binary_functors[op_symbol], d.element_types[0], d.element_types[1],
       a.begin[0], a.begin[1], a.loop_n,
       d.false_or_true_type_selector,
       a.set_size_back_door)

def elementwise_inplace_binary_op(
      array_type_name, op_class, op_symbol, type_flags):
  d = operator_decl_params(array_type_name, "binary", "n/a", type_flags)
  a = binary_operator_algo_params(array_type_name, type_flags)
  print """%s
  inline
  %s&
  operator%s(
    %s& a1,
    const %s& a2) {
    %sarray_operation_in_place_binary(functor_%s<
        %s,
        %s>(),
      a1.begin(), a2%s, %s);
    return a1;
  }
""" % (format_header("  ", d.header),
       d.params[0],
       op_symbol, d.params[0], d.params[1],
       a.size_assert,
       in_place_binary_functors[op_symbol],
       d.return_element_type[0],
       d.element_types[1],
       a.begin[1], a.loop_n);

def generate_elementwise_binary_op(
      array_type_name, op_class, op_symbol, function_name = None):
  if (function_name == None):
    function_name = "operator" + op_symbol
  for type_flags in ((1,1), (1,0), (0,1)):
    elementwise_binary_op(
      array_type_name, op_class, op_symbol, type_flags, function_name)

def generate_elementwise_inplace_binary_op(
      array_type_name, op_class, op_symbol):
  for type_flags in ((1,1), (1,0)):
    elementwise_inplace_binary_op(
      array_type_name, op_class, op_symbol, type_flags)

def reducing_boolean_op(array_type_name, op_symbol, type_flags):
  d = operator_decl_params(array_type_name, "binary", "boolean", type_flags)
  a = binary_operator_algo_params(array_type_name, type_flags)
  op_group_tags = {
    "==": "",
    "!=": "_not_equal_to",
    ">":  "_greater_less",
    "<":  "_greater_less",
    ">=": "",
    "<=": "",
  }
  print """%s
  inline
%s
  operator%s(
    const %s& a1,
    const %s& a2) {
    %sreturn array_operation_reducing_boolean%s(functor_%s<
%s,
        %s,
        %s>(),
      a1%s, a2%s, %s);
  }
""" % (format_header("  ", d.header),
       format_list("  ", d.return_element_type),
       op_symbol, d.params[0], d.params[1],
       a.size_assert,
       op_group_tags[op_symbol],
       binary_functors[op_symbol],
       format_list("        ", d.return_element_type),
       d.element_types[0], d.element_types[1],
       a.begin[0], a.begin[1], a.loop_n)

def generate_reducing_boolean_op(array_type_name, op_symbol):
  for type_flags in ((1,1), (1,0), (0,1)):
    reducing_boolean_op(array_type_name, op_symbol, type_flags)

def generate_1arg_reductions(array_type_name):
  hp = get_template_header_and_parameters(array_type_name, 1)
  for function_name in reduction_functions_1arg:
    print """%s
  inline
  ElementType
  %s(const %s& a) {
    return %s(a.const_ref());
  }
""" % (format_header("  ", hp.header),
       function_name, hp.params[0],
       function_name)

def generate_2arg_reductions(array_type_name):
  hp = get_template_header_and_parameters(array_type_name, 2)
  for function_name in reduction_functions_2arg:
    print """%s
  inline
  ElementType1
  %s(
    const %s& a1,
    const %s& a2) {
    return %s(a1.const_ref(), a2.const_ref());
  }
""" % (format_header("  ", hp.header),
       function_name, hp.params[0], hp.params[1],
       function_name)

def generate_1arg_element_wise(array_type_name, function_names):
  result_constructor_args = get_result_constructor_args(array_type_name)
  d = operator_decl_params(array_type_name, "unary", "arithmetic", (1,0))
  for function_name in function_names:
    print """%s
  inline
%s
  %s(const %s& a) {
%s
    result_array_type;
    typedef typename result_array_type::value_type return_element_type;
    result_array_type result%s;
    array_operation_unary(functor_%s<return_element_type, ElementType>(),
      a.begin(), result.begin(), a.size(),
      %s);
    %sreturn result;
  }
""" % (format_header("  ", d.header),
       format_list("  ", d.return_array_type),
       function_name, d.params[0],
       format_list("    ", d.typedef_return_array_type),
       result_constructor_args,
       function_name,
       d.false_or_true_type_selector,
       set_size_back_door(array_type_name))

def generate_2arg_element_wise(
  array_type_name, function_names,
  equal_element_type = 0
):
  for function_name in function_names:
    for type_flags in ((1,1), (1,0), (0,1)):
      d = operator_decl_params(
        array_type_name, "binary", "n/a", type_flags, equal_element_type)
      a = binary_operator_algo_params(array_type_name, type_flags)
      print """%s
  inline
%s
  %s(
    const %s& a1,
    const %s& a2) {
%s
    result_array_type;
    typedef typename result_array_type::value_type return_element_type;
    %sresult_array_type result%s;
    array_operation_binary_%s(functor_%s<
        return_element_type, %s, %s>(),
      a1%s, a2%s, result.begin(), %s,
      %s);
    %sreturn result;
  }
""" % (format_header("  ", d.header),
       format_list("  ", d.return_array_type),
       function_name, d.params[0], d.params[1],
       format_list("    ", d.typedef_return_array_type),
       a.size_assert,
       a.result_constructor_args,
       a.type_flags_code,
       function_name, d.element_types[0], d.element_types[1],
       a.begin[0], a.begin[1], a.loop_n,
       d.false_or_true_type_selector,
       a.set_size_back_door)

def generate_2arg_addl_element_wise(
  array_type_name, function_names,
  equal_element_type,
  addl_args
):
  for function_name in function_names:
    for type_flags in ((1,1), (1,0), (0,1)):
      d = operator_decl_params(
        array_type_name, "binary", "n/a", type_flags, equal_element_type)
      a = binary_operator_algo_params(array_type_name, type_flags)
      print """%s
  inline
%s
  %s(
    const %s& a1,
    const %s& a2,
    %s) {
%s
    result_array_type;
    typedef typename result_array_type::value_type return_element_type;
    %sresult_array_type result%s;
    array_operation_binary_addl_%s(functor_%s<
        return_element_type, %s, %s, %s>(),
      a1%s, a2%s, %s, result.begin(), %s,
      %s);
    %sreturn result;
  }
""" % (format_header("  ", d.header),
       format_list("  ", d.return_array_type),
       function_name, d.params[0], d.params[1], addl_args[0],
       format_list("    ", d.typedef_return_array_type),
       a.size_assert,
       a.result_constructor_args,
       a.type_flags_code,
       function_name, "ElementType", "ElementType", "ElementType",
       a.begin[0], a.begin[1], addl_args[1], a.loop_n,
       d.false_or_true_type_selector,
       a.set_size_back_door)

def generate_element_wise_special(
  array_type_name, special_def
):
  p = special_decl_params(array_type_name, special_def)
  if (len(p.arg_array_types) == 1):
    result_constructor_args = get_result_constructor_args(array_type_name)
    print """%s
  inline
  %s
  %s(const %s& a) {
    %s result%s;
    array_operation_unary(functor_%s<
      %s,
      %s >(),
      a.begin(), result.begin(), a.size(),
      %s);
    %sreturn result;
  }
""" % (format_header("  ", p.header),
       p.return_array_type,
       p.function_name, p.arg_array_types[0],
       p.return_array_type,
       result_constructor_args,
       p.function_name,
       special_def[0], special_def[2],
       p.false_or_true_type_selector,
       set_size_back_door(array_type_name))
  else:
    for type_flags in ((1,1), (1,0), (0,1)):
      a = binary_operator_algo_params(array_type_name, type_flags)
      params = []
      for i in xrange(2):
        if (type_flags[i]):
          params.append(p.arg_array_types[i])
        else:
          params.append(p.arg_element_types[i])
      print """%s
  inline
  %s
  %s(
    const %s& a1,
    const %s& a2) {
    %s result%s;
    %sarray_operation_binary_%s(functor_%s<
        %s,
        %s,
        %s >(),
      a1%s, a2%s, result.begin(), %s,
      %s);
    %sreturn result;
  }
""" % (format_header("  ", p.header), p.return_array_type,
       p.function_name, params[0], params[1],
       p.return_array_type,
       a.result_constructor_args,
       a.size_assert,
       a.type_flags_code,
       p.function_name,
       special_def[0], special_def[2], special_def[3],
       a.begin[0], a.begin[1], a.loop_n,
       p.false_or_true_type_selector,
       a.set_size_back_door)

def one_type(array_type_name):
  f = open("%s_algebra.h" % (array_type_name,), "w")
  sys.stdout = f
  write_copyright()
  print """
#ifndef CCTBX_ARRAY_FAMILY_%s_ALGEBRA_H
#define CCTBX_ARRAY_FAMILY_%s_ALGEBRA_H

#ifndef DOXYGEN_SHOULD_SKIP_THIS
""" % ((array_type_name.upper(),) * 2)
  if (array_type_name != "ref"):
    print "#include <cctbx/array_family/operator_traits_builtin.h>"
    print "#include <cctbx/array_family/operator_functors.h>"
    print "#include <cctbx/array_family/generic_array_operators.h>"
    print "#include <cctbx/array_family/std_imports.h>"
    print "#include <cctbx/array_family/misc_functions.h>"
  print """#include <cctbx/array_family/reductions.h>

namespace cctbx { namespace af {
"""

  if (array_type_name != "ref"):
    generate_unary_ops(array_type_name)
    for op_symbol in arithmetic_binary_ops:
      generate_elementwise_binary_op(
        array_type_name, "arithmetic", op_symbol)
      generate_elementwise_inplace_binary_op(
        array_type_name, "arithmetic", op_symbol + "=")
    for op_symbol in logical_binary_ops:
      generate_elementwise_binary_op(
        array_type_name, "logical", op_symbol)
    for op_symbol, function_name in (
      ("==", "equal_to"),
      ("!=", "not_equal_to"),
      (">", "greater"),
      ("<", "less"),
      (">=", "greater_equal"),
      ("<=", "less_equal")):
      generate_elementwise_binary_op(
        array_type_name, "boolean", op_symbol, function_name)
    for op_symbol in boolean_binary_ops:
      generate_reducing_boolean_op(array_type_name, op_symbol)
    generate_1arg_element_wise(
      array_type_name, cmath_1arg + cstdlib_1arg + complex_1arg)
    generate_2arg_element_wise(array_type_name, cmath_2arg)
    for special_def in complex_special:
      generate_element_wise_special(array_type_name, special_def)
    for args in misc_functions_2arg:
      apply(generate_2arg_addl_element_wise, (array_type_name,) + args)
  generate_1arg_reductions(array_type_name)
  generate_2arg_reductions(array_type_name)

  print """}} // namespace cctbx::af

#endif // DOXYGEN_SHOULD_SKIP_THIS

#endif // CCTBX_ARRAY_FAMILY_%s_ALGEBRA_H""" % (array_type_name.upper(),)
  sys.stdout = sys.__stdout__
  f.close()

def run():
  for array_type_name in ("ref", "tiny", "small", "shared", "versa"):
    one_type(array_type_name)

if (__name__ == "__main__"):
  run()
