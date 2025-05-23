from typing import Dict, Any
from . import AIProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider
from .custom_provider import CustomAIProvider as CustomProvider

def create_provider(config: Dict[str, Any]) -> AIProvider:
    """创建 AI 提供者实例"""
    provider_type = config["provider"]
    
    if provider_type == "openai":
        return OpenAIProvider(config["openai"])
    elif provider_type == "openrouter":
        return OpenRouterProvider(config["openrouter"])
    elif provider_type == "custom":
        return CustomProvider(config["custom"])
    else:
        raise ValueError(f"不支持的 AI 提供者类型: {provider_type}")
