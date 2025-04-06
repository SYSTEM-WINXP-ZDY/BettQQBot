import aiohttp
import json
from typing import Dict, Any, List, Optional
from loguru import logger
from . import AIProvider
import time

class OpenRouterProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.primary_model = config.get("model", "deepseek/deepseek-r1:free")
        self.max_tokens = config.get("max_tokens", 2000)
        self.temperature = config.get("temperature", 0.7)
        self.site_url = config.get("site_url", "")
        self.site_name = config.get("site_name", "BettQQBot")
        
        # 添加备用模型列表，当主模型触发速率限制时使用
        self.fallback_models = config.get("fallback_models", [
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-2-13b-chat:free",
            "google/gemma-7b-it:free",
            "anthropic/claude-instant-v1:free",
            "nousresearch/nous-hermes-2-yi-34b:free"
        ])
        
        # 记录模型使用情况和冷却时间
        self.model_cooldowns = {}
        self.current_model = self.primary_model
        
        # 记录模型速率限制信息
        self.rate_limits = {}
        
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
        return await self.generate(system_prompt, chat_messages, 0)
        
    def _select_available_model(self) -> str:
        """根据冷却时间选择可用的模型"""
        now = time.time()
        
        # 清理过期的冷却时间
        expired_models = []
        for model, cooldown_until in self.model_cooldowns.items():
            if now > cooldown_until:
                expired_models.append(model)
                
        for model in expired_models:
            del self.model_cooldowns[model]
            logger.info(f"模型 {model} 冷却时间已过期，现在可用")
        
        try:
            # 如果主模型可用，优先使用主模型
            if self.primary_model not in self.model_cooldowns:
                return self.primary_model
                
            # 否则使用第一个可用的备用模型
            for model in self.fallback_models:
                if model not in self.model_cooldowns:
                    logger.warning(f"主模型 {self.primary_model} 正在冷却中，切换到备用模型: {model}")
                    return model
                    
            # 如果所有模型都在冷却中，使用冷却时间最短的模型
            if not self.model_cooldowns:
                logger.warning(f"没有模型在冷却中，但无法找到可用模型，使用主模型")
                return self.primary_model
                
            soonest_available = min(self.model_cooldowns.items(), key=lambda x: x[1])
            logger.warning(f"所有模型都在冷却中，使用冷却时间最短的模型: {soonest_available[0]}, 还需等待 {int(soonest_available[1] - now)} 秒")
            return soonest_available[0]
        except Exception as e:
            logger.error(f"选择可用模型时出错: {e}")
            # 发生错误时，返回主模型作为后备
            return self.primary_model
        
    def _set_model_cooldown(self, model: str, seconds: int = 60) -> None:
        """设置模型冷却时间"""
        self.model_cooldowns[model] = time.time() + seconds
        logger.warning(f"模型 {model} 进入冷却状态，冷却时间: {seconds}秒，将在 {time.strftime('%H:%M:%S', time.localtime(time.time() + seconds))} 后可用")
        
        # 记录当前所有模型的冷却状态
        cooldown_info = []
        now = time.time()
        for m, t in self.model_cooldowns.items():
            cooldown_info.append(f"{m}: 还剩 {int(t - now)} 秒")
        
        if cooldown_info:
            logger.info(f"当前模型冷却状态: {', '.join(cooldown_info)}")
        
    def _parse_rate_limit_headers(self, headers: Dict[str, str], model: str) -> None:
        """解析速率限制头部信息"""
        try:
            limit = int(headers.get("X-RateLimit-Limit", "0"))
            remaining = int(headers.get("X-RateLimit-Remaining", "0"))
            reset = int(headers.get("X-RateLimit-Reset", "0")) / 1000  # 转换为秒
            
            # 确保reset是一个合理的值
            if reset > 0:
                # 如果已经没有剩余请求数，设置模型冷却时间
                if remaining <= 0:
                    now = time.time()
                    cooldown_seconds = max(int(reset - now), 60)  # 至少冷却60秒
                    logger.warning(f"模型 {model} 已无剩余请求配额 (0/{limit})，设置冷却时间 {cooldown_seconds} 秒")
                    self._set_model_cooldown(model, cooldown_seconds)
                elif remaining <= limit * 0.1:  # 如果剩余请求低于10%，发出警告
                    logger.warning(f"模型 {model} 剩余请求数量较低: {remaining}/{limit}，即将达到限制")
                else:
                    logger.info(f"模型 {model} 速率限制: {remaining}/{limit}，重置时间: {time.strftime('%H:%M:%S', time.localtime(reset))}")
                
                self.rate_limits[model] = {
                    "limit": limit,
                    "remaining": remaining,
                    "reset": reset
                }
        except (ValueError, TypeError) as e:
            logger.error(f"解析速率限制头部信息时出错: {e}")
        
    async def generate(self, system_prompt: str, messages: List[Dict[str, str]], recursion_depth: int = 0) -> str:
        """生成对话回复"""
        # 检查递归深度，避免无限递归
        if recursion_depth > 5:  # 最多尝试5个不同的模型
            logger.error(f"达到最大递归深度({recursion_depth})，所有模型可能都在冷却中")
            return "抱歉，所有AI模型都暂时不可用喵，请稍后再试~"
            
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        # 选择一个可用的模型
        model = self._select_available_model()
        logger.info(f"使用模型: {model} 生成回复 (递归深度: {recursion_depth})")
        
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
            "model": model,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"发送请求到 OpenRouter API，模型: {model}，消息数: {len(formatted_messages)}")
                start_time = time.time()
                
                async with session.post(url, headers=headers, json=payload) as response:
                    elapsed_time = time.time() - start_time
                    logger.debug(f"OpenRouter API 响应时间: {elapsed_time:.2f}秒，状态码: {response.status}")
                    
                    # 解析速率限制头部信息
                    if "X-RateLimit-Limit" in response.headers:
                        self._parse_rate_limit_headers(response.headers, model)
                    
                    if response.status == 429:  # 速率限制
                        error_text = await response.text()
                        try:
                            error_json = json.loads(error_text)
                            error_message = error_json.get("error", {}).get("message", "Unknown error")
                            logger.error(f"模型 {model} 触发速率限制: {error_message}")
                            
                            # 获取更详细的错误信息
                            metadata = error_json.get("error", {}).get("metadata", {})
                            provider = metadata.get("provider_name", "未知提供商")
                            
                            # 设置冷却时间 - 对特定模型的限制使用较长时间，对整体限制使用更长时间
                            cooldown_seconds = 300  # 默认5分钟
                            
                            if "per-day" in error_message or "free-models-per-day" in error_message:
                                # 对于每日/每月限制，设置更长的冷却时间
                                logger.critical(f"触发了每日使用限制: {error_message} (提供商: {provider})")
                                # 为同一提供商的所有模型设置较长的冷却时间
                                if "deepseek" in model.lower():
                                    # 如果是DeepSeek模型触发每日限制，为所有DeepSeek模型设置冷却
                                    for m in list(self.fallback_models) + [self.primary_model]:
                                        if "deepseek" in m.lower() and m != model:
                                            self._set_model_cooldown(m, 7200)  # 其他DeepSeek模型也冷却2小时
                                    cooldown_seconds = 7200  # 触发限制的模型冷却2小时
                                else:
                                    cooldown_seconds = 3600  # 其他提供商冷却1小时
                            elif "per-month" in error_message:
                                # 月度限制更严重，设置更长冷却时间
                                logger.critical(f"触发了月度使用限制: {error_message} (提供商: {provider})")
                                cooldown_seconds = 86400  # 24小时冷却
                            elif model.lower() in error_message.lower():
                                # 针对特定模型的限制
                                logger.error(f"触发了模型特定的速率限制: {error_message} (提供商: {provider})")
                                cooldown_seconds = 600  # 10分钟冷却
                            else:
                                logger.warning(f"触发了一般性速率限制: {error_message} (提供商: {provider})")
                                
                            # 记录更详细的限制信息
                            reset_time = metadata.get("headers", {}).get("X-RateLimit-Reset", 0)
                            if reset_time and str(reset_time).isdigit():
                                reset_time = int(reset_time) / 1000  # 转换为秒
                                if reset_time > time.time():
                                    reset_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_time))
                                    logger.info(f"速率限制将在 {reset_str} 重置")
                                    # 根据重置时间调整冷却时间
                                    reset_duration = reset_time - time.time()
                                    if reset_duration > 0 and reset_duration < 86400:  # 小于一天的情况下使用精确时间
                                        cooldown_seconds = int(reset_duration) + 60  # 额外加1分钟冷却
                                        logger.info(f"根据重置时间调整冷却时间为 {cooldown_seconds} 秒")
                                        
                            # 设置当前模型的冷却时间
                            self._set_model_cooldown(model, cooldown_seconds)
                            
                            # 递归调用自己尝试使用另一个模型
                            logger.warning(f"尝试使用备用模型重新生成回复...")
                            return await self.generate(system_prompt, messages, recursion_depth + 1)
                        except Exception as e:
                            logger.error(f"解析速率限制错误信息失败: {e}, 原始响应: {error_text}")
                            self._set_model_cooldown(model, 300)  # 出错也设置冷却时间
                            return await self.generate(system_prompt, messages, recursion_depth + 1)  # 尝试使用其他模型
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API 返回错误: {response.status} - {error_text}")
                        return "抱歉，AI 回复生成失败喵！请稍后再试或联系管理员。"
                    
                    try:
                        result = await response.json()
                        
                        if "choices" in result and len(result["choices"]) > 0:
                            content = result["choices"][0]["message"]["content"]
                            logger.debug(f"成功获取AI回复，长度: {len(content)}字符")
                            return content
                        elif "error" in result:
                            # 如果返回了错误信息但状态码不是429，记录错误并返回友好提示
                            error_message = result.get("error", {}).get("message", "Unknown error")
                            logger.error(f"OpenRouter API 返回错误: {error_message}")
                            
                            # 如果错误中包含"rate limit"或"exceeded"，可能是速率限制，尝试切换模型
                            error_str = str(error_message).lower()
                            if "rate limit" in error_str or "exceeded" in error_str:
                                logger.warning(f"检测到可能的速率限制错误: {error_message}")
                                self._set_model_cooldown(model, 300)  # 设置冷却时间
                                return await self.generate(system_prompt, messages, recursion_depth + 1)  # 递归尝试其他模型
                                
                            return "抱歉，AI服务出现了一些问题喵，请稍后再试~"
                        else:
                            logger.error(f"OpenRouter API 响应格式异常: {result}")
                            return "AI 返回了奇怪的结果喵，不太明白它在说什么..."
                    except json.JSONDecodeError as e:
                        logger.error(f"解析OpenRouter API响应失败: {e}")
                        return "AI服务返回了无效数据喵，请稍后再试~"
        except Exception as e:
            logger.error(f"调用 OpenRouter API 时出错: {e}")
            # 设置当前模型的冷却时间
            self._set_model_cooldown(model, 60)  # 错误后冷却1分钟
            return "AI 服务连接失败喵，请稍后再试!" 