from latex2sympy2 import latex2sympy
import sympy as sp
import re

def replace_function_name(source_code, old_name, new_name):
    """
    Replaces a specified function name with a new name in Python source code
    
    Args:
        source_code (str): Source code string
        old_name (str): Original function name to be replaced
        new_name (str): New function name
        
    Returns:
        str: Modified source code after replacement
    """
    # Build regular expression pattern, note: handle whitespace around function name
    pattern = r'(def\s+)(' + re.escape(old_name) + r')(\s*)(\()'
    
    # Replace with the new function name, preserving whitespace formatting
    result = re.sub(
        pattern, 
        lambda m: m.group(1) + new_name + m.group(3) + m.group(4), 
        source_code
    )
    
    return result

def latex_to_sympy_code(latex_str):
    try:
        # Step 1: Convert LaTeX to SymPy expression
        expr = latex2sympy(latex_str)
        
        # Step 2: Extract all symbols from the expression
        symbols = sorted(expr.free_symbols, key=lambda s: s.name)
        symbol_names = [s.name for s in symbols]
        
        # Step 3: Generate complete Python code
        # Ensure all SymPy functions are called via sympy (sp)
        expr_repr = sp.srepr(expr)
        
        # Replace all SymPy types with sp. prefixed versions
        # Find all SymPy class names (those starting with capital letter)
        sympy_classes = set(re.findall(r'\b([A-Z][a-zA-Z0-9_]*)\b', expr_repr))
        
        # Add commonly used classes that may not appear in the expression
        sympy_classes.update(['sin', 'cos', 'tan', 'exp', 'log', 'Derivative', 'Integral', 'pi'])
        
        # For each SymPy class, add the sp. prefix  
        for cls in sympy_classes:
            # Replace only on whole word boundaries
            expr_repr = re.sub(r'\b' + cls + r'\b', 'sp.' + cls, expr_repr)
        
        # Add necessary import statements
        func_code = (
            "import sympy as sp\n\n"
            f"def calculate({', '.join(symbol_names)}):\n"
            f"    return {expr_repr}\n"
        )
        
        return {
            "expression": expr,
            "symbols": symbol_names,
            "python_code": func_code
        }
        
    except Exception as e:
        return {"error": str(e)}

def calc_symbols(latex_formula):
    # Replace each symbol/unit
    latex_formula = str(latex_formula)
    try:
        result = latex_to_sympy_code(latex_formula)
        
        namespace = {}
        result["python_code"] = replace_function_name(result["python_code"], 'calculate', 'temp_cal')
        exec(result["python_code"], namespace)
        calculate_func = namespace['temp_cal']
        result_expr = calculate_func()
        
        return float(result_expr.doit().subs({}))

    except:
        raise ValueError("Error evaluating LaTeX expression: " + latex_formula)
