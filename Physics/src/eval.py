import argparse
import pandas as pd
import os
import csv
import json
from utils import compare_boxed_result_with_standard_answer


def eval_Benchmark_A(folder_path, llm_response='R1_response'):
    """Evaluate Benchmark A with LLM results."""
    data = pd.read_csv(folder_path)

    view_list = []
    # Calculate accuracy using a for loop for debugging
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
    view_table.to_csv('Phy_A_fixed_400.csv', encoding='utf-8-sig', quoting=csv.QUOTE_ALL, index=False)
    print(view_table.to_markdown(index=False))
def eval_Benchmark_B(folder_path, llm_response='R1_response'):
    data = pd.read_csv(folder_path)

    total_num = len(data)
    view_list = []
    file_name = 'result'
    data[file_name] = data.apply(
        lambda row: compare_boxed_result_with_standard_answer(row[llm_response], row['standard_answer']),
        axis=1
    )

    original_value = data[data['subid'] == 0][file_name].sum()
    temp_data = data[data['subid'] != 0]
    temp_data = (data.groupby('mid')[file_name].sum() == 4)

    print(file_name, original_value/(total_num//4), temp_data.sum()/len(temp_data))
    view_list.append([llm_response, original_value/(total_num//4), temp_data.sum()/len(temp_data)])
    view_table = pd.DataFrame(view_list, columns=['Models', 'Static Accuracy', 'Dynamic Accuracy']).sort_values(by=['Dynamic Accuracy'], ascending=False)
    model_name, ori_values, dyn_values = [], [], []
    for i in range(len(view_list)):
        model_name.append(view_list[i][0])
        ori_values.append(view_list[i][1])
        dyn_values.append(view_list[i][2])
    view_table.to_csv('Phy_B_dynamic_100.csv', encoding='utf-8-sig', quoting=csv.QUOTE_ALL, index=False)
    print(view_table.to_markdown(index=False))
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm_response", type=str, default='R1_response')
    parser.add_argument("--result_file", type=str, default='../samples/Result_Phy_A_fixed_400.csv')
    # parser.add_argument("--result_file", type=str, default='../samples/Result_Phy_B_dynamic_100.csv')

    args = parser.parse_args()

    # evaluate Phy_A_fixed_400
    eval_Benchmark_A(args.result_file, args.llm_response)

    # evaluate Phy_B_dynamic_100
    # eval_Benchmark_B(args.result_file, args.llm_response)
