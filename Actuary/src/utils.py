import re
import math
import random
import numpy as np
from number_modify import EnhancedVariableExtractor, get_unit_template
from latex2python import calc_symbols
# 如需调用大语言模型，请使用项目根目录的llm_utils.py中的call_openai_chat函数


def get_standard_answer(answer):
    try:
        return extract_numerical_value(answer)[-1]
    except:
        return ''


def value_str(text: str) -> float:
    if ' ' in text:
        text = text.replace(' ', '')
    if is_scientific_notation(text):
        return calc_symbols(text)
    else:
        return float(text)


def extract_boxed_content(text: str) -> str:
    depth = 0
    start_pos = text.rfind(r"\boxed{")
    end_pos = -1
    if start_pos != -1:
        content = text[start_pos + len(r"\boxed{"):]
        for i, char in enumerate(content):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

            if depth == -1:
                end_pos = i
                break

    if end_pos != -1:
        return content[:end_pos].strip()

    return None


def format_to_answer(ans_str: str, num: float) -> str:
    if is_scientific_notation(ans_str):
        return format_to_latex_scientific(ans_str, num)
    else:
        return format_to_reference_precision(ans_str, num)


def format_to_reference_precision(ref_str: str, num: float) -> str:
    if '.' in ref_str:
        integer_part, decimal_part = ref_str.split('.')
        num_decimals = len(decimal_part)
    else:

        num_decimals = 0


    if num_decimals == 0:
        return str(round(num))

    format_spec = f".{num_decimals}f"

    formatted = format(num, format_spec)

    return formatted


def format_to_latex_scientific(ref_str: str, num: float) -> str:
    value, _ = extract_numerical_value(ref_str)
    return float_to_latex_scientific(num, count_significant_digits(value))


def float_to_latex_scientific(f, precision=4, force_exponent=False):
    if f == 0.0:
        return r"$0$"

    if not isinstance(f, (int, float)):
        raise ValueError("输入必须是数字")

    exponent = 0
    abs_f = abs(f)
    if abs_f >= 10.0:
        while abs_f >= 10.0:
            abs_f /= 10.0
            exponent += 1
    elif abs_f < 1.0 and abs_f > 0.0:
        while abs_f < 1.0:
            abs_f *= 10.0
            exponent -= 1

    mantissa = f / (10.0 ** exponent)

    format_str = f"{{:.{precision}g}}" if precision > 1 else "{:.0f}"
    mantissa_str = format_str.format(abs(mantissa))

    sign = "-" if f < 0 else ""

    if exponent == 0 and not force_exponent:
        return f"${sign}{mantissa_str}$"
    else:
        exponent_sign = "" if exponent >= 0 else "-"
        exponent_value = abs(exponent)
        return f"${sign}{mantissa_str} \\times 10^{{{exponent_sign}{exponent_value}}}$"


def is_scientific_notation(answer):
    sci_pattern1 = r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x)\s*\{?10\}?\s*\^\s*\{?\s*([-+]?\s*\d+)\s*\}?'

    sci_pattern2 = r'([-+]?\s*[\d\.]+)\s*(?:\*|×|\\times|\\cdot|x)\s*10\s*\{?\^\s*\{?\s*([-+]?\s*\d+)\s*\}?'

    sci_pattern3 = r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x)\s*10\s*\*\*\s*\{?\s*([-+]?\s*\d+)\s*\}?'
    return (
            bool(re.search(sci_pattern1, answer)) |
            bool(re.search(sci_pattern2, answer)) |
            bool(re.search(sci_pattern3, answer))
    )


def extract_numerical_value(answer):
    answer = delete_unit(answer)
    sci_pattern_list = [
        r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x)\s*\{?10\}?\s*\^\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?',
        r'([-+]?\s*[\d\.]+)\s*(?:\*|×|\\times|\\cdot|x)\s*10\s*\{?\^\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?',
        r'\{?\s*([-+]?\s*[\d\.]+)\s*\}?\s*(?:\*|×|\\times|\\cdot|x)\s*10\s*\*\*\s*\{?\s*([-+]?\s*\{?\d+\}?)\s*\}?'
    ]

    for sci_pattern in sci_pattern_list:
        sci_match = re.search(sci_pattern, answer)
        if sci_match:
            coefficient = sci_match.group(1).replace(' ', '')
            exponent = sci_match.group(2) or '0'
            exponent = exponent.replace(' ', '')
            exponent = re.sub(r'\{|\}', '', exponent)
            return str(coefficient), str(coefficient) + " \\times 10^{" + str(
                exponent) + '}' if exponent != '0' else str(coefficient)

    num_dict = EnhancedVariableExtractor(answer).list_params()
    if len(num_dict) >= 2:
        raise ValueError("Answer内容不唯一")
    for key_item, value in num_dict:
        return str(value), str(value)
    return None, None


def count_significant_digits(value):
    value = value.lower().replace(' ', '')

    if 'e' in value:
        num_part = value.split('e')[0]
    else:
        num_part = value

    num_part = num_part.lstrip('+-')

    if '.' in num_part:
        integer, decimal = num_part.split('.')
        if integer != '' and integer != '0':
            digits = integer.lstrip('0') + decimal
            return len(digits)
        else:
            decimal = decimal.lstrip('0')
            return len(decimal)
    else:
        stripped = num_part.lstrip('0')
        return len(stripped) if stripped != '' else 1


def extract_unit(s):
    combined_patterns = get_unit_template()
    match = re.search(combined_patterns, s)
    if match:
        unit = match.group(0)
        cleaned = re.sub(r'^\s*(\\cdot|\/|\^|\\times)\s*|\s*(\\cdot|\/|\^|\\times)\s*$', '', unit)
        return cleaned

    return None


def delete_unit(text):
    master_pattern = get_unit_template()
    return re.sub(master_pattern, '', text)


def contains_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fa5]", text))


def question_add_condition(question, answer):
    unit_name = extract_unit(answer)
    if contains_chinese(question):
        add_condition = ' (结果'
        if is_scientific_notation(answer):
            add_condition += "使用科学计数法，"
            num_value, num_temp = extract_numerical_value(answer)
        else:
            num_value, num_temp = extract_numerical_value(answer)
        if unit_name is not None:
            add_condition += "以$ " + unit_name + " $为单位，"

        add_condition += "保留" + str(count_significant_digits(num_value)) + "位有效数字)"

        return question + add_condition
    else:
        add_condition = ' (Results should be expressed '
        if is_scientific_notation(answer):
            add_condition += "in scientific notation, "
            num_value, num_temp = extract_numerical_value(answer)
        else:
            num_value, num_temp = extract_numerical_value(answer)
        if unit_name is not None:
            add_condition += "with units of $ " + unit_name + " $,"

        add_condition += "and rounded to " + str(count_significant_digits(num_value)) + " significant figures)"

        return question + add_condition

INDICATOR_WORDS = [
    'is equal to', 'are equal to', 'equals', 'is approximately', 'is about',
    'is on', 'are on', 'is', 'are', 'of', 'for', 'be'
]
TRAILING_WORDS = [
    'exactly', 'approximately', 'about', 'roughly'
]

def clean_latex_text(text):

    if not isinstance(text, str):
        return text

    cleaned_text = re.sub(r'\\(mathrm|text)\s*\{([^}]+)\}', r'\2', text)
    cleaned_text = re.sub(r'\{,\}', '', cleaned_text)
    cleaned_text = re.sub(r'\s+\(.*?\)', '', cleaned_text)
    cleaned_text = cleaned_text.strip()

    candidate_answer = cleaned_text
    indicator_pattern = r'\b(' + '|'.join(re.escape(word) for word in INDICATOR_WORDS) + r')\b'

    matches = list(re.finditer(indicator_pattern, cleaned_text, re.IGNORECASE))

    if matches:
        last_match = matches[-1]
        candidate_answer = cleaned_text[last_match.end():].strip()

    trailing_pattern = r'\s+\b(' + '|'.join(re.escape(word) for word in TRAILING_WORDS) + r')\b\s*$'
    final_answer = re.sub(trailing_pattern, '', candidate_answer, flags=re.IGNORECASE).strip()

    return final_answer if final_answer else candidate_answer


def process_single_input(latex_string):
    try:
        return calc_symbols(latex_string)
    except ValueError:
        return clean_latex_text(latex_string)


def compare_result_with_standard_answer(result_str, standard_answer, threshold_diff=0.01, threshold_per=0.001):
    result_value = process_single_input(result_str)
    answer_value = process_single_input(standard_answer)

    if isinstance(result_value, (int, float)) and isinstance(answer_value, (int, float)):
        answer_diff = abs(answer_value - result_value)
        if answer_diff <= threshold_per * abs(answer_value) and answer_diff <= threshold_diff:
            return True
        else:
            return False

    elif isinstance(result_value, str) and isinstance(answer_value, str):
        return result_value.strip().lower() == answer_value.strip().lower()

    else:
        return False


def parse_to_number(s: str):
    s = s.strip()
    try:
        if s.endswith('%'):
            return float(s.rstrip('%')) / 100.0
        else:
            return float(s)
    except (ValueError, TypeError):
        return None


def process_and_compare_string(input_str: str):
    strip_chars = ' \t\n\r\f\v,、。;.．'
    input_str = input_str.strip(strip_chars)

    if ' ' not in input_str:
        return input_str
    parts = input_str.split()
    if len(parts) != 2:
        return input_str

    part1_str, part2_str = parts

    num1 = parse_to_number(part1_str)
    num2 = parse_to_number(part2_str)

    if num1 is not None and num2 is not None:
        if math.isclose(num1, num2):
            return part1_str

    return input_str


def compare_boxed_result_with_standard_answer(output_str, standard_answer, threshold_diff=0.01, threshold_per=0.001):

    try:
        result_expression = extract_boxed_content(output_str)
        if result_expression is None:
            return False

        result_expression = re.sub(r'\\text', r'\\mathrm', result_expression)
        result_expression = delete_unit(result_expression)

        if '=' in result_expression or '\\approx' or '\\approx;' in result_expression:
            parts = re.split(r'=|\\approx', result_expression)
            result_expression = parts[-1]

        result_expression = re.sub(r'[\\$¥€£]', '', result_expression)
        result_expression = process_and_compare_string(result_expression)

        is_correct = compare_result_with_standard_answer(
            result_expression,
            standard_answer,
            threshold_diff,
            threshold_per
        )

        return is_correct

    except:
        return False


