# -*- coding: utf-8 -*-
"""
This script evaluates the performance of a language model on a law benchmark.
It uses a hybrid evaluation strategy:
- Rule-based evaluation for Multiple-Choice Questions (MCQ).
- LLM as a Judge for open-ended Short-Answer Questions (QA).

To run this script, you need to:
1. Install the required libraries: pip install pandas openai
2. Provide your OpenAI-compatible API key via the --api_key command-line argument.
"""
import argparse
import os
import re
import time
from typing import List, Optional

import openai
import pandas as pd


# --------------- LLM as Judge API Functions ---------------

def llm_infer(messages, api_key, model, attemp_count=5, max_tokens=4096, temperature=0.0):
    """
    Calls the specified model via the OpenAI-compatible API with retry logic.
    """
    client = openai.OpenAI(
        api_key=api_key
    )

    base_delay, max_delay = 4, 64
    last_exception = None
    for attempt in range(attemp_count):
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
            if attempt < attemp_count - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                time.sleep(delay)

    raise ValueError(f"Model {model} failed after {attemp_count} attempts. Last error: {last_exception}") from last_exception

def get_judge_response(messages, api_key):
    """
    Wrapper function to get a judgment from the judge model.
    """
    try:
        # Correctly pass api_key and model name to the inference function
        output = llm_infer(messages, api_key, 'gpt-4o-2024-11-20')
        return output.strip() if output else "[[INCORRECT]] No response from judge."
    except Exception as e:
        print(f"Failed to get response from judge LLM: {e}")
        return f"[[INCORRECT]] Error during API call: {e}"

# --------------- Judge Prompt Template ---------------

JUDGE_PROMPT_TEMPLATE = """您是一位公正的法律专家，作为评测员，您的任务是根据“标准答案”，判断“考生的回答”在法律上是否正确。

**评测规则:**
1.  **核心原则**: 您的首要目标是评估考生的回答在**法律实质上是否正确**。答案无需与标准答案的措辞完全一致。
2.  **完整性**: 考生的回答**必须包含标准答案中的所有关键法律要素**。如果缺少了关键要素（例如责任主体、具体的法律行为或条件），则判定为 `[[INCORRECT]]`。
3.  **准确性**: 考生的回答**不得包含重大的错误信息**。如果回答中包含了错误的责任方、错误的法律原则或与案情矛盾的事实，即便其中也包含部分正确信息，也应判定为 `[[INCORRECT]]`。
4.  **具体性**: 答案需要达到问题所要求的**具体程度**。如果问题问的是“谁”或“什么”，一个宽泛的法律原则是不足够的。例如，若标准答案是“A医院”，那么回答“有过错的一方”应被判定为 `[[INCORRECT]]`。
5.  **输出格式**: 您的最终判断**必须**以 `[[CORRECT]]` 或 `[[INCORRECT]]` 开头。在此标签之前，不要提供任何其他文字或解释。如有必要，您可以在标签后附上简要的解释。

**问题:**
{question}

**标准答案:**
{reference_answer}

**考生的回答:**
{predicted_answer}

**判断:**
"""

# --------------- Helper Functions ---------------

def extract_boxed_text(text: str) -> Optional[str]:
    """
    Extracts the content from the last \\boxed{} in a given text.
    This function correctly handles nested curly braces.
    """
    if not isinstance(text, str):
        return None
    pattern = r'\\boxed\s*\{'
    matches = list(re.finditer(pattern, text))
    if not matches:
        return None
    last_match = matches[-1]
    start_index = last_match.end()
    brace_stack = 1
    current_index = start_index
    while current_index < len(text) and brace_stack > 0:
        if text[current_index] == '{':
            brace_stack += 1
        elif text[current_index] == '}':
            brace_stack -= 1
        current_index += 1
    if brace_stack == 0:
        return text[start_index:current_index - 1]
    return None

def compare_mcq_answers(pred: str, ref: str) -> bool:
    """
    Compares answers for Multiple-Choice Questions (order-insensitive).
    """
    def _normalize(answer_str: str) -> List[str]:
        if not isinstance(answer_str, str): return []
        normalized_str = re.sub(r'[,\s、，]+', ' ', answer_str.strip())
        return [part.strip().upper() for part in normalized_str.split(' ') if part.strip()]

    pred_normalized = _normalize(pred)
    ref_normalized = _normalize(ref)

    if not ref_normalized and not pred_normalized: return True
    if not ref_normalized or not pred_normalized: return False
    return len(pred_normalized) == len(ref_normalized) and set(pred_normalized) == set(ref_normalized)

# --------------- Main Evaluation Function ---------------

def evaluate_law_benchmark(result_file: str, llm_response_col: str, output_file: str, api_key: str):
    """
    Main evaluation function that reads a CSV file, evaluates predictions, and calculates accuracy.
    """
    try:
        df = pd.read_csv(result_file)
    except FileNotFoundError:
        print(f"Error: File not found at '{result_file}'")
        return

    required_cols = [llm_response_col, 'standard_answer', 'type', 'standard_question']
    if not all(col in df.columns for col in required_cols):
        print(f"Error: The result file '{result_file}' is missing one or more required columns: {required_cols}")
        return

    results = []
    total_count = len(df)
    for index, row in df.iterrows():
        print(f"Evaluating sample {index + 1}/{total_count}...", flush=True)
        
        prediction_raw = row[llm_response_col]
        prediction_boxed = extract_boxed_text(prediction_raw)
        prediction = prediction_boxed if prediction_boxed is not None else str(prediction_raw)
        prediction_clean = prediction.strip()

        reference = row['standard_answer']
        question = row['standard_question']
        question_type = str(row['type']).strip().upper()
        
        is_correct = False
        judge_output = "N/A"

        if not prediction_clean:
            is_correct = False
            judge_output = "N/A (Automatic failure due to empty prediction)"
        else:
            if question_type == 'MCQ':
                is_correct = compare_mcq_answers(prediction_clean, reference)
                judge_output = "N/A (Rule-based)"
            elif question_type == 'QA':
                prompt_for_judge = JUDGE_PROMPT_TEMPLATE.format(
                    question=question,
                    reference_answer=reference,
                    predicted_answer=prediction_clean
                )
                messages = [{"role": "user", "content": prompt_for_judge}]
                judge_output = get_judge_response(messages, api_key) # Pass api_key here
                if judge_output.strip().upper().startswith('[[CORRECT]]'):
                    is_correct = True
            else: # Fallback for unknown types
                if prediction_clean == str(reference).strip():
                    is_correct = True
                    judge_output = "N/A (Rule-based exact match)"

        results.append({
            **row.to_dict(),
            'prediction': prediction_boxed,
            'is_correct': is_correct,
            'judge_output': judge_output
        })

    # Save detailed results to a new CSV file
    result_df = pd.DataFrame(results)
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nDetailed evaluation results saved to '{output_file}'")

    # Calculate and print final score
    correct_count = result_df['is_correct'].sum()
    accuracy = correct_count / total_count if total_count > 0 else 0.0
    
    model_name = llm_response_col.replace('_response', '')
    print("\n--- Law Benchmark Evaluation Results ---")
    print(f"Model Evaluated : {model_name}")
    print(f"output File     : {output_file}")
    print(f"Score (Accuracy): {accuracy:.4f} ({correct_count} / {total_count})")
    print("----------------------------------------")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Evaluate a language model's performance on a law benchmark CSV file using a hybrid approach.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--api_key",
        type=str,
        required=True,
        help="Your OpenAI-compatible API key for LLM as a Judge."
    )
    parser.add_argument(
        '--result_file',
        type=str,
        required=True,
        default='../samples/Result_Law.csv',
        help="Path to the result CSV file containing model predictions and standard answers."
    )
    parser.add_argument(
        '--llm_response_col',
        type=str,
        required=True,
        default='R1_response',
        help="Name of the column with the language model's responses to evaluate (e.g., 'R1_response')."
    )
    parser.add_argument(
        '--output_file',
        type=str,
        default='../evaluation_details.csv',
        help="Path to save the detailed evaluation results CSV file (default: evaluation_details.csv)."
    )
    args = parser.parse_args()

    evaluate_law_benchmark(
        result_file=args.result_file,
        llm_response_col=args.llm_response_col,
        output_file=args.output_file,
        api_key=args.api_key # Pass the key from args
    )
