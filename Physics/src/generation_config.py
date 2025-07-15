class GenerationConfig:
    def __init__(
        self,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = -1,
        n: int = 1,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        max_tokens: int = 1024,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.n = n
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.max_tokens = max_tokens

    def to_dict(self):
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "n": self.n,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            temperature=d.get("temperature", 0.0),
            top_p=d.get("top_p", 1.0),
            top_k=d.get("top_k", -1),
            n=d.get("n", 1),
            presence_penalty=d.get("presence_penalty", 0.0),
            frequency_penalty=d.get("frequency_penalty", 0.0),
            max_tokens=d.get("max_tokens", 1024),
        ) 