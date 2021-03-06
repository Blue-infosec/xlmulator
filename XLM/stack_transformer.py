"""@package stack_transformer

Lark AST transformer to generate XLM_Objects from an AST generated from olevba_xlm.bnf.
Also functions for parsing olevba XLM.
"""

from __future__ import print_function
import string
import os
import re

# sudo pip install lark-parser
from lark import Lark
from lark import Transformer
from lark import UnexpectedInput

import XLM.color_print
from XLM.stack_item import *
from XLM.XLM_Object import *
import XLM.utils

## Load the olevba XLM grammar.
xlm_grammar_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), "olevba_xlm.bnf")
xlm_grammar = None
try:
    f = open(xlm_grammar_file, "r")
    xlm_grammar = f.read()
    f.close()
except IOError as e:
    XLM.color_print.output('r', "ERROR: Cannot read XLM grammar file " + xlm_grammar_file + ". " + str(e))
    sys.exit(102)
    
# Debugging flag.
debug = False

####################################################################
def fix_olevba_xlm(xlm_code):
    """
    plugin_biff.py does not escape some string characters that need escaping, so
    escape them.

    @param xlm_code (str) The olevba XLM code to modify.

    @return (str) The modified olevba XLM code.
    """

    # plugin_biff does not escape newlines in strings. Try to find them and fix them.
    xlm_code = xlm_code.strip().encode()
    r = b""
    mod_chunk = b""
    lines = xlm_code.split(b"\n")
    pos = -1
    new_line = b""
    xlm_pat = br"' \d\d\d\d {1,10}\d{1,6} [^\n]+\n"
    while (pos < (len(lines) - 1)):

        # Start putting together an aggregated line?
        pos += 1
        curr_line = lines[pos]
        if (curr_line.startswith(b"' ")):
            mod_chunk += new_line + b"\n"
            new_line = curr_line
            continue

        # This line is part of a string with unescaped newlines.
        new_line += b"\\n" + curr_line
    if (len(new_line) > 0):
        mod_chunk += b"\n" + new_line
    mod_chunk = mod_chunk.strip() + b"\n"

    # Handle double quotes in strings.
    for line in re.findall(xlm_pat, mod_chunk):

        # plugin_biff does not escape double quotes in strings. Try to find them
        # and fix them.
        #
        # ' 0006     72 FORMULA : Cell Formula - R9C1 len=50 ptgRefV R7C49153 ptgStr "Set wsh = CreateObject("WScript.Shell")" ptgFuncV FWRITELN (0x0089) 
        str_pat = b"Str \".*?\" ptg"
        str_pat1 = b"Str \"(.*?)\" ptg"
        for old_str in re.findall(str_pat, line):
            tmp_str = re.findall(str_pat1, old_str)[0]
            if (b'"' in tmp_str):
                # Escape single quotes.
                escaped_str = old_str[5:-5].replace(b"'", b"&apos;")
                new_str = b"Str '" + escaped_str + b"' ptg"

                line = line.replace(old_str, new_str)
        r += line

    # Done.
    return r
    
####################################################################
def parse_olevba_xlm(xlm_code):
    """
    Parse the given olevba XLM code into an internal object representation 
    that can be emulated.

    @param xlm_code (str) The olevba XLM code to parse.

    @return (dict) A dict of XLM formula objects (XLM_Object objects) where
    dict[ROW][COL] gives the XLM cell at (ROW, COL).
    """

    # Fix some escaping issues before parsing.
    xlm_code = XLM.utils.to_str(fix_olevba_xlm(xlm_code))
    
    # Parse the olevba XLM.
    xlm_ast = None
    try:
        xlm_parser = Lark(xlm_grammar, start="lines", parser='lalr')
        xlm_ast = xlm_parser.parse(xlm_code)
    except UnexpectedInput as e:
        XLM.color_print.output('r', "ERROR: Parsing olevba XLM failed.\n" + str(e))
        num_pat = r"at line (\d+), column (\d+)"
        error_loc = re.findall(num_pat, str(e))[0]
        line_num = int(error_loc[0]) - 1
        col_num = int(error_loc[1]) - 1
        lines = xlm_code.split("\n")
        bad_line = lines[line_num]
        bad_line = bad_line[:col_num] + "...ERROR START...-->" + bad_line[col_num:]
        XLM.color_print.output('r', "BAD LINE: " + bad_line)
        return None

    # Transform the AST into XLM_Object objects.
    if debug:
        print("=========== START XLM AST ==============")
        print(xlm_ast.pretty())
        print("=========== DONE XLM AST ==============")
    formula_cells = StackTransformer().transform(xlm_ast)
    if debug:
        print("=========== START XLM TRANSFORMED ==============")
        print(formula_cells)
        print("=========== DONE XLM TRANSFORMED ==============")
    return formula_cells

####################################################################
class StackTransformer(Transformer):
    """
    Lark AST transformer to generate XLM_Objects from an AST.
    """

    ##########################################################
    ## Non-terminal Transformers
    ##########################################################

    def lines(self, items):
        r = {}
        for line in items:
            line_type = line[2]            
            if (line_type != "FORMULA"):
                continue
            curr_info = line[3]
            row = curr_info[0][0]
            col = curr_info[0][1]
            curr_cell = XLM_Object(row, col, curr_info[1:])
            if (row not in r.keys()):
                r[row] = {}
            r[row][col] = curr_cell
        return r

    def xlm_line(self, items):
        return items
    
    def string_value(self, items):
        return str(items[0])

    def sheet_info(self, items):
        return str(items[0])

    def cell_value(self, items):
        return str(items[0])
    
    def line(self, items):
        return items

    def data(self, items):
        return items[0]
    
    def cell_formula(self, items):
        # Skip length.        
        r = [items[0]] + items[2:]
        return r

    def stack_item(self, items):
        return items[0]
    
    def cell(self, items):        
        return (items[0], items[1])

    def cell_area(self, items):
        # TODO: Need to handle "~" in cell areas.
        if (len(items) > 1):
            return (items[0], items[1])
        return items[0]

    def cell_area_col(self, items):
        return (-1, items[0])

    def cell_area_row(self, items):
        return (items[0], -1)
    
    def stack_int(self, items):
        return stack_int(items[0])
    
    def stack_funcv(self, items):
        # ['CHAR', '0x006f']
        return stack_funcv(items[0], items[1])
    
    def stack_concat(self, items):
        return stack_concat()
    
    def stack_cell_ref(self, items):
        return stack_cell_ref(items[0][0], items[0][1])
    
    def stack_str(self, items):
        return stack_str(items[0])
    
    def stack_bool(self, items):
        return stack_bool(items[0])
    
    def stack_attr(self, items):
        return stack_attr()
    
    def stack_add(self, items):
        return stack_add()
    
    def stack_sub(self, items):
        return stack_sub()
    
    def stack_exp(self, items):
        return stack_exp(items[0][0], items[0][1])
    
    def stack_name(self, items):
        return stack_name(items[0])
    
    def stack_num(self, items):
        if (len(items) == 0):
            return stack_str("FLOAT")
        return stack_num(items[0])
    
    def stack_missing_arg(self, items):
        return stack_missing_arg()
    
    def stack_func(self, items):
        return stack_func(items[0])
    
    def stack_func_var(self, items):
        # [1, 'RUN', '0x8011']
        return stack_func_var(items[1], items[0], items[2])
    
    def stack_namev(self, items):
        return stack_namev()
    
    def stack_area(self, items):
        return stack_area(items[0][0], items[0][1])
    
    def stack_less_than(self, items):
        return stack_less_than()
    
    def stack_namex(self, items):
        return stack_namex(items[0], items[1])
    
    def stack_not_equal(self, items):
        return stack_not_equal()
    
    def stack_mul(self, items):
        return stack_mul()
    
    def stack_paren(self, items):
        return stack_paren()
    
    def stack_array(self, items):
        return stack_array()
    
    def stack_equal(self, items):
        return stack_equal()
    
    def stack_greater_than(self, items):
        return stack_greater_than()
    
    def stack_mem_func(self, items):
        return stack_mem_func()
    
    def stack_power(self, items):
        return stack_power()
    
    def stack_ref_error(self, items):
        return stack_ref_error()
    
    def stack_mem_no_mem(self, items):
        return stack_mem_no_mem()
    
    def stack_area_error(self, items):
        return stack_area_error()
    
    def stack_div(self, items):
        return stack_div()
    
    def stack_uminus(self, items):
        return stack_uminus()

    def stack_uplus(self, items):
        return stack_uplus()
    
    def stack_greater_equal(self, items):
        return stack_greater_equal()
    
    def stack_area_3d(self, items):
        return stack_area_3d()
    
    def stack_end_sheet(self, items):
        return stack_end_sheet()
    
    def stack_mem_error(self, items):
        return stack_mem_error()

    def stack_mem_area(self, items):
        return stack_mem_area()

    def stack_range(self, items):
        return stack_range()
    
    def stack_percent(self, items):
        return stack_percent()

    def unparsed(self, items):
        return unparsed()

    def unknown_token(self, items):
        return unparsed()
    
    ##########################################################
    ## Terminal Transformers
    ##########################################################

    def BOOLEAN(self, items):
        return stack_bool(str(items))
    
    def NUMBER(self, items):
        return int(str(items))

    def NAME(self, items):
        return str(items)

    def HEX_NUMBER(self, items):
        return str(items)

    def DOUBLE_QUOTE_STRING(self, items):
        tmp = None
        try:
            tmp = str(items)
        except UnicodeEncodeError:
            tmp = ''.join(filter(lambda x:x in string.printable, items))
        return tmp[1:-1]

    def SINGLE_QUOTE_STRING(self, items):
        tmp = None
        try:
            tmp = str(items)
        except UnicodeEncodeError:
            tmp = ''.join(filter(lambda x:x in string.printable, items))
        return tmp[1:-1]

    def LINE_TYPE(self, items):
        return str(items)

    def STRING(self, items):
        tmp = None
        try:
            tmp = str(items)
        except UnicodeEncodeError:
            tmp = ''.join(filter(lambda x:x in string.printable, items))
        return tmp

    def DECIMAL(self, items):
        r = float(str(items))
        r_str = str(r)
        if (r_str[r_str.index("."):] == ".0"):
            r = int(r)
        return r
    
