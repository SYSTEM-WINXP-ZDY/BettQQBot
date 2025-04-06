from src.plugins import Plugin
from loguru import logger
from src.ai_providers.factory import create_provider
from src.utils.access_control import AccessControl
from src.utils.memory_manager import MemoryManager
from typing import Optional, Dict, Any, List
import aiohttp

class ChatPlugin(Plugin):
    async def on_load(self):
        logger.info("聊天插件已加载")
        
        config = self.bot.config["features"]["chat"]
        
        self.ai_provider = create_provider(config)
        
        self.system_prompt = config.get("system_prompt", "")
        
        self.memory_enabled = config.get("memory", {}).get("enabled", False)
        
        self.debug_enabled = config.get("debug", False)
        if self.debug_enabled:
            logger.info("聊天插件调试模式已启用")
        
        self.access_control = AccessControl(
            config.get("access_control", {}),
            self.bot.config["bot"]["admin"]["super_users"]
        )
        
        self.memory_manager = MemoryManager(config.get("memory", {}))
        
        self.user_info_cache: Dict[int, Dict[str, Any]] = {}
        
        self.session_stats = {
            "total_time": 0.0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "requests_count": 0,
            "start_time": None
        }
        
        import time
        self.session_stats["start_time"] = time.time()
        
    async def on_unload(self):
        logger.info("聊天插件已卸载")
        self._show_session_stats()
        
    def _show_session_stats(self):
        if self.session_stats["requests_count"] == 0:
            logger.info("本次会话没有AI请求")
            return
        
        import time
        session_duration = time.time() - self.session_stats["start_time"]
        
        logger.info("\n")
        logger.info("=" * 60)
        logger.info("=" * 15 + " 本次会话AI使用统计 " + "=" * 15)
        logger.info("=" * 60)
        logger.info(f"总运行时间: {session_duration:.2f}秒")
        logger.info(f"AI请求次数: {self.session_stats['requests_count']}次")
        logger.info(f"AI处理总耗时: {self.session_stats['total_time']:.2f}秒")
        logger.info(f"Token统计:")
        logger.info(f"  - 提示词tokens: {self.session_stats['prompt_tokens']}")
        logger.info(f"  - 回复tokens: {self.session_stats['completion_tokens']}")
        logger.info(f"  - 总tokens: {self.session_stats['total_tokens']}")
        logger.info(f"估计总费用: ${self.session_stats['total_tokens']/1000 * 0.002:.5f}")
        logger.info("=" * 60)
        
    async def _get_user_info(self, user_id: int) -> Dict[str, Any]:
        try:
            info = await self.bot.api.get_stranger_info(user_id=user_id)
            if info.get("status") == "failed":
                logger.error(f"获取用户 {user_id} 信息失败: {info}")
                return {"user_id": user_id, "nickname": str(user_id)}
            return info.get("data", {"user_id": user_id, "nickname": str(user_id)})
        except Exception as e:
            logger.error(f"获取用户 {user_id} 信息失败: {e}")
            return {"user_id": user_id, "nickname": str(user_id)}
        
    def _get_system_prompt(self, user_id: int, nickname: str) -> str:
        is_master = user_id in self.bot.config["bot"]["admin"]["super_users"]
        prompt = self.system_prompt + "\n\n"
        
        if is_master:
            prompt += f"当前对话的用户是我的主人 {nickname}（QQ: {user_id}喵喵~要傲娇而不失去礼貌哦！），要用特别尊敬和亲昵的语气对待喵~\n"
        else:
            prompt += f"当前对话的用户是 {nickname}（QQ: {user_id}）喵~\n"
            
        return prompt
        
    async def _is_admin_command(self, user_id: int) -> bool:
        return user_id in self.bot.config["bot"]["admin"]["super_users"]
        
    async def _handle_admin_command(self, command: str, group_id: Optional[int], user_id: int) -> str:
        user_info = await self._get_user_info(user_id)
        logger.info(f"用户 {user_info['nickname']}({user_id}) 使用管理命令: {command}")
        
        if user_id not in self.bot.config["bot"]["admin"]["super_users"]:
            logger.warning(f"用户 {user_info['nickname']}({user_id}) 尝试使用管理命令被拒绝")
            return "只有主人才能使用此命令喵~"
            
        parts = command.split()
        if len(parts) < 2:
            return "命令格式错误喵~"
            
        cmd = parts[0]
        action = parts[1]
        
        if cmd == "/chat.memory":
            if action == "clear":
                if len(parts) > 2:
                    target_id = int(parts[2])
                    if len(parts) > 3 and parts[3] == "group":
                        self.memory_manager.clear_memories(target_id, target_id)
                        logger.info(f"已清除群 {target_id} 的记忆")
                        return f"已清除群 {target_id} 的记忆喵~"
                    else:
                        target_info = await self._get_user_info(target_id)
                        self.memory_manager.clear_memories(target_id)
                        logger.info(f"已清除用户 {target_info['nickname']}({target_id}) 的记忆")
                        return f"已清除用户 {target_info['nickname']}({target_id}) 的记忆喵~"
                else:
                    if group_id:
                        self.memory_manager.clear_memories(user_id, group_id)
                        logger.info(f"已清除群 {group_id} 中用户 {user_info['nickname']}({user_id}) 的记忆")
                        return "已清除当前群的记忆喵~"
                    else:
                        self.memory_manager.clear_memories(user_id)
                        logger.info(f"已清除用户 {user_info['nickname']}({user_id}) 的记忆")
                        return "已清除当前对话的记忆喵~"
                        
        elif cmd == "/chat.whitelist":
            if action == "add":
                if len(parts) < 3:
                    return "请指定要添加的QQ号或群号喵~"
                target = int(parts[2])
                if len(parts) > 3 and parts[3] == "group":
                    self.access_control.add_to_whitelist(group_id=target)
                    return f"已将群 {target} 添加到白名单喵~"
                else:
                    self.access_control.add_to_whitelist(user_id=target)
                    return f"已将用户 {target} 添加到白名单喵~"
            elif action == "remove":
                if len(parts) < 3:
                    return "请指定要移除的QQ号或群号喵~"
                target = int(parts[2])
                if len(parts) > 3 and parts[3] == "group":
                    self.access_control.remove_from_whitelist(group_id=target)
                    return f"已将群 {target} 从白名单移除喵~"
                else:
                    self.access_control.remove_from_whitelist(user_id=target)
                    return f"已将用户 {target} 从白名单移除喵~"
                    
        elif cmd == "/chat.blacklist":
            if action == "add":
                if len(parts) < 3:
                    return "请指定要添加的QQ号或群号喵~"
                target = int(parts[2])
                if len(parts) > 3 and parts[3] == "group":
                    self.access_control.add_to_blacklist(group_id=target)
                    return f"已将群 {target} 添加到黑名单喵~"
                else:
                    self.access_control.add_to_blacklist(user_id=target)
                    return f"已将用户 {target} 添加到黑名单喵~"
            elif action == "remove":
                if len(parts) < 3:
                    return "请指定要移除的QQ号或群号喵~"
                target = int(parts[2])
                if len(parts) > 3 and parts[3] == "group":
                    self.access_control.remove_from_blacklist(group_id=target)
                    return f"已将群 {target} 从黑名单移除喵~"
                else:
                    self.access_control.remove_from_blacklist(user_id=target)
                    return f"已将用户 {target} 从黑名单移除喵~"
                    
        elif cmd == "/chat.access":
            if action == "whitelist":
                if len(parts) > 2:
                    enable = parts[2].lower() == "on"
                    self.access_control.whitelist_enabled = enable
                    return f"已{'启用' if enable else '禁用'}白名单喵~"
            elif action == "blacklist":
                if len(parts) > 2:
                    enable = parts[2].lower() == "on"
                    self.access_control.blacklist_enabled = enable
                    return f"已{'启用' if enable else '禁用'}黑名单喵~"
            elif action == "control":
                if len(parts) > 2:
                    enable = parts[2].lower() == "on"
                    self.access_control.enabled = enable
                    return f"已{'启用' if enable else '禁用'}访问控制喵~"
                    
        elif cmd == "/chat.debug":
            if action == "on":
                self.debug_enabled = True
                logger.info(f"用户 {user_info['nickname']}({user_id}) 启用了调试模式")
                return "已启用调试模式喵~"
            elif action == "off":
                self.debug_enabled = False
                logger.info(f"用户 {user_info['nickname']}({user_id}) 禁用了调试模式")
                return "已禁用调试模式喵~"
            elif action == "status":
                status = "启用" if self.debug_enabled else "禁用"
                return f"调试模式当前已{status}喵~"
                
        return "未知的命令喵~"

    async def _handle_chat(self, content: str, group_id: Optional[int], user_id: int, is_group: bool = False) -> str:
        try:
            user_info = await self._get_user_info(user_id)
            nickname = user_info.get("nickname", str(user_id))
            
            if group_id:
                logger.info(f"群 {group_id} 中用户 {user_id}({nickname}) 发送消息: {content}")
            else:
                logger.info(f"用户 {user_id}({nickname}) 发送私聊消息: {content}")
            
            memories = None
            if self.memory_enabled:
                memories = self.memory_manager.load_memories(user_id, group_id)
            
            messages = []
            
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            
            if memories:
                memories_text = self.memory_manager.format_memories_for_prompt(memories)
                messages.append({"role": "system", "content": f"以下是与用户的历史对话记录:\n{memories_text}"})
            
            messages.append({"role": "user", "content": content})
            
            try:
                response = await self._generate_response(messages)
                
                if self.memory_enabled:
                    self.memory_manager.save_memory(user_id, "user", content, group_id)
                    self.memory_manager.save_memory(user_id, "assistant", response, group_id)
                    
                return response
            except Exception as e:
                logger.error(f"处理用户 {user_id} 的消息时出错: {e}")
                return "抱歉，处理您的消息时出现错误喵~"
        except Exception as e:
            logger.error(f"处理用户 {user_id} 的消息时出错: {e}")
            return "抱歉，处理您的消息时出现错误喵~"
        
    async def _generate_response(self, messages: List[Dict[str, str]]) -> str:
        start_time = None
        response_text = None
        
        try:
            if self.debug_enabled:
                import time
                start_time = time.time()
                logger.debug(f"开始生成回复，消息数: {len(messages)}")
                for i, msg in enumerate(messages):
                    logger.debug(f"消息 {i+1}: [角色: {msg['role']}] {msg['content'][:50]}...")
            else:
                import time
                start_time = time.time()
            
            config = self.bot.config["features"]["chat"]
            
            api_key = None
            provider = config.get("provider", "openrouter")
            
            if provider == "openrouter" and "openrouter" in config:
                api_key = config["openrouter"].get("api_key", "")
                model = config["openrouter"].get("model", "gpt-3.5-turbo")
                logger.info(f"使用 OpenRouter 提供商，模型: {model}")
            elif provider == "openai" and "openai" in config:
                api_key = config["openai"].get("api_key", "")
                model = config["openai"].get("model", "gpt-3.5-turbo")
                logger.info(f"使用 OpenAI 提供商，模型: {model}")
            else:
                api_key = config.get("api_key", "")
                model = config.get("model", "gpt-3.5-turbo")
                logger.info(f"使用默认提供商，模型: {model}")
            
            if not api_key:
                logger.warning(f"未配置 {provider} API 密钥，使用默认回复")
                logger.debug(f"当前配置: {config}")
                return "我还没有配置好 AI 接口，请稍后再试喵~"
                
            logger.info(f"使用模型 {model} 生成回复")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": messages
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post("https://openrouter.ai/api/v1/chat/completions", 
                                      headers=headers, 
                                      json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"OpenRouter API 调用失败: {resp.status}, {error_text}")
                        return "抱歉，与 AI 通信时出现错误喵~"
                        
                    result = await resp.json()
                    
                    if "choices" not in result or not result["choices"]:
                        logger.error(f"OpenRouter API 返回了无效的响应: {result}")
                        return "抱歉，AI 返回了无效的回复喵~"
                        
                    response_text = result["choices"][0]["message"]["content"]
                    
                    import time
                    elapsed_time = time.time() - start_time
                    prompt_tokens = result.get("usage", {}).get("prompt_tokens", 0)
                    completion_tokens = result.get("usage", {}).get("completion_tokens", 0)
                    total_tokens = result.get("usage", {}).get("total_tokens", 0)
                    
                    self.session_stats["total_time"] += elapsed_time
                    self.session_stats["prompt_tokens"] += prompt_tokens
                    self.session_stats["completion_tokens"] += completion_tokens
                    self.session_stats["total_tokens"] += total_tokens
                    self.session_stats["requests_count"] += 1
                    
                    if self.debug_enabled:
                        logger.debug("=" * 40)
                        logger.debug("AI 回复详情:")
                        logger.debug(f"内容: {response_text}")
                        logger.debug(f"耗时: {elapsed_time:.2f}秒")
                        logger.debug(f"Token 统计:")
                        logger.debug(f"  - 提示词 tokens: {prompt_tokens}")
                        logger.debug(f"  - 回复 tokens: {completion_tokens}")
                        logger.debug(f"  - 总 tokens: {total_tokens}")
                        logger.debug(f"  - 估计费用: ${total_tokens/1000 * 0.002:.5f}")
                        logger.debug("=" * 40)
                    
                    return response_text
        except Exception as e:
            logger.error(f"生成回复时出错: {e}")
            return "抱歉，与 AI 通信时出现错误喵~"
        finally:
            if start_time and not response_text:
                import time
                elapsed_time = time.time() - start_time
                if self.debug_enabled:
                    logger.debug(f"生成回复失败，耗时: {elapsed_time:.2f}秒")
        
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        text = ""
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
        
        if text.startswith("/chat."):
            if not await self._is_admin_command(user_id):
                await self.bot.api.send_group_msg(group_id=group_id, message="你没有权限使用此命令")
                return
            reply = await self._handle_admin_command(text, group_id, user_id)
            await self.bot.api.send_group_msg(group_id=group_id, message=reply)
            return
        
        config = self.bot.config["features"]["chat"]["access_control"]
        allowed_groups = config.get("allowed_groups", [])
        if allowed_groups and group_id not in allowed_groups:
            logger.warning(f"群 {group_id} 不在允许列表中，忽略消息")
            return
        
        if self.access_control.enabled and not self.access_control.can_access(user_id, group_id):
            logger.warning(f"群 {group_id} 或用户 {user_id} 在黑名单中，忽略消息")
            return
        
        if text and text.startswith("!"):
            content = text[1:].strip()
            if content:
                reply = await self._handle_chat(content, group_id, user_id, is_group=True)
                await self.bot.api.send_group_msg(group_id=group_id, message=f"[CQ:at,qq={user_id}]\n{reply}")
        
    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        text = ""
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
            
        if text.startswith("/chat."):
            if not await self._is_admin_command(user_id):
                await self.bot.api.send_private_msg(user_id=user_id, message="你没有权限使用此命令")
                return
            reply = await self._handle_admin_command(text, None, user_id)
            await self.bot.api.send_private_msg(user_id=user_id, message=reply)
            return
        
        config = self.bot.config["features"]["chat"]["access_control"]
        allowed_friends = config.get("allowed_friends", [])
        if allowed_friends and user_id not in allowed_friends:
            logger.warning(f"用户 {user_id} 不在允许列表中，忽略消息")
            return
        
        if self.access_control.enabled and not self.access_control.can_access(user_id):
            logger.warning(f"用户 {user_id} 在黑名单中，忽略消息")
            return
        
        if text and text.startswith("!"):
            content = text[1:].strip()
            if content:
                reply = await self._handle_chat(content, None, user_id, is_group=False)
                await self.bot.api.send_private_msg(user_id=user_id, message=reply)

    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        if command == "clear_memory":
            return await self._clear_memory_command(user_id, group_id)
        return f"未知的命令: {command}"
    
    async def _clear_memory_command(self, user_id: int, group_id: Optional[int] = None) -> str:
        if not self.memory_enabled:
            return "记忆功能未启用喵~"
        
        try:
            self.memory_manager.clear_memories(user_id, group_id)
            
            if group_id:
                logger.info(f"已清除群 {group_id} 中用户 {user_id} 的记忆")
                return "已清除本群中与你的聊天记忆喵~"
            else:
                logger.info(f"已清除用户 {user_id} 的私聊记忆")
                return "已清除与你的私聊记忆喵~"
        except Exception as e:
            logger.error(f"清除记忆时出错: {e}")
            return "清除记忆时出现错误喵，请稍后再试~" 