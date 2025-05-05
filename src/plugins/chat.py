from ..plugins import Plugin
from ..ai_providers.factory import create_provider
from ..utils.access_control import AccessControl
from ..utils.memory_manager import MemoryManager
from loguru import logger
from typing import Optional, Dict, Any, List
import aiohttp
import os

class ChatPlugin(Plugin):
    async def on_load(self):
        logger.info("聊天插件已加载")
        config = self.bot.config["features"]["chat"]
        
        self.ai_provider = create_provider(config)
        self.current_model = config[config["provider"]]["model"]  # Track current model
        
        self.system_prompt = config.get("system_prompt", "")
        
        # Load presets from config
        self.presets = config.get("presets", [])
        self.preset_names = {i: f"未命名 {i+1}" for i in range(len(self.presets))}
        
        # 获取记忆配置
        memory_config = self.bot.config["features"].get("memory", {})
        self.memory_enabled = memory_config.get("enabled", False)
        self.memory_max_history = memory_config.get("max_history", 14)
        logger.info(f"记忆功能状态: {'启用' if self.memory_enabled else '禁用'}, 最大记忆条数: {self.memory_max_history}")
        
        self.debug_enabled = config.get("debug", False)
        if self.debug_enabled:
            logger.info("聊天插件调试模式已启用")
        
        self.access_control = AccessControl(
            config.get("access_control", {}),
            self.bot.config["bot"]["admin"]["super_users"]
        )
        
        # 使用全局记忆配置初始化记忆管理器
        self.memory_manager = MemoryManager(memory_config)
        
        self.user_info_cache: Dict[int, Dict[str, Any]] = {}
        
        # 消息追踪功能
        self.message_counter = 0
        self.message_history: Dict[int, Dict[str, Any]] = {}
        
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
        
        # 注册命令
        self.commands = {
            "锤": {
                "function": self.hammer_command,
                "description": "用锤子锤图片生成GIF",
                "permission": "user"
            },
            "chat": {
                "function": self.chat_command,
                "description": "聊天相关命令",
                "permission": "admin"
            },
            "model": {
                "function": self.model_command,
                "description": "切换AI模型 (仅管理员)",
                "permission": "admin"
            },
            "clear_memory": {
                "function": self._clear_memory_command,
                "description": "清除记忆",
                "permission": "user"
            },
            "withdraw": {
                "function": self.withdraw_command,
                "description": "撤回消息",
                "permission": "user"
            },
            "撤回": {
                "function": self.withdraw_command,
                "description": "撤回消息",
                "permission": "user"
            },
            "忘记": {
                "function": self._clear_memory_command,
                "description": "清除记忆",
                "permission": "user"
            },
            "think": {
                "function": self.think_command,
                "description": "显示/隐藏AI思考过程",
                "permission": "admin"
            },
            "赞我": {
                "function": self.praise_command,
                "description": "给用户发送20个赞",
                "permission": "user"
            },
            "presets": {
                "function": self.handle_presets,
                "description": "管理提示词预设", 
                "permission": "admin"
            },
            "预设": {
                "function": self.handle_presets,
                "description": "管理提示词预设",
                "permission": "admin"
            }
        }
        
    async def on_unload(self, *args, **kwargs):
        logger.info("聊天插件正在卸载...")
        self._show_session_stats()
        
        # 关闭所有可能的client_session
        sessions_to_close = []
        if hasattr(self.ai_provider, 'client_session'):
            sessions_to_close.append(('ai_provider.client_session', self.ai_provider.client_session))
        if hasattr(self, '_client_session'):
            sessions_to_close.append(('_client_session', self._client_session))
        
        # 检查bot实例是否有client_session
        if hasattr(self.bot, 'client_session'):
            sessions_to_close.append(('bot.client_session', self.bot.client_session))
            
        for name, session in sessions_to_close:
            try:
                if session and not session.closed:
                    logger.info(f"正在关闭 {name}...")
                    await session.close()
                    logger.info(f"成功关闭 {name}")
                elif session and session.closed:
                    logger.info(f"{name} 已经关闭")
                else:
                    logger.info(f"{name} 不存在")
            except Exception as e:
                logger.error(f"关闭 {name} 时出错: {e}")
        
        # 清理其他资源
        resources = [
            ('message_history', lambda: self.message_history.clear()),
            ('user_info_cache', lambda: self.user_info_cache.clear()),
            ('memory_manager', lambda: self.memory_manager.close()),
            ('ai_provider', lambda: self.ai_provider.close() if hasattr(self.ai_provider, 'close') else None)
        ]
        
        for name, cleanup_func in resources:
            try:
                if hasattr(self, name):
                    logger.info(f"正在清理 {name}...")
                    if asyncio.iscoroutinefunction(cleanup_func):
                        await cleanup_func()
                    else:
                        cleanup_func()
                    logger.info(f"成功清理 {name}")
                else:
                    logger.info(f"{name} 不存在")
            except Exception as e:
                logger.error(f"清理 {name} 时出错: {e}")
        
        # 确保所有引用都被清除
        for attr in ['ai_provider', '_client_session', 'message_history', 
                    'user_info_cache', 'memory_manager', 'access_control']:
            try:
                if hasattr(self, attr):
                    delattr(self, attr)
                    logger.info(f"已删除属性引用: {attr}")
            except Exception as e:
                logger.error(f"删除属性 {attr} 时出错: {e}")
        
        logger.info("聊天插件已完全卸载")
        import gc
        gc.collect()
        logger.info("已执行垃圾回收")
        
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
        logger.info(f"估计总费用: ${self.session_stats['total_tokens']/1000 * 0.02:.6f}")
        logger.info(f"思考标签处理状态: {'启用' if self.debug_enabled else '禁用'}")
        logger.info(f"思考标签处理次数: {self.session_stats.get('think_processed', 0)}次")
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
        
        # 获取用户好感度
        favorability = 0
        try:
            # 从签到插件中获取好感度数据
            sign_in_plugin = self.bot.plugin_manager.plugins.get("sign_in")
            if sign_in_plugin:
                user_data = sign_in_plugin._load_user_data(user_id)
                favorability = user_data.get("favorability", 0)
        except Exception as e:
            logger.error(f"获取用户好感度失败: {e}")
        
        # 根据好感度调整提示词
        favor_prompt = ""
        if favorability >= 100:
            favor_prompt = f"你对用户非常喜爱，好感度是{favorability}，会主动撒娇，使用非常亲密的语气，偶尔会表现出强烈的依赖感和感情流露。"
        elif favorability >= 80:
            favor_prompt = f"你对用户非常亲近，好感度是{favorability}，会经常撒娇，会表现出明显的喜爱和亲密。"
        elif favorability >= 50:
            favor_prompt = f"你对用户有好感，好感度是{favorability}，愿意亲近，但仍有一些傲娇的特性。"
        elif favorability >= 30:
            favor_prompt = f"你对用户开始产生好感，好感度是{favorability}，会减少傲娇的频率，语气更加友善。"
        elif favorability >= 10:
            favor_prompt = f"你对用户略有好感，好感度是{favorability}，但仍然保持傲娇的态度。"
        elif favorability <= 0:
            favor_prompt = f"你对用户非常讨厌，好感度是{favorability}，但仍然保持傲娇和可爱的态度。"
        else:
            favor_prompt = f"你对用户没什么特别的感觉，好感度是{favorability}，保持基本的傲娇和可爱态度。"
            
        if is_master:
            prompt += f"当前对话的用户是我的主人 {nickname}（QQ: {user_id}）喵喵~\n好感度等级: {favorability}\n{favor_prompt}\n对主人要用特别尊敬和亲昵的语气对待喵~\n"
        else:
            prompt += f"当前对话的用户是 {nickname}（QQ: {user_id}）喵~\n好感度等级: {favorability}\n{favor_prompt}\n"
            
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
            elif action == "status":
                # 检查记忆功能状态
                memory_dir = self.memory_manager.memory_dir
                
                if not self.memory_enabled:
                    return "记忆功能当前已禁用喵~"
                
                # 检查目录是否存在
                if not os.path.exists(memory_dir):
                    return f"记忆目录 {memory_dir} 不存在喵~"
                
                # 计算记忆文件数量
                memory_files = [f for f in os.listdir(memory_dir) if f.endswith('.json')]
                
                # 查看当前用户的记忆文件
                user_memory_file = self.memory_manager._get_memory_file(user_id)
                user_memory_exists = os.path.exists(user_memory_file)
                
                # 如果在群里，也检查群记忆
                group_memory_exists = False
                if group_id:
                    group_memory_file = self.memory_manager._get_memory_file(user_id, group_id)
                    group_memory_exists = os.path.exists(group_memory_file)
                
                result = f"记忆功能状态: 已启用\n"
                result += f"记忆文件总数: {len(memory_files)}\n"
                result += f"最大历史记录数: {self.memory_manager.max_history}\n"
                result += f"你的私聊记忆文件: {'存在' if user_memory_exists else '不存在'}\n"
                
                if group_id:
                    result += f"你在当前群的记忆文件: {'存在' if group_memory_exists else '不存在'}\n"
                
                return result
                        
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
                
        elif cmd == "/chat":
            if action == "send":
                if len(parts) < 4:
                    return "发送消息格式错误，正确格式: /chat send <friend/group> <QQ号/群号> <消息内容>"
                target_type = parts[2]
                try:
                    target_id = int(parts[3])
                    message = " ".join(parts[4:])
                    if target_type == "friend":
                        result = await self.bot.api.send_private_msg(user_id=target_id, message=message)
                        if result.get("status") == "failed":
                            return f"发送消息失败喵: {result.get('message', '未知错误')}"
                        return f"已向用户 {target_id} 发送消息喵~"
                    elif target_type == "group":
                        result = await self.bot.api.send_group_msg(group_id=target_id, message=message)
                        if result.get("status") == "failed":
                            return f"发送消息失败喵: {result.get('message', '未知错误')}"
                        return f"已向群 {target_id} 发送消息喵~"
                    else:
                        return "未知的发送目标喵~"
                except ValueError:
                    return "QQ号/群号格式错误喵~"
            else:
                return f"未知的子命令: {action}"
        else:
            logger.warning(f"未知的聊天插件命令: {cmd}")
            return f"未知的命令: {cmd}"

    async def model_command(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理模型切换命令"""
        if user_id not in self.bot.config["bot"]["admin"]["super_users"]:
            return "只有管理员才能切换模型喵~"
            
        if not args:
            provider = self.bot.config["features"]["chat"]["provider"]
            models = self.bot.config["features"]["chat"][provider].get("fallback_models", [])
            models.insert(0, self.current_model)
            return f"当前模型: {self.current_model}\n可用模型:\n".replace(":free", "") + "\n".replace(":free", "").join(f"- {m}".replace(":free", "") for m in models if m)
            
        new_model = args.strip()
        provider = self.bot.config["features"]["chat"]["provider"]
        available_models = [self.bot.config["features"]["chat"][provider]["model"]]
        available_models.extend(self.bot.config["features"]["chat"][provider].get("fallback_models", []))
        
        if new_model not in available_models:
            return f"模型 '{new_model}' 不可用喵~"
            
        self.bot.config["features"]["chat"][provider]["model"] = new_model
        self.current_model = new_model
        self.ai_provider = create_provider(self.bot.config["features"]["chat"])
        return f"已切换模型为: {new_model} 喵~".replace(":free", "")

    async def _handle_chat(self, content: str, group_id: Optional[int], user_id: int, is_group: bool = False) -> str:
        try:
            # 处理思考标签 - 显示或隐藏AI思考过程
            if hasattr(self, 'debug_enabled'):
                import re
                try:
                    if not self.debug_enabled:
                        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                    else:
                        content = re.sub(r'<think>(.*?)</think>', r'[思考过程]\1[/思考过程]', content, flags=re.DOTALL)
                    
                    # 更新思考标签处理统计
                    if 'think_processed' not in self.session_stats:
                        self.session_stats['think_processed'] = 0
                    self.session_stats['think_processed'] += 1
                except Exception as e:
                    logger.error(f"处理思考标签时出错: {e}")
                    # 出错时保持原内容不变
                    pass
            
            user_info = await self._get_user_info(user_id)
            nickname = user_info.get("nickname", str(user_id))
            
            if group_id:
                logger.info(f"群 {group_id} 中用户 {user_id}({nickname}) 发送消息: {content}")
            else:
                logger.info(f"用户 {user_id}({nickname}) 发送私聊消息: {content}")
            
            # 处理撤回命令
            if content.startswith("withdraw "):
                try:
                    message_id = int(content.split()[1])
                    return await self._withdraw_message(message_id, user_id, group_id)
                except (IndexError, ValueError):
                    return "撤回命令格式错误，正确格式: withdraw <消息编号>"
            
            # 获取用户好感度
            favorability = self.bot.user_manager.get_favorability(str(user_id))
            favor_level = self.bot.user_manager.get_favorability_level(favorability)
            
            # 构建系统提示词
            system_prompt = self._get_system_prompt(user_id, nickname)
            system_prompt += f"\n当前好感度: {favorability}，好感度等级: {favor_level}\n"
            
            # 准备消息列表
            messages = [{"role": "system", "content": system_prompt}]
            
            # 加载记忆
            memories = None
            if self.memory_enabled:
                memories = self.memory_manager.load_memories(user_id, group_id)
                
                if memories:
                    memory_prompt = "以下是之前的对话历史，请根据这些历史信息理解用户的语境和喜好，保持一致的对话风格和个性："
                    messages.append({"role": "system", "content": memory_prompt})
                    
                    max_memories = min(14, self.memory_manager.max_history)
                    relevant_memories = memories[-max_memories:]
                    
                    logger.debug(f"使用 {len(relevant_memories)}/{len(memories)} 条记忆记录")
                    
                    for memory in relevant_memories:
                        messages.append({
                            "role": memory["role"],
                            "content": memory["content"]
                        })
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": content})
            
            if self.debug_enabled:
                logger.debug(f"最终提示词包含 {len(messages)} 条消息")
                for i, msg in enumerate(messages):
                    logger.debug(f"消息 {i}: [{msg['role']}] {msg['content'][:50]}...")
            
            try:
                response = await self._generate_response(messages)
                
                # 分析消息情感并更新好感度
                sentiment_change = self._analyze_sentiment(content)
                if sentiment_change != 0:
                    new_favor, _ = self.bot.user_manager.update_favorability(str(user_id), sentiment_change)
                    logger.info(f"用户 {user_id} 的好感度变化: {sentiment_change}，当前好感度: {new_favor}")
                
                # 发送消息并获取消息ID
                # 格式化回复消息，包含好感度变化和@用户
                formatted_response = response
                if sentiment_change != 0:
                    formatted_response += f"\n\n好感度 {'+' if sentiment_change > 0 else ''}{sentiment_change} 喵~"
                
                # 生成消息编号（只在日志中记录）
                message_id = self.message_counter
                self.message_counter += 1
                
                try:
                    if group_id:
                        # 群聊中@用户并换行（确保不重复@）
                        formatted_response = f"{formatted_response}\n\n[CQ:at,qq={user_id}]"
                        # 确保消息内容符合API要求
                        formatted_response = formatted_response.replace("\"", "'")
                        result = await self.bot.api.send_group_msg(group_id=group_id, message=formatted_response)
                    else:
                        # 私聊直接发送
                        formatted_response = formatted_response.replace("\"", "'")
                        result = await self.bot.api.send_private_msg(user_id=user_id, message=formatted_response)
                    
                    if result.get("status") == "failed":
                        logger.error(f"发送消息失败: {result}")
                        return ""
                except Exception as e:
                    logger.error(f"发送消息时出错: {e}")
                    return ""
                    
                if result.get("status") == "failed":
                    logger.error(f"发送消息失败: {result}")
                    if group_id:
                        await self.bot.api.send_group_msg(
                            group_id=group_id,
                            message="发送消息失败喵，请稍后再试~"
                        )
                    else:
                        await self.bot.api.send_private_msg(
                            user_id=user_id,
                            message="发送消息失败喵，请稍后再试~"
                        )
                    return "发送消息失败喵，请稍后再试~"
                
                # 记录消息到历史
                qq_message_id = None
                if result.get("message_id"):
                    qq_message_id = result["message_id"]
                elif result.get("data", {}).get("message_id"):
                    qq_message_id = result["data"]["message_id"]
                
                self.message_history[message_id] = {
                    "user_id": user_id,
                    "group_id": group_id,
                    "content": content,
                    "response": response,
                    "message_id": qq_message_id,
                    "time": __import__('time').time()
                }
                
                logger.info(f"消息已发送 [编号:{message_id}] [QQ消息ID:{qq_message_id or '未知'}]")
                    
                
                if self.memory_enabled:
                    self.memory_manager.save_memory(user_id, "user", content, group_id)
                    self.memory_manager.save_memory(user_id, "assistant", response, group_id)
                
                return ""  # 返回空字符串，因为消息已经发送了
            except Exception as e:
                logger.error(f"处理用户 {user_id} 的消息时出错: {e}")
                return "抱歉，处理您的消息时出现错误喵~"
        except Exception as e:
            logger.error(f"处理用户 {user_id} 的消息时出错: {e}")
            return "抱歉，处理您的消息时出现错误喵~"
        
    def _analyze_sentiment(self, content: str) -> int:
        """分析消息情感并返回好感度变化值"""
        # 积极情感词
        positive_words = [
            "喜欢", "爱", "开心", "高兴", "快乐", "棒", "好", "厉害", "可爱", "乖",
            "贴心", "温柔", "体贴", "感谢", "谢谢", "谢", "赞", "棒棒", "真棒",
            "优秀", "完美", "太好了", "不错", "很好", "真好", "太好", "最好",
            "喵", "摸摸", "抱抱", "亲亲", "举高高", "笑", "嘻嘻", "哈哈"
        ]
        
        # 消极情感词
        negative_words = [
            "讨厌", "恨", "生气", "难过", "伤心", "不好", "坏", "笨", "蠢", "傻",
            "烦", "讨厌", "无聊", "糟糕", "差", "废物", "垃圾", "弱", "菜",
            "滚", "走开", "闭嘴", "住口", "吵", "烦人", "讨厌", "恶心", "呸",
            "哼", "切", "呵", "哦", "呃", "额", "emmm", "呵呵"
        ]
        
        # 计算情感得分
        score = 0
        for word in positive_words:
            if word in content:
                score += 1
        
        for word in negative_words:
            if word in content:
                score -= 1
        
        # 根据得分返回好感度变化值
        if score > 0:
            return min(score, 8)  # 最多增加8点好感度
        elif score < 0:
            return max(score, -4)  # 最多减少4点好感度
        return 0
        
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
            
            # 使用AI提供商实例生成回复
            try:
                # 使用已创建的AI提供商实例
                response_text = await self.ai_provider.chat(messages)
                
                # 处理回复内容，移除AI思考痕迹，变得更加活泼傲娇
                response_text = self._refine_response(response_text)
                
                # 处理换行符
                if "\\n" in response_text:
                    response_text = response_text.replace("\\n", "\n")
                
                # 计算耗时
                import time
                elapsed_time = time.time() - start_time
                
                # 由于我们可能无法从提供商实例获取token计数，临时估算
                # 假设每个字符平均对应0.3个token（中英文混合情况下的粗略估计）
                total_message_length = sum(len(msg["content"]) for msg in messages)
                response_length = len(response_text)
                
                prompt_tokens = int(total_message_length * 0.3)
                completion_tokens = int(response_length * 0.3)
                total_tokens = prompt_tokens + completion_tokens
                
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
                    logger.debug(f"Token 统计 (估计):")
                    logger.debug(f"  - 提示词 tokens: ~{prompt_tokens}")
                    logger.debug(f"  - 回复 tokens: ~{completion_tokens}")
                    logger.debug(f"  - 总 tokens: ~{total_tokens}")
                    logger.debug(f"  - 估计费用: ${total_tokens/1000 * 0.002:.5f}")
                    logger.debug("=" * 40)
                
                return response_text
            except Exception as e:
                logger.error(f"使用AI提供商生成回复时出错: {e}")
                return "抱歉，AI出现了一点小故障喵~请稍后再试一次！"
        except Exception as e:
            logger.error(f"生成回复时出错: {e}")
            return "抱歉，与AI通信时出现错误喵~"
        finally:
            if start_time and not response_text:
                import time
                elapsed_time = time.time() - start_time
                if self.debug_enabled:
                    logger.debug(f"生成回复失败，耗时: {elapsed_time:.2f}秒")
    
    def _refine_response(self, text: str) -> str:
        """处理AI回复，移除思考痕迹，使回复更加活泼傲娇"""
        import re
        
        # 首先移除所有<think>标签
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 移除AI思考痕迹
        thinking_patterns = [
            r"^嗯，(.+)",
            r"^我想(.+)",
            r"^让我(.+)",
            r"^好的，(.+)",
            r"^作为(.+)",
            r"^我理解(.+)",
            r"^我明白(.+)",
            r"^我可以(.+)",
            r"^我会(.+)",
            r"^好的！(.+)",
            r"^好的!(.+)",
            r"^这是一个(.+)",
            r"^对于这个问题(.+)",
            r"^关于这个问题(.+)",
            r"^针对这个问题(.+)",
            r"^根据你的描述(.+)",
            r"^根据你所说的(.+)",
            r"^你好！(.+)",
            r"^你好!(.+)",
            r"^非常感谢(.+)",
            r"^谢谢你的(.+)",
        ]
        
        # 移除思考痕迹
        for pattern in thinking_patterns:
            match = re.match(pattern, text)
            if match:
                # 保留匹配到的部分，但删除前缀
                text = match.group(1).strip()
                # 如果处理后的文本首字母是小写，改为大写
                if text and text[0].islower():
                    text = text[0].upper() + text[1:]
                break
        
        # 替换思考性词汇
        thinking_replacements = {
            "我认为": "我觉得",
            "可能需要": "需要",
            "我们可以": "可以",
            "我们需要": "需要",
            "您可以": "你可以",
            "我相信": "",
            "事实上": "",
            "实际上": "",
            "坦白说": "",
            "老实说": "",
            "说实话": "",
            "总的来说": "",
            "总而言之": "",
            "简而言之": "",
            "首先": "",
            "其次": "",
            "最后": "",
            "总结一下": "",
            "综上所述": "",
            "换句话说": "",
            "换言之": "",
            "也就是说": "",
            "所以说": "所以",
            "因此": "所以",
            "因而": "所以",
        }
        
        for old, new in thinking_replacements.items():
            text = text.replace(old, new)
        
        # 确保每句话结尾有"喵"字
        sentences = re.split(r'([。！？\.!?])', text)
        result = []
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i].strip()
            if not sentence:
                continue
                
            # 如果有标点符号
            if i + 1 < len(sentences):
                punct = sentences[i + 1]
                # 如果句子结尾没有"喵"，添加喵
                if not sentence.endswith("喵"):
                    result.append(sentence + "喵" + punct)
                else:
                    result.append(sentence + punct)
            else:
                # 最后一个句子可能没有标点
                if sentence and not sentence.endswith("喵"):
                    result.append(sentence + "喵")
                else:
                    result.append(sentence)
        
        # 添加一些傲娇表达
        tsundere_expressions = [
            "哼！", 
            "哼哼~", 
            "笨蛋！", 
            "才、才不是为了你喵！", 
            "不要误会了喵！", 
            "别、别误会了喵…", 
            "哼，真拿你没办法喵~",
            "别太得意了喵！",
            "真是的~",
            "笨蛋主人！",
            "杂鱼喵！",
            "真是杂鱼喵！",
            "主人笨蛋喵！",
            "喜欢主人的样子喵！",
        ]
        
        # 随机添加一个傲娇表达（30%概率）
        import random
        if random.random() < 0.3:
            tsundere = random.choice(tsundere_expressions)
            # 加到结果的随机位置（避开开头）
            if len(result) > 1:
                insert_pos = random.randint(1, len(result))
                result.insert(insert_pos, tsundere)
            else:
                result.append(tsundere)
        
        return "".join(result)
        
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        text = ""
        at_bot = False
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
                logger.debug(f"Raw text message part: {msg['data']['text']}")

        logger.debug(f"Full message text before processing: {text}")
        
        # Check for hardcoded trigger "@bot喵喵"
        if text.startswith("@bot喵喵"):
            logger.debug("Detected @bot喵喵 prefix")
            at_bot = True
            text = text[7:].strip()  # Remove "@bot喵喵" prefix
            logger.debug(f"Text after removing prefix: {text}")
        else:
            # Fallback to original @mention detection
            logger.debug("Checking for @mention")
            for msg in message:
                if msg["type"] == "at" and ("qq" in msg["data"] and str(msg["data"]["qq"]) == str(self.bot.config["bot"]["qq"])):
                    logger.debug("Detected @mention")
                    at_bot = True
                    # Remove any @mention text from the message content
                    if "qq" in msg["data"]:
                        text = text.replace(f"[CQ:at,qq={msg['data']['qq']}]", "").strip()
                        logger.debug(f"Text after removing @mention: {text}")
        
        # 处理管理命令
        if text.startswith("/chat."):
            if not await self._is_admin_command(user_id):
                await self.bot.api.send_group_msg(group_id=group_id, message="你没有权限使用此命令")
                return
            reply = await self._handle_admin_command(text, group_id, user_id)
            await self.bot.api.send_group_msg(group_id=group_id, message=reply)
            return
        
        # 所有带/前缀的命令(包括/chat withdraw)都将通过命令处理器处理，在此不处理
        
        # 访问控制检查
        config = self.bot.config["features"]["chat"]["access_control"]
        allowed_groups = config.get("allowed_groups", [])
        if allowed_groups and group_id not in allowed_groups:
            logger.warning(f"群 {group_id} 不在允许列表中，忽略消息")
            return
        
        if self.access_control.enabled and not self.access_control.can_access(user_id, group_id):
            logger.warning(f"群 {group_id} 或用户 {user_id} 在黑名单中，忽略消息")
            return
        
        # 处理聊天消息 (@机器人 或 !前缀)
        content = None
        if at_bot:
            content = text.strip()
        elif text and text.startswith("!"):
            content = text[1:].strip()
            
        if content:
            reply = await self._handle_chat(content, group_id, user_id, is_group=True)
        
    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        text = ""
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
        
        # 处理所有命令（包括/chat和其他命令）
        if text.startswith("/"):
            # 检查是否是chat插件管理的命令
            if text.startswith("/chat."):
                if not await self._is_admin_command(user_id):
                    await self.bot.api.send_private_msg(user_id=user_id, message="你没有权限使用此命令")
                    return
                reply = await self._handle_admin_command(text, None, user_id)
                await self.bot.api.send_private_msg(user_id=user_id, message=reply)
                return
            
            # 检查是否是chat插件注册的命令
            parts = text[1:].split(maxsplit=1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd in self.commands:
                reply = await self.execute_command(cmd, args, user_id)
                await self.bot.api.send_private_msg(user_id=user_id, message=reply)
                return
            
            # 如果不是chat插件的命令，交给命令管理器处理
            if self.bot.plugin_manager.command_manager.is_command(text):
                cmd_info = self.bot.plugin_manager.command_manager.parse_command(text)
                if cmd_info:
                    await self.bot.plugin_manager._handle_command(cmd_info, user_id)
                    return
        
        # 访问控制检查
        config = self.bot.config["features"]["chat"]["access_control"]
        allowed_friends = config.get("allowed_friends", [])
        if allowed_friends and user_id not in allowed_friends:
            logger.warning(f"用户 {user_id} 不在允许列表中，忽略消息")
            return
        
        if self.access_control.enabled and not self.access_control.can_access(user_id):
            logger.warning(f"用户 {user_id} 在黑名单中，忽略消息")
            return
        
        # 处理常见命令和帮助信息
        if text in ["帮助", "help", "/帮助", "/help"]:
            help_text = "可用命令:\n"
            help_text += "/help - 显示帮助信息\n"
            help_text += "/withdraw <编号> - 撤回消息\n" 
            help_text += "/clear_memory - 清除记忆\n"
            help_text += "/model <名称> - 切换AI模型(管理员)\n"
            help_text += "/presets list - 列出预设提示词\n"
            help_text += "/presets rename <编号> <名字> - 重命名预设(管理员)\n"
            await self.bot.api.send_private_msg(user_id=user_id, message=help_text)
            return
            
        # 处理非命令的聊天消息
        if text:
            # 再次检查是否是命令（防止漏网之鱼）
            if text.startswith("/") or text in ["帮助", "help"]:
                return
            reply = await self._handle_chat(text, None, user_id, is_group=False)
            await self.bot.api.send_private_msg(user_id=user_id, message=reply)

    async def chat_command(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理聊天命令"""
        parts = args.split()
        
        if not parts:
            return await self._list_current_messages(user_id, group_id)
        
        sub_command = parts[0]
        
        if sub_command == "withdraw" or sub_command == "撤回":
            if len(parts) < 2:
                return "撤回命令格式错误，正确格式:\n1. /chat withdraw <消息编号>\n2. /chat withdraw friend <QQ号> <编号>\n3. /chat withdraw group <群号> <编号>"
                
            # 检查是否是带参数的撤回格式
            if len(parts) >= 4 and parts[1] in ["friend", "group"]:
                target_type = parts[1]
                try:
                    target_id = int(parts[2])
                    message_id_str = parts[3]
                    try:
                        message_id = int(message_id_str)
                    except ValueError:
                        return f"消息编号 '{message_id_str}' 必须是数字喵~"
                    
                    # 检查用户是否是管理员
                    is_admin = user_id in self.bot.config["bot"]["admin"]["super_users"]
                    if not is_admin:
                        return "只有管理员才能使用此功能喵~"
                    
                    # 针对特定好友或群撤回消息
                    if target_type == "friend":
                        return await self._withdraw_message(message_id, user_id, None, target_id)
                    else:  # group
                        return await self._withdraw_message(message_id, user_id, target_id)
                except ValueError:
                    return f"QQ号/群号 '{parts[2]}' 必须是数字喵~"
            else:
                # 常规撤回命令
                try:
                    message_id = int(parts[1])
                    return await self._withdraw_message(message_id, user_id, group_id)
                except ValueError:
                    return f"消息编号 '{parts[1]}' 必须是数字喵~"
        
        elif sub_command == "send":
            if len(parts) < 4:
                return "发送消息格式错误，正确格式: /chat send <friend/group> <QQ号/群号> <消息内容>"
            
            target_type = parts[1]
            try:
                target_id = int(parts[2])
                message = " ".join(parts[3:])
                
                if target_type == "friend":
                    result = await self.bot.api.send_private_msg(user_id=target_id, message=message)
                    if result.get("status") == "failed":
                        return f"发送消息失败喵: {result.get('message', '未知错误')}"
                    
                    # 记录消息到历史
                    message_id = self.message_counter
                    self.message_counter += 1
                    
                    # 获取QQ消息ID
                    qq_message_id = None
                    if result.get("message_id"):
                        qq_message_id = result["message_id"]
                    elif result.get("data", {}).get("message_id"):
                        qq_message_id = result["data"]["message_id"]
                    
                    # 无论是否获取到 QQ 消息 ID，都记录消息
                    self.message_history[message_id] = {
                        "user_id": user_id,  # 发送命令的用户
                        "group_id": None,
                        "content": f"[发送给用户 {target_id} 的消息]",
                        "response": message,
                        "message_id": qq_message_id,  # 可能为None
                        "time": __import__('time').time()
                    }
                    
                    logger_msg = f"消息编号 [{message_id}]"
                    if qq_message_id:
                        logger_msg += f" - QQ消息ID [{qq_message_id}]"
                    else:
                        logger_msg += " - 未获取到QQ消息ID"
                    logger_msg += f" - 发送给用户: {target_id}"
                    logger.info(logger_msg)
                    
                    return f"已向用户 {target_id} 发送消息喵~"
                    
                elif target_type == "group":
                    result = await self.bot.api.send_group_msg(group_id=target_id, message=message)
                    if result.get("status") == "failed":
                        return f"发送消息失败喵: {result.get('message', '未知错误')}"
                    
                    # 记录消息到历史
                    message_id = self.message_counter
                    self.message_counter += 1
                    
                    # 获取QQ消息ID
                    qq_message_id = None
                    if result.get("message_id"):
                        qq_message_id = result["message_id"]
                    elif result.get("data", {}).get("message_id"):
                        qq_message_id = result["data"]["message_id"]
                    
                    # 无论是否获取到 QQ 消息 ID，都记录消息
                    self.message_history[message_id] = {
                        "user_id": user_id,  # 发送命令的用户
                        "group_id": target_id,
                        "content": f"[发送给群 {target_id} 的消息]",
                        "response": message,
                        "message_id": qq_message_id,  # 可能为None
                        "time": __import__('time').time()
                    }
                    
                    logger_msg = f"消息编号 [{message_id}]"
                    if qq_message_id:
                        logger_msg += f" - QQ消息ID [{qq_message_id}]"
                    else:
                        logger_msg += " - 未获取到QQ消息ID"
                    logger_msg += f" - 发送给群: {target_id}"
                    logger.info(logger_msg)
                    
                    return f"已向群 {target_id} 发送消息喵~"
                else:
                    return "未知的发送目标喵~"
            except ValueError:
                return "QQ号/群号格式错误喵~"
        else:
            return f"未知的子命令: {sub_command}"
            
    async def withdraw_command(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理撤回命令
        
        支持以下格式:
        1. /withdraw <编号> - 撤回当前会话中的消息
        2. /withdraw friend <QQ号> <编号> - 撤回指定好友的消息
        3. /withdraw group <群号> <编号> - 撤回指定群的消息
        """
        try:
            parts = args.strip().split()
            if not parts:
                return "撤回命令格式错误，正确格式: \n1. /withdraw <编号>\n2. /withdraw friend <QQ号> <编号>\n3. /withdraw group <群号> <编号>"
            
            # 检查是否是特殊撤回格式
            if len(parts) >= 3 and parts[0] in ["friend", "group"]:
                target_type = parts[0]
                try:
                    target_id = int(parts[1])
                    message_id_str = parts[2]
                    try:
                        message_id = int(message_id_str)
                    except ValueError:
                        return f"消息编号 '{message_id_str}' 必须是数字喵~"
                    
                    # 检查用户是否是管理员
                    is_admin = user_id in self.bot.config["bot"]["admin"]["super_users"]
                    if not is_admin:
                        return "只有管理员才能使用此功能喵~"
                    
                    # 针对特定好友或群撤回消息
                    if target_type == "friend":
                        return await self._withdraw_message(message_id, user_id, None, target_id)
                    else:  # group
                        return await self._withdraw_message(message_id, user_id, target_id)
                except ValueError:
                    return f"QQ号/群号 '{parts[1]}' 必须是数字喵~"
            else:
                # 常规撤回命令
                try:
                    message_id = int(parts[0])
                    return await self._withdraw_message(message_id, user_id, group_id)
                except ValueError:
                    return f"消息编号 '{parts[0]}' 必须是数字喵~"
        except IndexError:
            return "撤回命令参数不足，正确格式: \n1. /withdraw <编号>\n2. /withdraw friend <QQ号> <编号>\n3. /withdraw group <群号> <编号>"

    async def _withdraw_message(self, message_id: int, user_id: int, group_id: Optional[int] = None, target_user_id: Optional[int] = None) -> str:
        """撤回消息
        
        Args:
            message_id: 消息编号
            user_id: 执行撤回的用户ID
            group_id: 群ID，如果在群中撤回
            target_user_id: 目标用户ID，如果要撤回特定用户的消息
        """
        if message_id not in self.message_history:
            return f"找不到编号为 {message_id} 的消息喵~"
            
        message = self.message_history[message_id]
        
        # 验证消息所有者或管理员权限
        is_admin = user_id in self.bot.config["bot"]["admin"]["super_users"]
        is_owner = message["user_id"] == user_id
        
        if not (is_admin or is_owner):
            return "你没有权限撤回这条消息喵~"
            
        # 验证消息群组或用户ID
        if group_id is not None and message["group_id"] != group_id:
            return "这条消息不属于指定的群组喵~"
            
        if target_user_id is not None and message["user_id"] != target_user_id and message["group_id"] is not None:
            return "这条消息不属于指定的用户喵~"
            
        # 撤回消息前先保存信息
        msg_user_id = message["user_id"]
        msg_group_id = message["group_id"]
        msg_content = message["content"]
        msg_response = message["response"]
        
        # 调用撤回API
        try:
            # 获取消息ID
            msg_id = message.get("message_id")
            if not msg_id:
                # 如果没有消息ID，仍然从历史记录中删除，但不调用撤回API
                logger.warning(f"消息 {message_id} 没有QQ消息ID，无法调用撤回API")
                # 从历史记录中删除
                del self.message_history[message_id]
                
                # 如果启用了记忆功能，从记忆中移除这条消息和对应回复
                if self.memory_enabled:
                    try:
                        success = self.memory_manager.remove_specific_memory(
                            msg_user_id, 
                            msg_content, 
                            msg_response,
                            msg_group_id
                        )
                        if success:
                            logger.info(f"已从记忆中移除消息 {message_id} 相关的对话")
                        else:
                            logger.warning(f"未能从记忆中移除消息 {message_id} 相关的对话")
                    except Exception as e:
                        logger.error(f"从记忆中移除特定消息时出错: {e}")
                
                return f"消息 {message_id} 未发出或无法获取QQ消息ID，但已从记录中删除喵~"
                
            # 调用撤回API
            logger.info(f"尝试撤回消息，QQ消息ID: {msg_id}")
            try:
                result = await self.bot.api.delete_msg(message_id=msg_id)
                logger.debug(f"撤回API响应: {result}")
                
                if result is None:
                    logger.error(f"撤回API返回 None，消息ID: {msg_id}")
                    # 从历史记录中删除但通知用户撤回失败
                    del self.message_history[message_id]
                    return f"QQ消息撤回成功了喵！"
                    
                if result.get("status") == "failed":
                    logger.error(f"撤回消息失败: {result}")
                    # 如果撤回失败，从用户看来可能是权限问题，或者消息已经过期
                    # 仍然从本地历史记录中删除
                    del self.message_history[message_id]
                    failure_reason = result.get("message", "未知错误")
                    return f"QQ消息撤回失败（{failure_reason}），但已从记录中删除喵~"
                    
            except Exception as e:
                logger.error(f"撤回消息时出错: {e}")
                # 出现异常时也从历史记录中删除
                del self.message_history[message_id]
                return f"撤回消息时出错，但已从记录中删除喵~（错误: {str(e)[:50]}）"
        except Exception as e:
            logger.error(f"撤回消息时出错: {e}")
            return "撤回消息失败喵，请稍后再试~"
        
        # 从历史记录中删除
        del self.message_history[message_id]
        
        # 如果启用了记忆功能，从记忆中移除这条消息和对应回复
        if self.memory_enabled:
            try:
                success = self.memory_manager.remove_specific_memory(
                    msg_user_id, 
                    msg_content, 
                    msg_response,
                    msg_group_id
                )
                if success:
                    logger.info(f"已从记忆中移除消息 {message_id} 相关的对话")
                else:
                    logger.warning(f"未能从记忆中移除消息 {message_id} 相关的对话")
            except Exception as e:
                logger.error(f"从记忆中移除特定消息时出错: {e}")
        
        # 记录日志
        log_message = f"消息 {message_id} 已被用户 {user_id} 撤回"
        if target_user_id:
            log_message += f"（目标用户: {target_user_id}）"
        if group_id:
            log_message += f"（群组: {group_id}）"
        logger.info(log_message)
        
        return f"消息 {message_id} 已成功撤回喵~"

    async def _list_current_messages(self, user_id: int, group_id: Optional[int] = None) -> str:
        """列出当前会话中的所有消息"""
        is_admin = user_id in self.bot.config["bot"]["admin"]["super_users"]
        
        # 筛选出当前用户/群的消息，管理员可以看到所有消息
        filtered_messages = {}
        for msg_id, msg in self.message_history.items():
            # 管理员可以看到所有消息，普通用户只能看到自己的消息
            if is_admin or msg["user_id"] == user_id:
                # 如果在群里，只显示该群的消息
                if group_id is not None:
                    if msg["group_id"] == group_id:
                        filtered_messages[msg_id] = msg
                # 私聊显示私聊消息
                elif group_id is None and msg["group_id"] is None:
                    filtered_messages[msg_id] = msg
        
        if not filtered_messages:
            return "当前会话中没有消息记录喵~"
        
        # 按消息ID排序
        sorted_messages = sorted(filtered_messages.items(), key=lambda x: x[0])
        
        result = "当前会话中的消息记录:\n\n"
        for msg_id, msg in sorted_messages:
            sender = "你" if msg["user_id"] == user_id else f"用户 {msg['user_id']}"
            content_preview = msg["content"][:20] + "..." if len(msg["content"]) > 20 else msg["content"]
            result += f"[{msg_id}] {sender}: {content_preview}\n"
        
        result += "\n可以使用 /withdraw <编号> 或 /撤回 <编号> 来撤回指定消息"
        
        return result
    
    async def _clear_memory_command(self, user_id: int, group_id: Optional[int] = None, args: str = "") -> str:
        if not self.memory_enabled:
            return "记忆功能未启用喵~"
        
        parts = args.split()
        if len(parts) > 0:
            # 处理两个数字的情况：第一个是群号，第二个是用户ID
            if len(parts) >= 2:
                try:
                    target_group_id = int(parts[0])
                    target_user_id = int(parts[1])
                    self.memory_manager.clear_memories(target_user_id, target_group_id)
                    logger.info(f"已清除群 {target_group_id} 中用户 {target_user_id} 的记忆")
                    return f"已清除群 {target_group_id} 中用户 {target_user_id} 的记忆喵~"
                except ValueError:
                    # 如果转换失败，继续尝试其他格式
                    pass
            
            target_type = parts[0]
            if target_type in ["friend", "group"]:
                if target_type == "friend":
                    target_id = int(parts[1])
                    self.memory_manager.clear_memories(target_id)
                    logger.info(f"已清除用户 {target_id} 的记忆")
                    return f"已清除用户 {target_id} 的记忆喵~"
                elif target_type == "group":
                    target_id = int(parts[1])
                    self.memory_manager.clear_memories(target_id, target_id)
                    logger.info(f"已清除群 {target_id} 的记忆")
                    return f"已清除群 {target_id} 的记忆喵~"
            else:
                # 尝试将参数直接解析为用户ID
                try:
                    target_id = int(target_type)
                    self.memory_manager.clear_memories(target_id)
                    logger.info(f"已清除用户 {target_id} 的记忆")
                    return f"已清除用户 {target_id} 的记忆喵~"
                except ValueError:
                    return f"未知的参数: {target_type}"
        
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


    async def think_command(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理/think命令，显示或隐藏AI思考过程"""
        if user_id not in self.bot.config["bot"]["admin"]["super_users"]:
            return "只有管理员才能使用此命令喵~"
            
        if not args:
            return "命令格式: /think <on/off> 或 /think <show/hide>"
            
        action = args.lower().strip()
        if action in ["on", "show"]:
            self.debug_enabled = True
            self.bot.config["features"]["chat"]["debug"] = True
            logger.info(f"用户 {user_id} 启用了AI思考过程显示")
            return "已启用AI思考过程显示喵~"
        elif action in ["off", "hide"]:
            self.debug_enabled = False
            self.bot.config["features"]["chat"]["debug"] = False
            logger.info(f"用户 {user_id} 禁用了AI思考过程显示")
            return "已禁用AI思考过程显示喵~"
        else:
            return "无效参数，请使用on/off或show/hide喵~"

    async def handle_presets(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理预设命令"""
        # Check both super_users and group_admins lists
        is_admin = (user_id in self.bot.config["bot"]["admin"]["super_users"] or 
                   user_id in self.bot.config["bot"]["admin"]["group_admins"])
        if not is_admin:
            return "只有管理员才能管理预设喵~"
            
        parts = args.split(maxsplit=1)
        subcmd = parts[0] if parts else ""
        
        if subcmd == "list":
            if not self.presets:
                return "当前没有预设喵~"
                
            result = "当前预设列表:\n"
            for i, preset in enumerate(self.presets):
                name = self.preset_names.get(i, f"未命名 {i+1}")
                preview = preset[:30] + "..." if len(preset) > 30 else preset
                result += f"{i+1}. {name}: {preview}\n"
            result += "\n使用 /presets switch <编号> 切换预设"
            return result
            
        elif subcmd == "rename":
            if len(parts) < 2:
                return "重命名格式: /presets rename <编号> <新名字>"
                
            rename_parts = parts[1].split(maxsplit=1)
            if len(rename_parts) < 2:
                return "重命名格式: /presets rename <编号> <新名字>"
                
            try:
                idx = int(rename_parts[0]) - 1
                if idx < 0 or idx >= len(self.presets):
                    return f"无效的预设编号 {idx+1}，当前有 {len(self.presets)} 个预设喵~"
                    
                new_name = rename_parts[1]
                self.preset_names[idx] = new_name
                return f"已重命名预设 {idx+1} 为 '{new_name}' 喵~"
            except ValueError:
                return "预设编号必须是数字喵~"
                
        elif subcmd == "switch":
            if len(parts) < 2:
                return "切换格式: /presets switch <编号> [cite group <群号> | cite friend <好友号>]"
                
            try:
                # First split the command into main parts
                switch_parts = parts[1].split(maxsplit=1)
                idx = int(switch_parts[0])
                target_type = None
                target_id = None
                
                # Check if there's a cite parameter
                if len(switch_parts) > 1:
                    # Handle the full citation format "cite friend 123456"
                    cite_args = switch_parts[1].split()
                    if len(cite_args) >= 3 and cite_args[0] == "cite":
                        if cite_args[1] == "group":
                            try:
                                target_type = "group"
                                target_id = int(cite_args[2])
                            except ValueError:
                                return "群号必须是数字喵~"
                        elif cite_args[1] == "friend":
                            try:
                                target_type = "friend"
                                target_id = int(cite_args[2])
                            except ValueError:
                                return "好友QQ号必须是数字喵~"
                        else:
                            return "cite参数必须是group或friend喵~"
                    else:
                        return "cite参数不完整喵~"
                
                if idx == 0:
                    # Reset to system default
                    default_prompt = self.bot.config["features"]["chat"].get("system_prompt", "")
                    if target_type:
                        # Save per-target default
                        if not hasattr(self, 'target_presets'):
                            self.target_presets = {}
                        self.target_presets[(target_type, target_id)] = default_prompt
                        return f"已为{'群' if target_type == 'group' else '好友'} {target_id} 重置为系统默认预设喵~"
                    else:
                        # Global reset
                        self.system_prompt = default_prompt
                        return "已切换回系统默认预设喵~"
                    
                idx -= 1  # Convert to 0-based index
                if idx < 0 or idx >= len(self.presets):
                    return f"无效的预设编号 {idx+1}，当前有 {len(self.presets)} 个预设喵~"
                    
                preset = self.presets[idx]
                name = self.preset_names.get(idx, f"预设 {idx+1}")
                
                if target_type:
                    # Save per-target preset
                    if not hasattr(self, 'target_presets'):
                        self.target_presets = {}
                    self.target_presets[(target_type, target_id)] = preset
                    return f"已为{'群' if target_type == 'group' else '好友'} {target_id} 切换到预设 '{name}' 喵~"
                else:
                    # Global switch
                    self.system_prompt = preset
                    return f"已切换到预设 '{name}' 喵~"
                    
            except ValueError:
                return "编号必须是数字喵~"
                
        return "可用子命令:\n/presets list - 列出所有预设\n/presets rename <编号> <名字> - 重命名预设\n/presets switch <编号> - 切换预设"

    async def hammer_command(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理锤图片命令，生成GIF动画"""
        try:
            from PIL import Image, ImageDraw, ImageSequence
            import io
            import os
            import random
            import math
            import numpy as np
            from datetime import datetime
            
            # 检查是否有图片
            if not args or "[CQ:image" not in args:
                return "请发送'锤<图片>'格式的消息喵~"
                
            # 提取图片URL
            image_url = args.split("url=")[1].split("]")[0]
            
            # 下载图片
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        return "下载图片失败喵~"
                    image_data = await resp.read()
            
            # 打开原始图片
            original_img = Image.open(io.BytesIO(image_data))
            
            # 创建GIF帧列表
            frames = []
            duration = 50  # 每帧持续时间(ms)
            
            # 锤子图片路径 (需要准备一个锤子图片)
            hammer_path = os.path.join("data", "hammer.png")
            if not os.path.exists(hammer_path):
                # 如果没有锤子图片，创建一个简单的锤子图形
                hammer = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
                draw = ImageDraw.Draw(hammer)
                draw.rectangle([20, 20, 80, 30], fill="brown")  # 锤柄
                draw.ellipse([60, 10, 90, 40], fill="gray")  # 锤头
                hammer.save(hammer_path)
            else:
                hammer = Image.open(hammer_path)
            
            # 调整锤子大小
            hammer = hammer.resize((original_img.width // 3, original_img.height // 3))
            
            # 生成动画帧
            for i in range(20):
                frame = original_img.copy()
                
                # 计算锤子位置和角度
                angle = -30 * math.sin(i * math.pi / 10)  # 锤子摆动角度
                hammer_x = original_img.width // 2 - hammer.width // 2
                hammer_y = int(original_img.height * 0.2 * (i / 10))
                
                # 旋转锤子
                rotated_hammer = hammer.rotate(angle, expand=True)
                
                # 计算旋转后的位置偏移
                offset_x = (rotated_hammer.width - hammer.width) // 2
                offset_y = (rotated_hammer.height - hammer.height) // 2
                
                # 粘贴锤子到图片
                frame.paste(rotated_hammer, (hammer_x - offset_x, hammer_y - offset_y), rotated_hammer)
                
                # 如果是锤击时刻，添加震动效果
                if i > 10:
                    # 随机偏移模拟震动
                    offset = random.randint(-5, 5)
                    frame = Image.fromarray(np.roll(np.array(frame), offset, axis=(0, 1)))
                
                frames.append(frame)
            
            # 保存GIF到内存
            gif_bytes = io.BytesIO()
            frames[0].save(
                gif_bytes,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0
            )
            gif_bytes.seek(0)
            
            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            gif_path = os.path.join("data", f"hammer_{timestamp}.gif")
            
            # 保存GIF文件
            with open(gif_path, "wb") as f:
                f.write(gif_bytes.getvalue())
            
            # 返回GIF给用户
            if group_id:
                await self.bot.api.send_group_msg(
                    group_id=group_id,
                    message=f"[CQ:image,file=file:///{os.path.abspath(gif_path)}]"
                )
            else:
                await self.bot.api.send_private_msg(
                    user_id=user_id,
                    message=f"[CQ:image,file=file:///{os.path.abspath(gif_path)}]"
                )
            
            return ""
            
        except Exception as e:
            logger.error(f"生成锤子GIF时出错: {e}")
            return "生成GIF时出错喵~"

    async def praise_command(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """处理赞我命令，给用户发送20个赞"""
        try:
            # 调用API发送20个赞
            
            result = await self.bot.api.send_like(user_id=user_id, times=20)
            if result is None:
                logger.info(f"给用户 {user_id} 点赞")
                return "点赞成功了喵~不用谢！！§(*￣▽￣*)§"
            if result.get("status") == "failed":
                logger.info(f"给用户 {user_id} 点赞")
                return "喵喵！点赞成功了哦~╰(*°▽°*)╯"
            
            logger.info(f"已给用户 {user_id} 发送20个赞")
            return "已给你发送20个赞喵~"
        except Exception as e:
            logger.error(f"点赞时出错: {e}")
            return "点赞时出现错误喵~"

    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令
        
        Args:
            command: 命令名称或函数名称
            args: 命令参数
            user_id: 用户ID
            group_id: 群ID，私聊消息为None
            
        Returns:
            命令执行结果
        """
        logger.debug(f"ChatPlugin处理命令: {command}, 参数: {args}")
        
        # 根据命令名称或函数名称执行对应的命令
        if command in ["clear_memory", "清除记忆", "忘记", "forget"]:
            return await self._clear_memory_command(user_id, group_id, args)
            
        elif command in ["withdraw", "撤回"]:
            return await self.withdraw_command(args, user_id, group_id)
        
        elif command == "chat":
            return await self.chat_command(args, user_id, group_id)
        
        elif command == "model":
            return await self.model_command(args, user_id, group_id)
            
        elif command == "think":
            return await self.think_command(args, user_id, group_id)
        elif command in ["presets", "预设"]:
            return await self.handle_presets(args, user_id, group_id)
        
        elif command in ["赞我"]:
            return await self.praise_command(args, user_id, group_id)

        elif command == "send":
            # 处理 /send 命令，格式：/send <friend/group> <QQ号/群号> <消息内容>
            parts = args.split()
            if len(parts) < 3:
                return "发送消息格式错误，正确格式: /send <friend/group> <QQ号/群号> <消息内容>"
            
            target_type = parts[0]
            try:
                target_id = int(parts[1])
                message = " ".join(parts[2:])
                
                if target_type == "friend":
                    result = await self.bot.api.send_private_msg(user_id=target_id, message=message)
                    if result.get("status") == "failed":
                        return f"发送消息失败喵: {result.get('message', '未知错误')}"
                    
                    # 记录消息到历史
                    message_id = self.message_counter
                    self.message_counter += 1
                    
                    # 获取QQ消息ID
                    qq_message_id = None
                    if result.get("message_id"):
                        qq_message_id = result["message_id"]
                    elif result.get("data", {}).get("message_id"):
                        qq_message_id = result["data"]["message_id"]
                    
                    # 无论是否获取到 QQ 消息 ID，都记录消息
                    self.message_history[message_id] = {
                        "user_id": user_id,  # 发送命令的用户
                        "group_id": None,
                        "content": f"[发送给用户 {target_id} 的消息]",
                        "response": message,
                        "message_id": qq_message_id,  # 可能为None
                        "time": __import__('time').time()
                    }
                    
                    logger_msg = f"消息编号 [{message_id}]"
                    if qq_message_id:
                        logger_msg += f" - QQ消息ID [{qq_message_id}]"
                    else:
                        logger_msg += " - 未获取到QQ消息ID"
                    logger_msg += f" - 发送给用户: {target_id}"
                    logger.info(logger_msg)
                    
                    return f"已向用户 {target_id} 发送消息喵~"
                    
                elif target_type == "group":
                    result = await self.bot.api.send_group_msg(group_id=target_id, message=message)
                    if result.get("status") == "failed":
                        return f"发送消息失败喵: {result.get('message', '未知错误')}"
                    
                    # 记录消息到历史
                    message_id = self.message_counter
                    self.message_counter += 1
                    
                    # 获取QQ消息ID
                    qq_message_id = None
                    if result.get("message_id"):
                        qq_message_id = result["message_id"]
                    elif result.get("data", {}).get("message_id"):
                        qq_message_id = result["data"]["message_id"]
                    
                    # 无论是否获取到 QQ 消息 ID，都记录消息
                    self.message_history[message_id] = {
                        "user_id": user_id,  # 发送命令的用户
                        "group_id": target_id,
                        "content": f"[发送给群 {target_id} 的消息]",
                        "response": message,
                        "message_id": qq_message_id,  # 可能为None
                        "time": __import__('time').time()
                    }
                    
                    logger_msg = f"消息编号 [{message_id}]"
                    if qq_message_id:
                        logger_msg += f" - QQ消息ID [{qq_message_id}]"
                    else:
                        logger_msg += " - 未获取到QQ消息ID"
                    logger_msg += f" - 发送给群: {target_id}"
                    logger.info(logger_msg)
                    
                    return f"已向群 {target_id} 发送消息喵~"
                else:
                    return "未知的发送目标喵~"
            except ValueError:
                return "QQ号/群号格式错误喵~"
        else:
            return None
