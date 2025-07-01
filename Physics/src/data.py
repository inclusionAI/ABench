import os
import json
import yaml
import string
from datasets import Dataset, DatasetDict
import pandas as pd
from utils import save_gen_results, compare_boxed_result_with_standard_answer, save_eval_results
from tqdm.auto import tqdm
import numpy as np

prompt_base = '''
You are a expert. Please read the following question and provide a step-by-step solution.
Put your final answer, in a \\boxed{} environment.
'''



class DataLoader:
    def __init__(
        self, model=None, task="Phy_A_fixed_400", data_path="data", seed=1234):
        self.client = model
        self.task = task
        self.seed = seed
        self.prompt = prompt_base

        if self.task == "Phy_A_fixed_400" or self.task == "Phy_B_dynamic_100":
            self.data_path = f"{data_path}/{self.task}.jsonl"
            self.dataset = self.load_samples_phy()
        else:
            pass


    def load_samples_phy(self):
        np.random.seed(self.seed)
        dataset = DatasetDict()
        raw_data = []
        df = pd.read_csv(self.data_path, encoding='utf-8')
        for i, row in df.iterrows():
            if 'suid' not in row:
                row['subid'] = '0'
            raw_data.append({
                'standard_question': row['standard_question'],
                'standard_answer': row['standard_answer'],
                'mid': row['mid'],
                'subid': row['subid'],
            })
        
        dataset = Dataset.from_list(raw_data)
        return dataset


    def generate_responses(self):
        print(f"> Generating {self.task} responses for {self.client.model_name}...")

        for idx, sample in tqdm(self.dataset.iterrows()):
            if self.task == "Phy_A_fixed_400" or self.task == "Phy_B_dynamic_100":
                msg = self.prompt.format(
                    standard_question=sample["standard_question"],
                    standard_answer=sample["standard_answer"],
                    mid=sample["mid"],
                    subid=sample["subid"],
                )
                response = self.client.gen_response(msg)
                res = {
                    "standard_question": sample["standard_question"],
                    "standard_answer": sample["standard_answer"],
                    "mid": sample["mid"],
                    "subid": sample["subid"],
                    "answer": response.get("answer", ""),
                }

            save_gen_results(res, self.task, self.client.model_name)

    def load_eval_results(self):
        file_path = f"results/{self.task}/{self.client.model_name}.jsonl"
        if not os.path.exists(file_path):
            print("No results found! Please run generation first.")
        else:
            responses = pd.read_json(
                path_or_buf=file_path, lines=True, encoding="utf-8"
            )
            if len(responses) != 200:
                print(
                    f"> Results are not complete (n = {len(responses)}/200), you should run the model again for missing samples"
                )
            return responses

    def evaluate(self):
        print(f"> Evaluating {self.task} results for {self.client.model_name}...")
        responses = self.load_eval_results()
        total_num = len(responses)
        correct = 0
        results = []
        if responses is not None and len(responses):
            if self.task == "Phy_A_fixed_400":
                for idx, response in responses.iterrows():
                    answer = response.get("answer") 
                    standard_answer = response.get("standard_answer")
                    is_correct = compare_boxed_result_with_standard_answer(answer, standard_answer, threshold=0.01)
                    if is_correct:
                        correct += 1
            elif self.task == "Phy_B_dynamic_100":
                responses = responses.apply(
                    lambda row: compare_boxed_result_with_standard_answer(responses['answer'], responses['standard_answer']), axis=1)


        if self.task == "Phy_A_fixed_400":
            if total_num == 0:
                results['Accuracy'] = 0
            else:
                results['Accuracy'] = 100 * correct / total_num

        elif self.task == "Phy_B_dynamic_100":
            original_value = responses[responses['subid'] == 0].sum()
            temp_data = responses[responses['subid'] != 0]
            temp_data = (responses.groupby('mid').sum() == 4)
            results['Static Accuracy'] = original_value/(total_num//4)
            results['Dynamic Accuracy'] = temp_data.sum()/len(temp_data)

        save_eval_results(results, self.task, self.client.model_name)
