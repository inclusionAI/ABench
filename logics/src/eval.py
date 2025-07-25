import argparse
import pandas as pd
import re
import json

def extract_boxed_text_postprocess(text: str) -> str:
    pattern = r'\\boxed\s*\{'
    matches = list(re.finditer(pattern, text))
    if not matches:
        return ""
    last_match = matches[-1]
    start = last_match.end()
    stack = 1
    end = start
    while end < len(text) and stack > 0:
        if text[end] == '{':
            stack += 1
        elif text[end] == '}':
            stack -= 1
        end += 1
    if stack == 0:
        return text[start:end-1]
    else:
        return ""

def compare_answers(pred, ref, is_order_str):
    # 先提取boxed内容
    pred = extract_boxed_text_postprocess(str(pred)) if isinstance(pred, str) else pred
    pred_answers = [p.strip().lower() for p in str(pred).strip().split(' ') if p.strip()]
    ref_answers = [r.strip().lower() for r in str(ref).strip().split(' ') if r.strip()]
    is_correct = False
    if is_order_str == '是':
        if pred_answers == ref_answers:
            is_correct = True
    elif is_order_str == '否':
        if len(pred_answers) == len(ref_answers) and set(pred_answers) == set(ref_answers):
            is_correct = True
    else:
        if pred_answers == ref_answers:
            is_correct = True
    return is_correct


def evaluate(result_file, result_col='result', answer_col='standard_answer', is_order_col='is_order'):
    df = pd.read_csv(result_file)
    correct = 0
    total = 0
    res_json = {"score": 2, "detail": []}
    res_list = []
    for idx, row in df.iterrows():
        pred = row[result_col]
        ref = row[answer_col]
        is_order = row[is_order_col] if is_order_col in row else '是'  # 默认顺序敏感
        mid = row['mid'] if 'mid' in row else idx  # 若无mid字段则用行号
        is_correct = compare_answers(pred, ref, is_order)
        if is_correct:
            correct += 1
        total += 1
        res_list.append({"pred": pred, "answer": ref, "correct":is_correct, "mid": row['mid']})
    acc = correct / total if total > 0 else 0
    res_json = {"score": 2, "detail": res_list}

    with open('/Users/wangjiayi/Downloads/abench_logics_json_res/QwQ32B.json', 'w') as f:
        json.dump(res_json, f, ensure_ascii=False, indent=4)
    print(f"Accuracy: {acc:.4f} ({correct}/{total})")
    return acc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result_file', type=str, required=True, help='Path to the result CSV file')
    parser.add_argument('--result_col', type=str, default='result', help='Column name for model predictions')
    parser.add_argument('--answer_col', type=str, default='standard_answer', help='Column name for standard answers')
    parser.add_argument('--is_order_col', type=str, default='is_order', help='Column name for order sensitivity')
    args = parser.parse_args()
    evaluate(args.result_file, args.result_col, args.answer_col, args.is_order_col)

if __name__ == '__main__':
    main()
