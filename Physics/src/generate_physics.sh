python generate.py \
  --api_key sk-8db248b051ca4afb9ae5afb276c1695f \
  --api_base https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --model qwen3-235b-a22b \
  --generation_config '{"temperature": 0.0, "top_p": 1.0, "top_k": -1, "n": 1, "presence_penalty": 0.0, "frequency_penalty": 0.0, "max_tokens": 1024}' \
  --stream \
  --enable_thinking \
  --limit 1