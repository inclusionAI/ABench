import os
import re
import time
import torch
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from transformers import pipeline
from utils import  get_model_name

load_dotenv("./.env")

prompt_phy = '''
You are a physics expert. Please read the following question and provide a step-by-step solution.
Put your final answer, which must be a readable LaTeX formula, in a \\boxed{} environment.
Question: {standard_question}
Answer:{answer}
'''



class LLM:
    def __init__(
        self,
        model_type="openai",
        model_path="gpt-4.1",
        device=-1,
    ):
        self.model_type = model_type
        self.model_path = model_path
        self.model_name = get_model_name(model_path)
        self.device = device if device >= 0 else "cpu"
        self.prompts = ''
        self.load_model()

    def init_prompt(self, task):
        if task == "Phy_A_fixed_400" or task == "Phy_B_dynamic_100":
            self.prompts = prompt_phy
        self.messages = [{"role": "system", "content": self.prompts}]

    def load_model(self):
        if self.model_type == "openai":
            self.client = ChatOpenAI(
                model=self.model_path,
                api_key=os.environ.get("API_KEY"),
                temperature=0.7,
            )
        elif self.model_type == "HF":
            self.client = pipeline(
                "text-generation", model=self.model_path, device=self.device
            )
        elif self.model_type == "openai-compatible":
            self.client = ChatOpenAI(
                model=self.model_path,
                base_url=os.environ.get("API_URL"),
                api_key=os.environ.get("API_KEY"),
                temperature=0.7,
            )
        else:
            print("Model is not supported at the moment")
            self.client = None

        print(f"> {self.model_name} loaded successfully")

    def gen_response(self, msg):
        messages = self.messages + [{"role": "user", "content": msg}]
        try:
            if self.model_type == "HF":
                response = self.client(messages, max_new_tokens=2048, return_full_text=False, )[0]
                response = response["generated_text"]
            else:
                response = self.client.invoke(messages)
                response = response.content
            
            if response is None:
                raise ValueError("No JSON response found")
            return response
        except Exception as e:
            print(f"Error: {e}")
            # Sleep for API calls
            if self.model_type != "HF":
                print("Retrying in 5 seconds...")
                time.sleep(5)
            return (
                {"answer": ""}
            )


