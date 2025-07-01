import argparse
from data import DataLoader
from model import LLM

# Set random seeds for reproducibility
seed = 1234

# Supported tasks -> physics,...
TASKS = ["Phy_A_fixed_400","Phy_B_dynamic_100"]


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument( "--model_type",type=str,default="openai",choices=["openai", "openai-compatible", "HF"],)
    parser.add_argument("--model_path", type=str, default="gpt-4.1")
    parser.add_argument("--task", type=str, default="all", choices=TASKS)
    parser.add_argument("--device", type=int, default=-1)
    args = parser.parse_args()

    # Initialize the LLM
    llm = LLM(
        model_type=args.model_type,
        model_path=args.model_path,
        device=args.device,
        
    )
    for task in TASKS :
        llm.init_prompt(task)
        dataloader = DataLoader(model=llm, task=task, seed=seed)
        dataloader.generate_responses()
        dataloader.evaluate()

