import aiohttp
import json
from typing import Dict, Any, List
from loguru import logger
from . import AIProvider

class OpenRouterProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "deepseek/deepseek-r1:free")
        self.max_tokens = config.get("max_tokens", 2000)
        self.temperature = config.get("temperature", 0.7)
        self.site_url = config.get("site_url", "")
        self.site_name = config.get("site_name", "BettQQBot")
        
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """实现AIProvider接口的chat方法"""
        # 从消息中提取系统提示
        system_prompt = ""
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                chat_messages.append(msg)
        
        # 如果没有单独的系统提示，使用空字符串
        return await self.generate(system_prompt, chat_messages)
        
    async def generate(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        """生成对话回复"""
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
            
        if self.site_name:
            headers["X-Title"] = self.site_name
            
        # 添加系统提示
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt
            })
            
        # 添加用户和助手的对话消息
        formatted_messages.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API 返回错误: {response.status} - {error_text}")
                        return "抱歉，AI 回复生成失败喵！请稍后再试或联系管理员。"
                    
                    result = await response.json()
                    
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                        return content
                    else:
                        logger.error(f"OpenRouter API 响应格式异常: {result}")
                        return "AI 返回了奇怪的结果喵，不太明白它在说什么..."
        except Exception as e:
            logger.error(f"调用 OpenRouter API 时出错: {e}")
            return "AI 服务连接失败喵，请稍后再试!" 