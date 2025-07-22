# -*- coding: utf-8 -*-
import argparse
import pandas as pd
import re
from typing import List, Optional

def extract_boxed_text(text: str) -> Optional[str]:

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
        return text[start_index: current_index - 1]

    return None


def _normalize_answers(answer_str: str) -> List[str]:
    if not isinstance(answer_str, str):
        return []
    return [part.strip().lower() for part in answer_str.strip().split() if part.strip()]


def compare_answers(pred: str, ref: str, is_order_sensitive: bool) -> bool:
    pred_extracted = extract_boxed_text(pred)
    if pred_extracted is None:
        pred_extracted = str(pred)

    pred_normalized = _normalize_answers(pred_extracted)
    ref_normalized = _normalize_answers(ref)

    if not ref_normalized and not pred_normalized:
        return True
    if not ref_normalized or not pred_normalized:
        return False

    if is_order_sensitive:
        return pred_normalized == ref_normalized
    else:
        return len(pred_normalized) == len(ref_normalized) and set(pred_normalized) == set(ref_normalized)


def evaluate_benchmark(result_file: str, llm_response_col: str):
    ANSWER_COL = 'standard_answer'
    IS_ORDER_COL = 'is_order'

    try:
        df = pd.read_csv(result_file)
    except FileNotFoundError:
        print(f"Error: The file was not found at '{result_file}'")
        return None
    except pd.errors.ParserError:
        print(f"Error: Failed to parse the CSV file. Please check its format.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading the file: {e}")
        return None

    required_cols = [llm_response_col, ANSWER_COL, IS_ORDER_COL]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: The result file '{result_file}' is missing required columns: {missing_cols}")
        return None

    correct_count = 0
    total_count = len(df)
    if total_count == 0:
        print("Warning: The result file is empty. No evaluation to perform.")
        return 0.0

    for _, row in df.iterrows():
        prediction = row[llm_response_col]
        reference = row[ANSWER_COL]
        # Normalize 'is_order' column: 'YES' (case-insensitive) means sensitive.
        is_sensitive = str(row[IS_ORDER_COL]).strip().upper() == 'YES'

        if compare_answers(prediction, reference, is_sensitive):
            correct_count += 1

    accuracy = correct_count / total_count

    model_name = llm_response_col.replace('_pred', '').replace('_response', '')
    print("\n--- Benchmark Evaluation Results ---")
    print(f"Model Evaluated : {model_name}")
    print(f"Result File     : {result_file}")
    print(f"Score (Accuracy): {accuracy:.4f} ({correct_count} / {total_count})")
    print("----------------------------------")

    return accuracy

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Evaluate a language model's performance on a benchmark CSV file.",
        formatter_class=argparse.RawTextHelpFormatter  # For better help text formatting
    )

    parser.add_argument(
        '--result_file',
        type=str,
        default='../samples/Result_Logic.csv',
        help="Path to the result CSV file containing model predictions and standard answers."
    )

    parser.add_argument(
        '--llm_response',
        type=str,
        default='R1_response',
        help="Name of the column with the language model's responses to evaluate (e.g., 'R1_response')."
    )

    args = parser.parse_args()

    evaluate_benchmark(
        result_file=args.result_file,
        llm_response_col=args.llm_response
    )
