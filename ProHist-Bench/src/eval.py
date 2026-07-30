# -*- coding: utf-8 -*-
"""
This script evaluates the performance of a language model on ProHist-Bench,
a history (Chinese imperial examination) benchmark with three answer types:

All scoring branches first strip the model's reasoning/think block
(``split_and_remove_think``), mirroring the original opencompass pipeline which
scores ``predictions[idx]`` (think already stripped). The RAW output is
preserved in ``origin_prediction`` for the record; only the scoring inputs —
八股文 character count, the subjective judge prompt, and MCQ extraction (which
strips think itself) — use the think-stripped text. This matches the canonical
run file (ProHistBench_504.json).

Per type:
- 选择题 (MCQ): rule-based scoring against the boxed option set (0 / 60 / 100).
  The recorded ``model_answer`` is the EXTRACTED boxed option set (e.g.
  "ADEF"), matching the canonical run file.
- 八股文 (baguwen, eight-legged essay): rubric-based LLM-as-a-judge scoring,
  with a hard length constraint that zeros out over-length answers.
- 其他主观题 (名词解释 / 简答题 / 论述题 / 史料题 ...): rubric-based
  LLM-as-a-judge scoring (加分项 / 减分项 binary verdicts -> 0-100).

Design mirrors Law/src/eval.py: a single self-contained CLI script that reads
a result CSV holding the model's predictions AND the benchmark fields
(category, question, rubrics, answer, length_constraint, dynasty, content, ...),
scores each prediction with a hybrid rule-based + LLM-judge strategy, and
writes a detailed CSV plus a summary. The result CSV is self-contained — no
separate benchmark JSON is needed (build_samples.py produces exactly such a
CSV). Each row also surfaces the canonical judge-detail fields
(``origin_prediction``, ``processed_prediction``, ``reference``, ``correct``)
alongside the input prediction column.

To run this script, you need to:
1. Install the required libraries: pip install pandas openai
2. Provide your OpenAI-compatible API key via --api_key.
"""
import argparse
import time
from typing import Optional

import openai
import pandas as pd

from utils import (
    calculate_final_score,
    count_chinese_characters,
    extract_mcq_answer,
    get_rubric_weights,
    parse_scores,
    score_mcq,
    split_and_remove_think,
)


# --------------- ProHist-Bench Prompt Templates ---------------

# Rubric-scoring judge prompt (matches ProHist-Bench/LLM_judge_prompt.txt).
JUDGE_PROMPT_TEMPLATE = """
## 角色
您是一位具备20年中国史研究经验的历史学教授，在中国科举制度研究领域深耕多年，并发表数篇权威文章，手握多个国社科重点项目。

## 任务
严格根据【评分细则】单独判断下方【待评分回答】对于每一条细则是否有“明确提及/满足”，并赋予相应分数。

## 评分准则
1. 加分项必须完美符合描述才能得分，减分项内容若存在相关表述即可扣分；
2. 对每个评分条目进行二进制判定（0/1），1表示符合条件，0表示不符合；
3. 输出格式必须严格遵循指定模板，不多加解释。

## 问题
<question>
{question}
</question>

## 待评分回答
<answer>
{answer}
</answer>

## 评分细则
{rubric}

## 输出要求
1. 每条评分细则必须转换为带序号的标记行
2. 使用以下格式标记每个条目：
    加分项_序号:判定结果（1/0）
    减分项_序号:判定结果（1/0）
3. 不要添加任何解释性文字
4. 保持输出纯净以便正则解析

## 示例输出
加分项_1: 1
加分项_2: 0
加分项_3: 1
减分项_1: 1
减分项_2: 0""".strip()


# --------------- LLM as Judge API Functions ---------------

DEFAULT_JUDGE_MODEL = 'deepseek-r1-250528'


def llm_infer(messages, api_key, model, base_url: Optional[str] = None,
              attempt_count=5, max_tokens=4096, temperature=0.0):
    """
    Call the specified model via the OpenAI-compatible API with retry logic.
    """
    client_kwargs = {'api_key': api_key}
    if base_url:
        client_kwargs['base_url'] = base_url
    client = openai.OpenAI(**client_kwargs)

    base_delay, max_delay = 4, 64
    last_exception = None
    for attempt in range(attempt_count):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_exception = e
            print(f"Model {model} Attempt {attempt + 1} failed. Exception: {e}", flush=True)
            if attempt < attempt_count - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                time.sleep(delay)

    raise ValueError(
        f"Model {model} failed after {attempt_count} attempts. Last error: {last_exception}"
    ) from last_exception


def evaluate_score(prompt, api_key, model=DEFAULT_JUDGE_MODEL, base_url: Optional[str] = None,
                   max_retry=5, retry_interval=3) -> str:
    """
    Get a rubric verdict from the judge model with empty-output retries.

    Mirrors the original utils.evaluate_score contract, but routes the call
    through the OpenAI-compatible client. Returns "" when every retry yields
    no content.
    """
    messages = [{"role": "user", "content": prompt}]
    last_output = ""
    for attempt in range(max_retry):
        try:
            output = llm_infer(messages, api_key, model, base_url=base_url)
        except Exception as e:
            print(f"evaluate_score attempt {attempt + 1} raised: {e}", flush=True)
            output = ""
        if output:
            return output.strip()
        time.sleep(retry_interval)
    print(f"[WARNING] llm_infer连续{max_retry}次都无内容返回，prompt={repr(prompt)}")
    return last_output


# --------------- Per-type scoring ---------------

def score_rubric_question(question: str, pred: str, rubric: str,
                          api_key: str, model: str, base_url: Optional[str]):
    """
    Score a rubric-graded subjective question.

    Returns (single_score, judge_raw_output).
    """
    prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, answer=pred, rubric=rubric)
    model_output = evaluate_score(prompt, api_key, model=model, base_url=base_url)
    model_output_response = split_and_remove_think(model_output)

    rubric_scores = get_rubric_weights(rubric)
    parsed = parse_scores(model_output_response)
    single_score = calculate_final_score(parsed, rubric_scores)
    return single_score, model_output


def score_baguwen_question(question: str, pred: str, rubric: str, length_constraint: int,
                           api_key: str, model: str, base_url: Optional[str]):
    """
    Score an 八股文 question: over-length -> 0; otherwise rubric-graded.

    Returns (single_score, length, judge_raw_output_or_None).
    """
    length = count_chinese_characters(pred)
    if length > length_constraint:
        return 0, length, None
    single_score, model_output = score_rubric_question(
        question, pred, rubric, api_key, model, base_url
    )
    return single_score, length, model_output


# --------------- Main Evaluation Function ---------------

def _cell(row, col):
    """Return a CSV cell as a stripped string, '' for NaN/missing."""
    if col not in row.index:
        return ''
    val = row[col]
    if pd.isna(val):
        return ''
    return str(val).strip()


def evaluate_prohist_benchmark(result_file: str, llm_response_col: str,
                               output_file: str, api_key: str,
                               judge_model: str, base_url: Optional[str]):
    """
    Read the result CSV, score each prediction, write detailed results and
    print the final + per-category scores.

    The result CSV is self-contained: it carries the benchmark fields
    (category, question, rubrics, answer, length_constraint, dynasty, content,
    ...) alongside the model response column. All scoring-relevant fields are
    read directly from the row — no separate benchmark JSON is needed.
    """
    try:
        df = pd.read_csv(result_file)
    except FileNotFoundError:
        print(f"Error: File not found at '{result_file}'")
        return

    if llm_response_col not in df.columns:
        print(f"Error: response column '{llm_response_col}' not found in '{result_file}'.")
        print(f"Available columns: {list(df.columns)}")
        return

    # category drives the scoring branch; the others are used per-branch.
    needed_cols = ['id', 'category']
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        print(f"Error: result file '{result_file}' is missing required columns: {missing}")
        return

    from collections import defaultdict

    results = []
    total_count = len(df)
    scores = []
    category_scores = defaultdict(list)

    for index, row in df.iterrows():
        row_id = _cell(row, 'id') or str(index)
        category = _cell(row, 'category')
        question = _cell(row, 'question')
        rubric = _cell(row, 'rubrics')
        prediction = _cell(row, llm_response_col)
        # Strip the reasoning/think block BEFORE any scoring, so every branch
        # sees the think-stripped answer — matching the original opencompass
        # pipeline, which passes `predictions[idx]` (think already stripped) to
        # `score()`. `origin_prediction` (below) preserves the RAW output for the
        # record; only the scoring inputs use the stripped text. This is what
        # makes 八股文's length check and the subjective judge prompt match the
        # canonical run (ProHistBench_504.json).
        origin_prediction = prediction
        prediction_clean = split_and_remove_think(prediction).strip()

        print(f"Evaluating sample {index + 1}/{total_count} [id={row_id}, category={category}]...", flush=True)

        single_score = 0
        judge_raw = None
        length = None
        # Canonical judge-detail tracking.
        #   origin_prediction    : the RAW model response (think block intact),
        #                          kept for the record (== judge_detail.origin_prediction)
        #   processed_prediction : the think-stripped answer the score was
        #                          computed on (MCQ -> boxed letters; otherwise
        #                          the think-stripped response)
        #   reference            : what the score is judged against (gold answer
        #                          for MCQ; rubric for subjective)
        #   correct              : single_score / 100 (0/0.6/1 for MCQ; 0-1 rubric)
        processed_prediction = prediction_clean
        reference = ''

        if not prediction_clean:
            single_score = 0
            judge_raw = "N/A (Automatic failure due to empty prediction)"
        elif category == '选择题':
            # MCQ: model_answer is the EXTRACTED boxed option set (e.g. "ADEF").
            # extract_mcq_answer/score_mcq strip the think block themselves, so
            # passing the already-stripped prediction_clean is safe and gives the
            # same option set as the raw path.
            gold_answer = _cell(row, 'answer')
            processed_prediction = extract_mcq_answer(prediction_clean)
            single_score = score_mcq(prediction_clean, gold_answer)
            reference = gold_answer
            judge_raw = "N/A (Rule-based MCQ)"
        elif category == '八股文':
            # Length is counted on the THINK-STRIPPED essay (prediction_clean),
            # not the raw response — the think block's Chinese characters must
            # NOT count toward the length constraint, else essays are wrongly
            # zeroed. Matches the original score() which receives a stripped pred.
            try:
                len_const = int(float(_cell(row, 'length_constraint') or 0))
            except ValueError:
                len_const = 0
            single_score, length, judge_raw = score_baguwen_question(
                question, prediction_clean, rubric, len_const,
                api_key, judge_model, base_url,
            )
            reference = rubric
        else:
            single_score, judge_raw = score_rubric_question(
                question, prediction_clean, rubric,
                api_key, judge_model, base_url,
            )
            reference = rubric

        correct = single_score / 100 if single_score else 0.0

        scores.append(single_score)
        category_scores[category].append(single_score)

        # The result CSV already carries the benchmark fields, so the detail
        # row starts from the input row and we only overlay the evaluation
        # columns. `length` is the one computed field not present in the input.
        detail = {**row.to_dict()}
        detail.update({
            'rubric': rubric,
            'model_answer': processed_prediction,
            'single_score': single_score,
            'judge_model_scoring': judge_raw,
            # Canonical judge-details fields, surfaced as CSV columns.
            'origin_prediction': origin_prediction,
            'processed_prediction': processed_prediction,
            'reference': reference,
            'correct': correct,
        })
        if category == '八股文':
            detail['length'] = length

        if single_score == 0:
            print("*" * 100)
            print({k: detail.get(k) for k in ('id', 'category', 'single_score', 'length', 'answer')})
            print("*" * 100)

        results.append(detail)

    if not results:
        print("No samples were evaluated. Nothing to write.")
        return

    result_df = pd.DataFrame(results)
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nDetailed evaluation results saved to '{output_file}'")

    final_score = sum(scores) / len(scores) if scores else 0.0
    sub_scores = {k: (sum(v) / len(v) if v else 0.0) for k, v in category_scores.items()}

    model_name = llm_response_col.replace('_response', '')
    print("\n--- ProHist-Bench Evaluation Results ---")
    print(f"Model Evaluated  : {model_name}")
    print(f"Judge Model      : {judge_model}")
    print(f"Result File      : {result_file}")
    print(f"Output File      : {output_file}")
    print(f"Score (Overall)  : {final_score:.4f} ({len(scores)} samples)")
    print("--- Per-category scores ---")
    for cat, sc in sorted(sub_scores.items()):
        print(f"  {cat:<10}: {sc:.4f} ({len(category_scores[cat])} samples)")
    print("-" * 40)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Evaluate a language model's performance on ProHist-Bench (history benchmark) using a hybrid rule-based + LLM-judge approach.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--api_key",
        type=str,
        required=True,
        help="Your OpenAI-compatible API key for LLM as a Judge.",
    )
    parser.add_argument(
        "--api_base",
        type=str,
        default=None,
        help="Optional OpenAI-compatible API base URL (e.g. https://api.deepseek.com).",
    )
    parser.add_argument(
        "--llm_response_col",
        type=str,
        default='R1_response',
        help="Name of the column holding model responses to evaluate (default: R1_response).",
    )
    parser.add_argument(
        '--result_file',
        type=str,
        default='../samples/Result_ProHist.csv',
        help="Path to the result CSV file containing model predictions and benchmark fields (must have 'id' and 'category' columns).",
    )
    parser.add_argument(
        '--judge_model',
        type=str,
        default=DEFAULT_JUDGE_MODEL,
        help=f"Model name for the LLM-as-a-judge (default: {DEFAULT_JUDGE_MODEL}).",
    )
    parser.add_argument(
        '--output_file',
        type=str,
        default='../evaluation_details.csv',
        help="Path to save the detailed evaluation results CSV file.",
    )
    args = parser.parse_args()

    evaluate_prohist_benchmark(
        result_file=args.result_file,
        llm_response_col=args.llm_response_col,
        output_file=args.output_file,
        api_key=args.api_key,
        judge_model=args.judge_model,
        base_url=args.api_base,
    )
