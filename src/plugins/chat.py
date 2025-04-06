from src.plugins import Plugin
from loguru import logger
from src.ai_providers.factory import create_provider
from src.utils.access_control import AccessControl
from src.utils.memory_manager import MemoryManager
from typing import Optional, Dict, Any, List
import aiohttp
import os

class ChatPlugin(Plugin):
    async def on_load(self):
        logger.info("聊天插件已加载")
        
        config = self.bot.config["features"]["chat"]
        
        self.ai_provider = create_provider(config)
        
        self.system_prompt = config.get("system_prompt", "")
        
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
            favor_prompt = "你对用户非常喜爱，会主动撒娇，使用非常亲密的语气，偶尔会表现出强烈的依赖感和感情流露。"
        elif favorability >= 80:
            favor_prompt = "你对用户非常亲近，会经常撒娇，会表现出明显的喜爱和亲密。"
        elif favorability >= 50:
            favor_prompt = "你对用户有好感，愿意亲近，但仍有一些傲娇的特性。"
        elif favorability >= 30:
            favor_prompt = "你对用户开始产生好感，会减少傲娇的频率，语气更加友善。"
        elif favorability >= 10:
            favor_prompt = "你对用户略有好感，但仍然保持傲娇的态度。"
        else:
            favor_prompt = "你对用户没什么特别的感觉，保持基本的傲娇态度。"
            
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
                

    async def _handle_chat(self, content: str, group_id: Optional[int], user_id: int, is_group: bool = False) -> str:
        try:
            user_info = await self._get_user_info(user_id)
            nickname = user_info.get("nickname", str(user_id))
            
            if group_id:
                logger.info(f"群 {group_id} 中用户 {user_id}({nickname}) 发送消息: {content}")
            else:
                logger.info(f"用户 {user_id}({nickname}) 发送私聊消息: {content}")
            
            # 处理撤回命令 - 只处理纯 'withdraw' 开头的命令
            if content.startswith("withdraw ") and not content.startswith("withdraw withdraw") and not content.startswith("withdraw chat"):
                try:
                    message_id = int(content.split()[1])
                    return await self._withdraw_message(message_id, user_id, group_id)
                except (IndexError, ValueError):
                    return "撤回命令格式错误，正确格式: withdraw <消息编号>"
            
            # 不在这里处理 'chat withdraw' 格式，仅在命令处理器中处理
            
            # 构建系统提示词
            system_prompt = self._get_system_prompt(user_id, nickname)
            
            # 准备消息列表
            messages = [{"role": "system", "content": system_prompt}]
            
            # 加载记忆
            memories = None
            if self.memory_enabled:
                memories = self.memory_manager.load_memories(user_id, group_id)
                
                # 如果有记忆，添加到消息列表
                if memories:
                    # 添加总体记忆提示
                    memory_prompt = "以下是之前的对话历史，请根据这些历史信息理解用户的语境和喜好，保持一致的对话风格和个性："
                    messages.append({"role": "system", "content": memory_prompt})
                    
                    # 限制记忆数量，避免token过多
                    # 只保留最近的14条或当前配置的记忆上限
                    max_memories = min(14, self.memory_manager.max_history)
                    relevant_memories = memories[-max_memories:]
                    
                    # 记录使用的记忆数量
                    logger.debug(f"使用 {len(relevant_memories)}/{len(memories)} 条记忆记录")
                    
                    # 直接将历史消息作为独立消息添加
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
                
                # 记录消息到历史
                message_id = self.message_counter
                self.message_counter += 1
                self.message_history[message_id] = {
                    "user_id": user_id,
                    "group_id": group_id,
                    "content": content,
                    "response": response,
                    "time": __import__('time').time()
                }
                
                # 在控制台显示消息编号
                logger.info(f"消息编号 [{message_id}] - 用户: {user_id} - 内容: {content[:30]}...")
                
                if self.memory_enabled:
                    self.memory_manager.save_memory(user_id, "user", content, group_id)
                    self.memory_manager.save_memory(user_id, "assistant", response, group_id)
                
                # 直接返回回复内容，不添加消息编号
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
            
            # 使用AI提供商实例生成回复
            try:
                # 使用已创建的AI提供商实例
                response_text = await self.ai_provider.chat(messages)
                
                # 处理回复内容，移除AI思考痕迹，变得更加活泼傲娇
                response_text = self._refine_response(response_text)
                
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
        if random.random() < 0.7:
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
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
        
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
        
        # 处理聊天消息
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
        
        # 处理管理命令
        if text.startswith("/chat."):
            if not await self._is_admin_command(user_id):
                await self.bot.api.send_private_msg(user_id=user_id, message="你没有权限使用此命令")
                return
            reply = await self._handle_admin_command(text, None, user_id)
            await self.bot.api.send_private_msg(user_id=user_id, message=reply)
            return
        
        # 所有带/前缀的命令(包括/chat withdraw)都将通过命令处理器处理，在此不处理
        
        # 访问控制检查
        config = self.bot.config["features"]["chat"]["access_control"]
        allowed_friends = config.get("allowed_friends", [])
        if allowed_friends and user_id not in allowed_friends:
            logger.warning(f"用户 {user_id} 不在允许列表中，忽略消息")
            return
        
        if self.access_control.enabled and not self.access_control.can_access(user_id):
            logger.warning(f"用户 {user_id} 在黑名单中，忽略消息")
            return
        
        # 处理聊天消息
        if text and text.startswith("!"):
            content = text[1:].strip()
            if content:
                reply = await self._handle_chat(content, None, user_id, is_group=False)
                await self.bot.api.send_private_msg(user_id=user_id, message=reply)

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
            return await self._clear_memory_command(user_id, group_id)
            
        elif command in ["withdraw", "撤回"]:
            try:
                message_id = int(args.strip())
                return await self._withdraw_message(message_id, user_id, group_id)
            except ValueError:
                return "撤回命令格式错误，正确格式: /withdraw <消息编号>"
                
        elif command == "chat":
            # 如果没有参数，显示当前会话的所有消息
            if not args:
                return await self._list_current_messages(user_id, group_id)
                
            # 处理类似 /chat withdraw 1 的命令
            if args.startswith("withdraw " or args.startswith("撤回 ")):
                try:
                    parts = args.split()
                    if len(parts) != 2:
                        return "撤回命令格式错误，正确格式: /chat withdraw <消息编号>"
                    message_id = int(parts[1])
                    return await self._withdraw_message(message_id, user_id, group_id)
                except (IndexError, ValueError):
                    return "撤回命令格式错误，正确格式: /chat withdraw <消息编号>"
            else:
                return f"未知的子命令: {args}"
        else:
            logger.warning(f"未知的聊天插件命令: {command}")
            return f"未知的命令: {command}"
    
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

    async def _withdraw_message(self, message_id: int, user_id: int, group_id: Optional[int] = None) -> str:
        """撤回消息"""
        if message_id not in self.message_history:
            return f"找不到编号为 {message_id} 的消息喵~"
            
        message = self.message_history[message_id]
        
        # 验证消息所有者或管理员权限
        is_admin = user_id in self.bot.config["bot"]["admin"]["super_users"]
        is_owner = message["user_id"] == user_id
        
        if not (is_admin or is_owner):
            return "你没有权限撤回这条消息喵~"
            
        # 验证消息群组
        if group_id is not None and message["group_id"] != group_id:
            return "这条消息不属于当前群组喵~"
            
        # 撤回消息前先保存信息
        msg_user_id = message["user_id"]
        msg_group_id = message["group_id"]
        msg_content = message["content"]
        msg_response = message["response"]
        
        # 从历史记录中删除
        del self.message_history[message_id]
        
        # 如果启用了记忆功能，从记忆中移除这条消息和对应回复
        if self.memory_enabled:
            try:
                success = self.memory_manager.remove_specific_memory(
                    msg_user_id, 
                    msg_content, 
                    msg_response,  # 现在回复中不再有编号前缀
                    msg_group_id
                )
                if success:
                    logger.info(f"已从记忆中移除消息 {message_id} 相关的对话")
                else:
                    logger.warning(f"未能从记忆中移除消息 {message_id} 相关的对话")
            except Exception as e:
                logger.error(f"从记忆中移除特定消息时出错: {e}")
        
        logger.info(f"消息 {message_id} 已被用户 {user_id} 撤回")
        return f"消息 {message_id} 已成功撤回喵~" 