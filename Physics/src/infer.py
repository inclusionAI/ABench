from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI
from generation_config import GenerationConfig
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseInference(ABC):
    @abstractmethod
    def infer(self, stream: Optional[bool] = None, messages_col: str = 'standard_question', **kwargs) -> Any:
        pass

    @abstractmethod
    def batch_infer(self, batch_messages: List[List[Dict[str, str]]], stream: bool = False, **kwargs) -> Any:
        pass

class OpenAIInference(BaseInference):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        extra_body: Optional[dict] = None,
        generation_config: Optional[Union[GenerationConfig, dict]] = None,
        data_path: Optional[str] = None,
        limit: Optional[int] = None,
        stream: bool = False,
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.extra_body = extra_body or {}
        self.data_path = data_path
        self.limit = limit
        self.stream = stream
        if isinstance(generation_config, GenerationConfig):
            self.generation_config = generation_config
        elif isinstance(generation_config, dict):
            self.generation_config = GenerationConfig.from_dict(generation_config)
        else:
            self.generation_config = GenerationConfig()
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

    def infer(self, stream: Optional[bool] = None, messages_col: str = 'standard_question', **kwargs) -> Any:
        results = []
        if not self.data_path:
            raise ValueError("data_path is not set.")
        logger.info(f"Using generation config: {self.generation_config.to_dict()}")
        df = pd.read_csv(self.data_path)
        if self.limit is not None:
            df = df.head(self.limit)
        use_stream = self.stream if stream is None else stream
        if use_stream:
            return self._infer_stream(df, messages_col, **kwargs)
        else:
            return self._infer_nostream(df, messages_col, **kwargs)

    def _infer_stream(self, df, messages_col, **kwargs):
        from collections import defaultdict
        results = []
        for idx, row in df.iterrows():
            logger.info(f"Infer row {idx}")
            try:
                question = row[messages_col]
                msgs = [{"role": "user", "content": str(question)}]
                mid = row["mid"] if "mid" in row else None
            except Exception as e:
                logger.error(f"[Data Parse Error] row {idx}: {str(e)}")
                results.append({
                    "mid": row["mid"] if "mid" in row else None,
                    messages_col: row[messages_col] if messages_col in row else None,
                    "result": f"[Data Parse Error] {str(e)}",
                    "choice_index": 0
                })
                continue
            try:
                openai_generation_config = self.generation_config.to_dict()
                openai_generation_config.pop("top_k", None)
                if self.extra_body:
                    kwargs["extra_body"] = self.extra_body
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    stream=True,
                    **openai_generation_config,
                    **kwargs
                )
                choice_contents = defaultdict(lambda: {"reasoning_content": "", "content": ""})
                for chunk in completion:
                    for i, choice in enumerate(chunk.choices):
                        delta = getattr(choice, 'delta', None)
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                            choice_contents[i]["reasoning_content"] += delta.reasoning_content
                        if delta and hasattr(delta, 'content') and delta.content:
                            choice_contents[i]["content"] += delta.content
                for i, v in choice_contents.items():
                    if v["reasoning_content"]:
                        result_str = f"<think>{v['reasoning_content']}</think>{v['content']}"
                    else:
                        result_str = v["content"]
                    results.append({
                        "mid": mid,
                        messages_col: question,
                        "result": result_str,
                        "choice_index": i
                    })
            except Exception as e:
                logger.error(f"[OpenAI API Error] row {idx}: {str(e)}")
                results.append({
                    "mid": mid,
                    messages_col: question,
                    "result": f"[OpenAI API Error] {str(e)}",
                    "choice_index": 0
                })
        return results

    def _infer_nostream(self, df, messages_col, **kwargs):
        results = []
        for idx, row in df.iterrows():
            logger.info(f"Infer row {idx}")
            try:
                question = row[messages_col]
                msgs = [{"role": "user", "content": str(question)}]
                mid = row["mid"] if "mid" in row else None
            except Exception as e:
                logger.error(f"[Data Parse Error] row {idx}: {str(e)}")
                results.append({
                    "mid": row["mid"] if "mid" in row else None,
                    messages_col: row[messages_col] if messages_col in row else None,
                    "result": f"[Data Parse Error] {str(e)}",
                    "choice_index": 0
                })
                continue
            try:
                openai_generation_config = self.generation_config.to_dict()
                openai_generation_config.pop("top_k", None)
                if self.extra_body:
                    kwargs["extra_body"] = self.extra_body
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    stream=False,
                    **openai_generation_config,
                    **kwargs
                )
                for i, choice in enumerate(completion.choices):
                    reasoning_content = ""
                    if hasattr(choice, 'delta') and hasattr(choice.delta, 'reasoning_content') and choice.delta.reasoning_content is not None:
                        reasoning_content = choice.delta.reasoning_content
                    content = choice.message.content
                    if reasoning_content:
                        result_str = f"<think>{reasoning_content}</think>{content}"
                    else:
                        result_str = content
                    results.append({
                        "mid": mid,
                        messages_col: question,
                        "result": result_str,
                        "choice_index": i
                    })
            except Exception as e:
                logger.error(f"[OpenAI API Error] row {idx}: {str(e)}")
                results.append({
                    "mid": mid,
                    messages_col: question,
                    "result": f"[OpenAI API Error] {str(e)}",
                    "choice_index": 0
                })
        return results

    def batch_infer(self, batch_messages: List[List[Dict[str, str]]], stream: bool = False, **kwargs) -> Any:
        raise NotImplementedError("openai batch_infer not implemented yet.") 