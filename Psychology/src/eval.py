# -*- coding: utf-8 -*-
import argparse
import pandas as pd
def evaluate_mcq(result_file: str, llm_response_col: str):
    ANSWER_COL = 'standard_answer'

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

    required_cols = [llm_response_col, ANSWER_COL]
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

        if prediction == reference:
            correct_count += 1

    accuracy = correct_count / total_count
    print("\n--- MCQ Evaluation Results ---")
    print(f"Result File     : {result_file}")
    print(f"Score (Accuracy): {accuracy:.4f} ({correct_count} / {total_count})")
    print("----------------------------------")
    return accuracy


def parse_rubric(rubric_text):
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
            score = int(line[start_index + 1:end_index])

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
    score_dict = {}
    for line in score_text.split('\n'):
        line = line.strip()
        if line:
            parts = line.split(': ', 1)
            if len(parts) == 2:
                key, value = parts
                try:
                    score_dict[key.strip()] = int(value.strip())
                except ValueError:
                    print(f"Warning: Unable to convert value '{value.strip()}' to an integer for key '{key.strip()}'.")
            else:
                print(f"Warning: Line '{line}' is not in the expected format 'key: value'.")
    return score_dict

def calculate_final_score(judgement, rubric_scores):
    final_score = 0
    full_score = 0
    for item, points in rubric_scores.items():
        if item in judgement and judgement[item] == 1:
            final_score += points
        if '加分项' in item:
            full_score += points
    if full_score == 0:
        print("Warning: full_score=0")
        return 0
    return round(final_score * 100 / full_score, 0)

def evaluate_qa(result_file: str, llm_response_col: str):
    RUBRIC_COL = 'rubric'
    JUDGEMENT_COL = 'judgement'

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

    required_cols = [llm_response_col, RUBRIC_COL, JUDGEMENT_COL]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: The result file '{result_file}' is missing required columns: {missing_cols}")
        return None

    total_score = 0
    for _, row in df.iterrows():
        rubric_text = row[RUBRIC_COL]
        judgement_text = row[JUDGEMENT_COL]

        rubric_scores = parse_rubric(rubric_text)
        judgement_scores = parse_scores(judgement_text)

        single_score = calculate_final_score(judgement_scores, rubric_scores)
        total_score += single_score

    accuracy = total_score / len(df) / 100
    print("\n--- QA Evaluation Results ---")
    print(f"Result File     : {result_file}")
    print(f"Score (Accuracy): {accuracy:.4f}")
    print("----------------------------------")

    return accuracy


# Example execution
if __name__ == '__main__':
        parser = argparse.ArgumentParser(
            description="Evaluate a language model's performance on MCQ or QA benchmarks.",
            formatter_class=argparse.RawTextHelpFormatter
        )

        parser.add_argument(
            '--eval_type',
            type=str,
            required=True,
            choices=['mcq', 'qa'],
            help="Type of evaluation to perform: 'mcq' for multiple-choice or 'qa' for rubric-based QA."
        )

        parser.add_argument(
            '--llm_response',
            type=str,
            default='R1_response',
            help="Name of the column with the language model's responses to evaluate (default: 'R1_response')."
        )

        parser.add_argument(
            '--result_file',
            type=str,
            default='../samples/Result_MCQ.csv',
            required=True,
            help="Path to the result CSV file."
        )

        args = parser.parse_args()

        if args.eval_type == 'mcq':
            evaluate_mcq(
                result_file=args.result_file,
                llm_response_col=args.llm_response
            )
        elif args.eval_type == 'qa':
            evaluate_qa(
                result_file=args.result_file,
                llm_response_col=args.llm_response
            )
        else:
            # This case should not be reached due to 'choices' in add_argument
            print(f"Error: Unknown evaluation type '{args.eval_type}'.")
