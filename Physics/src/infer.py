from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI
from generation_config import GenerationConfig
import pandas as pd
import logging
from vllm import LLM, SamplingParams

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


class VLLMInference(BaseInference):
    """
    使用 vLLM 进行离线推理的实现类。
    这个类会一次性加载所有数据，并以批处理方式进行推理，以获得最佳性能。
    """

    def __init__(
            self,
            model: str,
            generation_config: Optional[Union[GenerationConfig, dict]] = None,
            data_path: Optional[str] = None,
            limit: Optional[int] = None,
            tensor_parallel_size: int = 1,
            gpu_memory_utilization: float = 0.9,
            **kwargs,
    ):
        """
        初始化 VLLMInference 实例。

        Args:
            model (str): 模型路径或 Hugging Face Hub 上的模型名称。
            generation_config (Optional[Union[GenerationConfig, dict]]): 生成配置。
            data_path (Optional[str]): CSV 数据文件路径，用于 infer() 方法。
            limit (Optional[int]): 要处理的数据行数限制。
            tensor_parallel_size (int): 用于张量并行的大小。
            gpu_memory_utilization (float): 每个 GPU 使用的内存比例。
            **kwargs: 其他传递给 vllm.LLM 的参数。
        """
        self.model_path = model
        self.data_path = data_path
        self.limit = limit

        if isinstance(generation_config, GenerationConfig):
            self.generation_config = generation_config
        elif isinstance(generation_config, dict):
            self.generation_config = GenerationConfig.from_dict(generation_config)
        else:
            self.generation_config = GenerationConfig()

        # 将 GenerationConfig 转换为 vLLM 的 SamplingParams
        config_dict = self.generation_config.to_dict()
        self.sampling_params = SamplingParams(
            n=config_dict.get("n", 1),
            temperature=config_dict.get("temperature", 0.7),
            top_p=config_dict.get("top_p", 1.0),
            top_k=config_dict.get("top_k", -1),
            max_tokens=config_dict.get("max_tokens", 512),
            stop=config_dict.get("stop", None)
        )
        logger.info(f"Using vLLM SamplingParams: {self.sampling_params}")

        # 初始化 vLLM 引擎
        logger.info(f"Loading model '{self.model_path}' with vLLM...")
        self.llm = LLM(
            model=self.model_path,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            **kwargs
        )
        self.tokenizer = self.llm.get_tokenizer()
        logger.info("Model loaded successfully.")

    def infer(self, stream: Optional[bool] = None, messages_col: str = 'standard_question', **kwargs) -> Any:
        """
        从 CSV 文件读取数据，进行批量推理。

        Note: The 'stream' parameter is ignored as vLLM's batch generation is non-streaming.
        """
        if not self.data_path:
            raise ValueError("data_path is not set for infer method.")

        # 1. 数据加载和预处理
        try:
            df = pd.read_csv(self.data_path)
            if self.limit is not None:
                df = df.head(self.limit)
            prompts = df[messages_col].astype(str).tolist()
            mids = df["mid"].tolist() if "mid" in df.columns else [None] * len(prompts)
        except Exception as e:
            logger.error(f"[Data Parse Error] Could not read or process {self.data_path}: {str(e)}")
            return [{"error": f"[Data Parse Error] {str(e)}"}]

        logger.info(f"Starting inference on {len(prompts)} prompts...")

        # 2. 使用 vLLM 进行批量推理
        try:
            outputs = self.llm.generate(prompts, self.sampling_params)
        except Exception as e:
            logger.error(f"[vLLM Inference Error] {str(e)}")
            return [{
                "mid": mid,
                messages_col: prompt,
                "result": f"[vLLM Inference Error] {str(e)}",
                "choice_index": 0
            } for mid, prompt in zip(mids, prompts)]

        # 3. 格式化输出
        results = []
        for i, output in enumerate(outputs):
            for choice_index, generated_choice in enumerate(output.outputs):
                results.append({
                    "mid": mids[i],
                    messages_col: output.prompt,
                    "result": generated_choice.text,
                    "choice_index": choice_index
                })
        logger.info("Inference completed.")
        return results

    def batch_infer(self, batch_messages: List[List[Dict[str, str]]], stream: bool = False, **kwargs) -> Any:
        """
        对一批聊天消息进行推理。

        Note: The 'stream' parameter is ignored as vLLM's batch generation is non-streaming.
        """
        if not self.tokenizer:
            raise RuntimeError("Tokenizer is not available. Cannot process chat messages.")

        try:
            prompts = [
                self.tokenizer.apply_chat_template(conv, tokenize=False, add_generation_prompt=True)
                for conv in batch_messages
            ]
        except Exception as e:
            logger.error(f"Error applying chat template: {e}")
            raise

        logger.info(f"Starting batch inference on {len(prompts)} conversations...")
        outputs = self.llm.generate(prompts, self.sampling_params)

        results = [output.outputs[0].text for output in outputs]
        logger.info("Batch inference completed.")
        return results

