from latex2sympy2 import latex2sympy
import sympy as sp
import re

def replace_function_name(source_code, old_name, new_name):
    pattern = r'(def\s+)(' + re.escape(old_name) + r')(\s*)(\()'
    result = re.sub(
        pattern,
        lambda m: m.group(1) + new_name + m.group(3) + m.group(4),
        source_code
    )

    return result

def latex_to_sympy_code(latex_str):
    try:
        expr = latex2sympy(latex_str)
        symbols = sorted(expr.free_symbols, key=lambda s: s.name)
        symbol_names = [s.name for s in symbols]

        expr_repr = sp.srepr(expr)

        sympy_classes = set(re.findall(r'\b([A-Z][a-zA-Z0-9_]*)\b', expr_repr))

        sympy_classes.update(['sin', 'cos', 'tan', 'exp', 'log', 'Derivative', 'Integral', 'pi'])

        for cls in sympy_classes:
            expr_repr = re.sub(r'\b' + cls + r'\b', 'sp.' + cls, expr_repr)

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
        raise ValueError("Latex公式计算失败: " + latex_formula)

