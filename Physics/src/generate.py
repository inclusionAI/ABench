import os
import argparse
import json
from infer import OpenAIInference
from generation_config import GenerationConfig

def main():
    parser = argparse.ArgumentParser(description="Run OpenAIInference on a CSV dataset.")
    parser.add_argument('--generation_config', type=str, default='{}', help='Generation config as JSON string')
    parser.add_argument('--model', type=str, required=True, help='Model name, e.g., gpt-3.5-turbo')
    parser.add_argument('--api_key', type=str, default=None, help='OpenAI API key (or set OPENAI_API_KEY env)')
    parser.add_argument('--api_base', type=str, default=None, help='OpenAI API base url (optional)')
    parser.add_argument('--data_path', type=str, default=None, help='Path to CSV data file')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of rows to infer')
    parser.add_argument('--enable_thinking', action='store_true', help='Enable Qwen thinking mode (for Qwen models)')
    parser.add_argument('--stream', action='store_true', help='Enable OpenAI stream mode')
    args = parser.parse_args()

    # 解析generation_config
    try:
        gen_config_dict = json.loads(args.generation_config)
    except Exception as e:
        raise ValueError(f"Invalid generation_config JSON: {e}")
    generation_config = GenerationConfig.from_dict(gen_config_dict)

    # 处理api_key优先级
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API key must be provided via --api_key or OPENAI_API_KEY env variable.")

    # 处理data_path
    if args.data_path:
        data_path = args.data_path
    else:
        data_path = os.path.join(os.path.dirname(__file__), "../data/Phy_A_fixed_400.csv")

    # extra_body用于Qwen的enable_thinking
    extra_body = {"enable_thinking": True} if args.enable_thinking else {"enable_thinking": False}

    inferencer = OpenAIInference(
        api_key=api_key,
        model=args.model,
        api_base=args.api_base,
        generation_config=generation_config,
        data_path=data_path,
        limit=args.limit,
        extra_body=extra_body,
        stream=args.stream
    )

    results = inferencer.infer(messages_col="standard_question")
    for idx, res in enumerate(results):
        print(f"Result {idx}: {res}\n")

    # 保存为jsonl
    output_path = os.path.join(os.path.dirname(__file__), "../data/phy_a_fixed_400_results.jsonl")
    with open(output_path, 'w', encoding='utf-8') as fout:
        for res in results:
            json.dump(res, fout, ensure_ascii=False)
            fout.write('\n')
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main() 