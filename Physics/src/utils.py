import re
import os
import json
from number_modify import EnhancedVariableExtractor, get_unit_template
from latex2python import calc_symbols

def save_gen_results(data, task, model_name):
    file_dir = f"results/{task}"
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    file_name = f"{file_dir}/{model_name}.jsonl"

    with open(file_name, "a+") as f:
        json.dump(data, f, ensure_ascii=False)
        f.write("\n")




def get_standard_answer(answer):
    try:
        return extract_numerical_value(answer)[-1]
    except:
        return ''

def extract_boxed_content(text: str) -> str:
    """
    Extracts answers in \\boxed{}.
    """
    depth = 0
    start_pos = text.rfind(r"\boxed{")
    end_pos = -1
    if start_pos != -1:
        content = text[start_pos + len(r"\boxed{") :]
        for i, char in enumerate(content):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

            if depth == -1:  # exit
                end_pos = i
                break

    if end_pos != -1:
        return content[:end_pos].strip()

    return None


def extract_numerical_value(answer):
    """
    Extract the numerical result from the answer, ignoring symbols on the left and digits in subscripts.
    """
    answer = delete_unit(answer)

    # Match three numerical formats: scientific notation, decimals, integers
    sci_pattern_list = [
        # Support coefficients and exponents enclosed in curly braces
        r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x)\s*\{?10\}?\s*\^\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?',

        # Support various exponent formats
        r'([-+]?\s*[\d\.]+)\s*(?:\*|×|\\times|\\cdot|x)\s*10\s*\{?\^\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?',
        
        # Support scientific notation without '^' symbol
        r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x)\s*10\s*\*\*\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?'
    ]
  
    # Prioritize matching scientific notation
    for sci_pattern in sci_pattern_list:
        sci_match = re.search(sci_pattern, answer)
        if sci_match:
            coefficient = sci_match.group(1).replace(' ', '')
            exponent = sci_match.group(2) or '0'
            exponent = exponent.replace(' ', '')
            exponent = re.sub(r'\{|\}', '', exponent)
            return str(coefficient), str(coefficient) + " \\times 10^{" + str(exponent) + '}' if exponent != '0' else str(coefficient)
    
    # Match floating-point numbers
    num_dict = EnhancedVariableExtractor(answer).list_params()
    if len(num_dict) >= 2:
        raise ValueError("Answer内容不唯一")
    for key_item, value in num_dict:
        return str(value), str(value)
 
    return None, None


def delete_unit(text):
    text = re.sub(r'\\text', r'\\mathrm', text)
    master_pattern = get_unit_template()
    return re.sub(master_pattern, '', text)


def compare_result_with_standard_answer(result_str, standard_answer, threshold=0.01):
    try:
        result_value = calc_symbols(result_str)
    except :
        result_str = get_standard_answer(result_str)
    try:
        result_value = calc_symbols(result_str)
        answer_value = calc_symbols(standard_answer)
    except:
        return False
    if abs(answer_value - result_value) <= threshold * abs(answer_value):
        return True
    else:
        return False

def compare_boxed_result_with_standard_answer(output_str, standard_answer, threshold=0.01):
    try:
        result_expression = extract_boxed_content(output_str)
        if result_expression is None:
            return False
       
        result_expression = delete_unit(result_expression)
        if '=' in result_expression or '\\approx' in result_expression:
            parts = re.split(r'=|\\approx', result_expression)
            result_expression = parts[-1]
        
        return compare_result_with_standard_answer(result_expression, standard_answer, threshold=threshold)
    except:
        return False


def save_eval_results(results, task, model_name):
    file_name = f"results/{task}/{model_name}.json"

    if not os.path.exists(file_name):
        with open(file_name, "w") as f:
            json.dump({model_name: {task: results}}, f, ensure_ascii=False, indent=2)
    else:
        data = json.load(open(file_name, "r"))
        data[model_name] = data.get(model_name, {})
        data[model_name][task] = results
        with open(file_name, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# 如需调用大语言模型，请使用目录的llm_utils.py中的call_openai_chat函数