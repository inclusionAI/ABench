# ABench-Logic
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)


## Overview
State‑of‑the‑art LLMs still struggle with formal logic reasoning and fallacy detection. This benchmark addresses a critical gap often overlooked by traditional fact- or semantics-based evaluation suites. Based on the principle of validity, we release a 500‑item test suite of discrete logical problems. Each task requires a valid inference: premises → inference → conclusion. All problems come from high‑discrimination real‑world logic exams and pass multiple layers of manual curation.

## Key features

🧠️ **→ Expert-crunched**: Every single problem is produced and double‑checked by domain experts strictly adheres to rigorous quality standards.
 
🔒 **→ Contamination-proof**: To prevent data contamination, each problem is sourced from thousands of questions and undergoes a rigorous multi-stage verification pipeline by both models and experts.

🔗  **→ RLVR-oriented**: Items retain the structural complexity of premier logic reasoning exams, stressing deep logical inference instead of superficial pattern matching.

🎯️ **→ Accurate evaluation**: Based on the foundational principles of logic, an inference is considered valid if and only if its conclusion is necessarily true whenever its premises are true. Our evaluation directly measure the absolute correctness of the answer with a strict all-or-nothing scoring scheme.


## Liscense

We are releasing this project under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). This allows for both personal and commercial use, provided that the original license and copyright notice are included in any distributed copies or substantial portions of the software.

We are releasing this project under the Creative Commons Attribution 4.0 International License (CC BY 4.0).

## Evaluation Metrics
We employ a strict, all-or-nothing scoring mechanism, where no partial credit is awarded. A model's response is judged as correct only if it perfectly matches the ground-truth answer. The specific criteria for correctness vary by question type:
* For Multiple-Choice Questions (MCQ):  A response is considered correct if and only if the set of selected options is exactly identical to the set of ground-truth correct options.
* For Question Answering (QA):  The answers to these questions consist of words. A response is judged as correct only if it is an exact match to the standard answer. For questions where the sequence of words is semantically crucial (explicitly marked by an is-order flag in our dataset), this exact match criterion is also order-sensitive.

## Main Results
![Main_Result](img/logic.png)
| Models                       |   Accuracy |
|:-----------------------------|-----------:|
| Gemini2.5-pro-reasoning      |     0.506  |
| Gemini2.5-pro                |     0.502  |
| o3                           |     0.454  |
| DeepSeek-R1                  |     0.412  |
| o1                           |     0.386  |
| QwQ-32B                      |     0.356  |
| Claude-3.7-Sonnet-Thinking   |     0.236  |
| Qwen-Max                     |     0.200  |
| DeepSeek-V3                  |     0.190  |
| GPT-4o                       |     0.190  |
| Claude-3.7-Sonnet            |     0.184  |
| O3mini                       |     0.184  |
| GPT4.1                       |     0.142  |
| DeepSeek-R1-Distill-Qwen-32B |     0.114  |
| Qwen3-30B-A3B                |     0.008  |


* Current SOTA models still struggle with our logical challenge benchmark, failing to reliably solve these problems.


## Data Structure
* The dataset contains 500 logical reasoning problems provided in a structured plain text file.The dataset has two distinct question formats: QA problems and MCQ. The QA entries are designed for tasks where the model must generate a specific word or ordered sequence of words as the answer.The MCQ entries are designed for tasks where the model must select the correct option(s) from a given list. For this question type, there may be one or more correct answers.This section serves as a fixed benchmark for consistent evaluation.
  
    **scheme**
    | mid | standard_question | standard_answer   | type | is_order  | 
    |----|----------|---------------------|------------|-------------|
    | 321 | question_text | answer_text | QA | YES |



## Usage Guide
1. Create an Environment Variables File (if you are using API models)
   ```
    API_KEY=<Your API Key>
    API_URL=<API Endpoint (if you are using a third-party API)
   ```
2. Install requirements
   ```
    pip install -r requirements.txt
   ```
3. Perform Evaluations Only

     If you have already generated LLM results and want to perform evaluations without re-running the model. First, please place the model's answers into a new column, following the format of Result_Logic.csv. Then, simply execute the following command:

    ```
   python src/eval.py \
        --llm_response "R1_response" \
        --result_file  ./samples/Result_Logic.csv
    ```

   --llm_response: specifies the name of the column in the CSV file where the model responses are stored (e.g., "R1_response").

   --result_file: the folder path, Result_Logic.csv, where the results produced by the model are stored. This script will utilize these results for accuracy assessment.


## Example problems
#### Multiple-Choice Questions
```
Question:
在一个古老的音乐合奏比赛中，有三位钢琴演奏者：小梅、小竹、小兰，以及三位小提琴演奏者：小荷、小菊、小莲。他们可以选择演奏四种音乐作品：协奏曲、奏鸣曲、交响乐和狂想曲。小梅演奏的是协奏曲或奏鸣曲；小菊演奏狂想曲；如果一部作品没有任何钢琴演奏者演奏，那么任何小提琴演奏者也不能演奏该作品；一部作品只有有小提琴演奏者演奏，钢琴演奏者才能演奏该作品；每个演奏者只能演奏一部作品。如果题干的断定为真，且有人演奏奏鸣曲，则演奏奏鸣曲的演奏者中不可能同时包含？
A、小梅和小竹
B、小竹和小兰
C、小兰和小荷
D、小兰和小莲
E、小荷和小莲
F、小梅和小荷
G、小竹和小荷
H、小梅和小莲
Answer: B
is-order：NO

Question:
On a large ranch called Prairie View Ranch, there are six cowboys named Jake, Tom, Ben, Sam, Cody, and Max. Each cowboy is proficient in two tasks: a primary task and a secondary task. Sam's secondary task is cattle roping. Three of the other cowboys have cattle roping as their primary task. Cody and Max both have horseback riding as one of their tasks. Max's primary task is fence mending, which is a secondary task for both Ben and Cody. Cattle roping and saddle making are Jake's tasks, but the primary-secondary relationship is the reverse of Sam's. Boot repairing is a secondary task for only one of them. The only cowboy with a sister has saddle making as his primary task.
Which one of the following can be true?
A、Ben's primary task is cattle roping
B、Cody has a sister
C、Jake's primary task is saddle making
D、Max has a sister
E、Sam has a sister
F、Max's secondary task is fence mending
G、Sam's secondary taks is saddle making
Answer: A E
is-order：NO

```


#### Question Answering
```
Question:
In the enchanted forest of Eldoria, three elves—Elara, Thalion, and Lyra—each hold a sacred role: Guardian (always speaks truth), Deceiver (always tells lies), or Mystic (alternates between truth and lies, starting with either). They share the following statements with a traveler:
Elara:Thalion is a Guardian.I am a Mystic.
Thalion:Elara is a Deceiver.I am a Guardian.
Lyra: I am a Guardian. Thalion is a Mystic.
What are the roles of Elara, Thalion, and Lyra respectively?
Answer:  Deceiver Guardian Mystic
is-order：YES

Question: 班级里有四个学生：小华、小丽、小强、小美。已知：小华说：“小美是年龄最小的。”小丽说：“我是小华的姐姐。”小强说：“四个人中只有哥哥是男生，其余都是女生。”如果上述都为真，四个学生按照年龄由大到小排序是：
Answer: 小丽 小华 小强 小美
is-order：YES

Question: In a spelling bee, three contestants - William, James, and Benjamin - are the top three scorers in some order. Each contestant makes two statements about their positions, with one statement being valid and the other being invalid. Here are their statements:William said: "I am not in first place." "James came second."James said: "I am the top scorer." "Benjamin was second."Benjamin said: "I am not the winner." "William finished third."
Which one is in second place?
Answer: William
is-order：NO

```



