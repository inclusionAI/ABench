# -*- coding: utf-8 -*-
"""
ProHist-Bench evaluation utilities.

Pure parsing/scoring helpers for the rubric-based LLM-as-a-judge evaluation.
All model inference lives in eval.py so this module stays free of any
specific ML-framework dependency (opencompass / datasets / requests are no
longer required here).
"""
import re


def split_and_remove_think(text) -> str:
    """
    Strip reasoning/thinking tokens from a model response.

    DeepSeek-R1 style models wrap their chain-of-thought in <think>...</think>.
    We only keep the part after the last </think> tag so downstream parsing
    sees the final answer block.
    """
    if type(text) is not str:
        return text

    THINK_TOKENS = ['</think>']
    for special_token in THINK_TOKENS:
        text = text.split(special_token)[-1]
    return text


def create_weight_map(rubric_part):
    """
    Build a {item_index: weight} map from one half of the rubric.

    Each rubric line carries a weight marker like {+5} or {-2}; we sum all
    weights on a single numbered item so multi-line items contribute their
    total weight.
    """
    weight_map = {}
    rubric_part = rubric_part.strip()
    if not rubric_part:
        return {}
    weight_regex = r'\{[+-]?\s*(\d+)\s*\}'
    items = re.split(r'\n(?=\s*\d+[、【.])', rubric_part)
    if items and not re.match(r'^\s*\d+', items[0]):
        items.pop(0)
    for item_text in items:
        index_match = re.match(r'\s*(\d+)', item_text)
        if not index_match:
            continue
        index_str = index_match.group(1)
        weights_found = re.findall(weight_regex, item_text)
        total_weight = sum(int(w) for w in weights_found)
        if total_weight > 0:
            weight_map[index_str] = total_weight
    return weight_map


def get_rubric_weights(rubric):
    """
    Split a rubric into '加分项' (bonus) and '减分项' (deduction) halves and
    return a unified {key: signed_weight} map.

    Bonus items keep their positive weight; deduction items are negated so the
    final score can simply sum the matched-item weights.
    """
    rubric_parts = re.split(r'减分项', rubric, maxsplit=1)
    bonus_rubric_part = rubric_parts[0]
    deduction_rubric_part = rubric_parts[1] if len(rubric_parts) > 1 else ""
    bonus_weights_map = create_weight_map(bonus_rubric_part)
    deduction_weights_map = create_weight_map(deduction_rubric_part)

    # 合成weight_map
    result = {}
    for k, v in bonus_weights_map.items():
        result[f'加分项_{k}'] = v
    for k, v in deduction_weights_map.items():
        result[f'减分项_{k}'] = -v
    return result


def parse_rubric(rubric_text):
    """
    (Legacy) Parse a rubric block into {item_key: score}.

    Kept for reference/compatibility; the score pipeline uses
    get_rubric_weights + parse_scores + calculate_final_score instead.
    """
    rubric_dict = {}
    idx = 0
    flag = 100000
    for line in rubric_text.split('\n'):
        idx += 1
        line = line.strip()
        if not line or '加分项' in line:
            continue
        if '减分项' in line:
            flag = idx

        try:
            start_index = line.index('{')
            end_index = line.index('}')
            score = int(line[start_index + 1:end_index].strip())

            item_name = line.split('、')[0].strip()
            if idx < flag:
                item_key = f"加分项_{item_name}"
            elif idx > flag:
                item_key = f"减分项_{item_name}"

            rubric_dict[item_key] = score
        except ValueError:
            continue

    return rubric_dict


def parse_scores(score_text):
    """
    Parse the judge model's line-per-rubric output into a {item_key: 1/0} dict.

    Expected lines look like:
        加分项_1: 1
        减分项_2: 0
    Non-conforming lines are reported and skipped.
    """
    score_dict = {}
    for line in score_text.split('\n'):
        line = line.strip().replace('：', ':')
        if line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key, value = parts
                try:
                    score_dict[key.strip()] = int(value.strip())
                except ValueError:
                    print(f"Warning: Unable to convert value '{value.strip()}' to an integer for key '{key.strip()}'.")
            else:
                print(f"Warning: Line '{line}' is not in the expected format 'key: value'.")
    return score_dict


def calculate_final_score(scores, rubric_scores):
    """
    Convert per-item 0/1 verdicts + rubric weights into a 0-100 score.

    final_score = sum(weight[item] for matched bonus/deduction items)
                  / sum(weight of all bonus items) * 100
    Deduction items push the score down (their weights are negative), but the
    total never goes below 0.
    """
    final_score = 0
    full_score = 0
    for item, points in rubric_scores.items():
        if item in scores and scores[item] == 1:
            final_score += points
        if '加分项' in item:
            full_score += points
    if full_score == 0:
        print("警告！！full_score=0")
        return 0
    if final_score < 0:
        final_score = 0
    return round(final_score * 100 / full_score, 0)


def count_chinese_characters(text):
    """
    Count Chinese (CJK) characters in `text`, ignoring punctuation, latin
    letters and digits. Used to enforce the 八股文 length constraint.
    """
    # 匹配所有中文字符（汉字），忽略标点、字母、数字
    chinese_chars = re.findall(r'[一-龥]', text)
    return len(chinese_chars)


def extract_mcq_answer(pred: str) -> str:
    """
    Extract the boxed multiple-choice answer from a model prediction.

    Strips reasoning tokens and LaTeX math delimiters, then pulls the content
    of the last \\boxed{...} occurrence and collapses it to uppercase letters.
    Returns "" when no boxed answer is found.
    """
    if not isinstance(pred, str):
        return ""
    pred_postprecessed = pred.split('</think>')[-1] \
        .replace('$', '') \
        .replace(r'\(', '') \
        .replace(r'\)', '') \
        .replace(r'\[', '') \
        .replace(r'\]', '')
    matches = re.findall(r'\\boxed\{([A-Z]+)\}', pred_postprecessed)
    result = matches[-1] if matches else ""
    return result


def score_mcq(pred: str, standard_answer: str) -> int:
    """
    Score an 不定项选择题 (multi-select MCQ) against the standard answer.

    - exact option-set match -> 100
    - non-empty strict subset of the standard set -> 60
    - otherwise -> 0
    """
    result = extract_mcq_answer(pred)
    std_answer_set = set(standard_answer)
    result_set = set(result)

    if result_set == std_answer_set:
        return 100
    if result_set.issubset(std_answer_set) and len(result_set) > 0:
        return 60
    return 0
