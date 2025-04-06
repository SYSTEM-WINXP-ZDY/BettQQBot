from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AIProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """发送聊天请求并返回回复"""
        pass 