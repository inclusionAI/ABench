import os
from openai import OpenAI
import requests
from typing import List, Optional, Dict, Any, Union
from .generation_config import GenerationConfig

class LLMInfer:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        extra_body: Optional[dict] = None,
        generation_config: Optional[Union[GenerationConfig, dict]] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.extra_body = extra_body or {}
        if isinstance(generation_config, GenerationConfig):
            self.generation_config = generation_config
        elif isinstance(generation_config, dict):
            self.generation_config = GenerationConfig.from_dict(generation_config)
        else:
            self.generation_config = GenerationConfig()

    def _call_vllm_offline_chat(self, messages, stream=False, **kwargs):
        try:
            from vllm import LLM, SamplingParams
        except ImportError:
            return "[vllm-offline] Please install vllm."
        prompt = ""
        for msg in messages:
            if msg["role"] == "user":
                prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n"
        prompt += "Assistant: "
        sampling_params = SamplingParams(**self.generation_config.to_dict())
        llm = LLM(model=self.model)
        outputs = llm.generate([prompt], sampling_params)
        return outputs[0].outputs[0].text.strip()

    def _call_vllm_chat(self, messages, stream=False, **kwargs):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = {
            "model": self.model,
            "messages": messages,
            **self.generation_config.to_dict(),
            "stream": stream,
        }
        data.update(kwargs)
        url = f"{self.api_base}/chat/completions"
        response = requests.post(url, headers=headers, json=data, stream=stream)
        if stream:
            def stream_generator():
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = line.decode("utf-8")
                            if chunk.startswith("data: "):
                                chunk = chunk[6:]
                            if chunk.strip() == "[DONE]":
                                break
                            import json
                            obj = json.loads(chunk)
                            delta = obj["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            continue
            return stream_generator()
        else:
            obj = response.json()
            return obj["choices"][0]["message"]["content"]

    def infer(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Any:
        # 1. 没有api_key, 说明是vllm, 而vllm分为离线和服务, 通过api_base判断
        if not self.api_key:
            if self.api_base and "localhost" in self.api_base:
                return self._call_vllm_chat(messages, stream=stream, **kwargs)
            else:
                return self._call_vllm_offline_chat(messages, stream=stream, **kwargs)
        # 2. 有api_key，标准openai协议
        is_qwen = self.api_base and "dashscope.aliyuncs.com" in self.api_base
        enable_thinking = self.extra_body.get("enable_thinking", False)
        if is_qwen:
            if enable_thinking:
                stream = True
            elif self.extra_body and not stream:
                self.extra_body["enable_thinking"] = False
        client = OpenAI(
            api_key=self.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=self.api_base or os.getenv("OPENAI_BASE_URL")
        )
        try:
            openai_config = self.generation_config.to_dict()
            openai_config.pop("top_k", None)  # openai协议不支持top_k
            if self.extra_body:
                kwargs["extra_body"] = self.extra_body
            completion = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                **openai_config,
                **kwargs
            )
            if stream and is_qwen and enable_thinking:
                reasoning_content = ""
                answer_content = ""
                is_answering = False
                for chunk in completion:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                        reasoning_content += delta.reasoning_content
                    if hasattr(delta, "content") and delta.content:
                        is_answering = True
                        answer_content += delta.content
                return f"<think>{reasoning_content}</think>{answer_content}"
            elif stream:
                def stream_generator():
                    for chunk in completion:
                        delta = getattr(chunk.choices[0], 'delta', None)
                        if delta and hasattr(delta, 'content') and delta.content:
                            yield delta.content
                return stream_generator()
            else:
                return completion.choices[0].message.content
        except Exception as e:
            return f"[OpenAI API Error] {str(e)}" 