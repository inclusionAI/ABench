import argparse
import pandas as pd
import os
import csv
import json
from utils import compare_boxed_result_with_standard_answer

def eval_Benchmark(folder_path, llm_response='R1_response'):
    """Evaluate Benchmark  with LLM results."""
    data = pd.read_csv(folder_path)

    view_list = []
    correct_count = 0; total_num = 0

    for question_num, model_answer in data[llm_response].items():
        total_num += 1
        standard_answer = data['standard_answer'][question_num]
        if compare_boxed_result_with_standard_answer(model_answer, standard_answer):
            correct_count += 1

    file_name = 'result'
    # Store accuracy in the DataFrame
    data[file_name] = correct_count / total_num
    view_list.append([llm_response, correct_count / total_num])

    view_table = pd.DataFrame(view_list, columns=['Models', 'Accuracy']).sort_values(by=['Accuracy'], ascending=False)
    view_table.to_csv('Actuary.csv', encoding='utf-8-sig', quoting=csv.QUOTE_ALL, index=False)
    print(view_table.to_markdown(index=False))


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm_response", type=str, default='R1_response')
    parser.add_argument("--result_file", type=str, default='../samples/Result_Actuary.csv')

    args = parser.parse_args()

    eval_Benchmark(args.result_file, args.llm_response)
