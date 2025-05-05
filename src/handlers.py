from typing import TYPE_CHECKING, Dict, Any, Optional, List, Set
from loguru import logger
import json
import asyncio
import aiohttp
from urllib.parse import urlencode
import websockets

if TYPE_CHECKING:
    from .bot import BettQQBot

class MessageHandler:
    def __init__(self, bot: 'BettQQBot'):
        self.bot = bot
        self.plugins = bot.plugin_manager.plugins
        self.ws = None
        self.connected = False
        self.tasks: Set[asyncio.Task] = set()
        self.message_queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
        
    async def start(self):
        logger.info("消息处理器已启动")
        
        config = self.bot.config["bot"]["napcat"]
        host = config.get("host", "127.0.0.1")
        port = config.get("port", 5700)
        token = config.get("access_token", "")
        
        # websockets 10.4版本的连接方式
        ws_url = f"ws://{host}:{port}/bot"
        
        # 如果有token，将其添加为查询参数
        if token:
            ws_url = f"{ws_url}?access_token={token}"
        
        # 准备额外的HTTP头
        extra_headers = {}
        if token:
            # 尝试多种可能的token格式
            extra_headers["Authorization"] = f"{token}"
            extra_headers["access_token"] = token
            logger.info(f"正在使用token: {'*' * (len(token) // 3)}***")  # 隐藏真实token
        
        # 隐藏token的WebSocket URL
        masked_ws_url = ws_url
        if token:
            masked_ws_url = masked_ws_url.replace(token, '***********')
        logger.info(f"正在连接到 WebSocket: {masked_ws_url}")
        
        try:
            # 使用websockets 11.0+的连接方式并传递HTTP头
            websocket = await websockets.connect(ws_url, headers=extra_headers)
            self.ws = websocket
            self.connected = True
            logger.success(f"WebSocket 连接成功！")
            
            try:
                # 启动消息处理任务
                await asyncio.gather(
                    self._heartbeat(websocket),
                    self._receive_messages(websocket),
                    self._process_messages()
                )
            except Exception as e:
                logger.error(f"WebSocket 任务执行错误: {e}")
            finally:
                # 关闭连接
                if not websocket.closed:
                    await websocket.close()
                
            # 如果执行到这里，说明连接已经断开
            logger.warning("WebSocket 连接已断开")
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            self.connected = False
            self.ws = None
        
        self.connected = False
        self.ws = None
        logger.warning("WebSocket 连接已关闭")
        
    async def stop(self):
        logger.info("停止消息处理器...")
        self._stop_event.set()
        
        for task in self.tasks:
            if not task.done():
                task.cancel()
                
        await asyncio.sleep(0.5)
        
        for task in self.tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            
        logger.info("消息处理器已停止")
        
    async def _heartbeat(self, websocket):
        # 由于NapCat不支持标准心跳包，我们只是简单的保持任务活动但不实际发送心跳
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(30)
                logger.debug("心跳检查 - 连接正常")
        except asyncio.CancelledError:
            logger.debug("心跳任务已取消")
        except Exception as e:
            logger.error(f"心跳出错: {e}")
            
    async def _receive_messages(self, websocket):
        try:
            while not self._stop_event.is_set():
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data.get("post_type") != "meta_event" or data.get("meta_event_type") != "heartbeat":
                        logger.debug(f"收到消息: {message}")
                    
                    if data.get("status") == "failed":
                        logger.error(f"收到错误响应: {data}")
                        if data.get("retcode") == 1403:
                            logger.error("token验证失败，请检查配置")
                        continue
                    
                    # 检查是否是API响应
                    if "echo" in data:
                        # 将API响应传递给API处理器
                        self.bot.api.handle_api_response(data)
                        continue
                    
                    # 将消息放入队列等待处理
                    await self.message_queue.put(data)
                except json.JSONDecodeError:
                    logger.error(f"JSON解析失败: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.error("WebSocket连接已关闭")
                    break
                except Exception as e:
                    logger.error(f"接收消息时出错: {e}")
        except asyncio.CancelledError:
            logger.debug("接收消息任务已取消")
        except Exception as e:
            logger.error(f"接收消息循环出错: {e}")
            
    async def _process_messages(self):
        try:
            while not self._stop_event.is_set():
                try:
                    data = await asyncio.wait_for(self.message_queue.get(), 1)
                    
                    if data.get("post_type") == "message":
                        message_type = data.get("message_type")
                        
                        if message_type == "group":
                            group_id = data.get("group_id")
                            user_id = data.get("user_id")
                            raw_message = data.get("raw_message", "")
                            message = data.get("message", [])
                            
                            task = asyncio.create_task(
                                self._process_group_message(group_id, user_id, message, raw_message)
                            )
                            self.tasks.add(task)
                            task.add_done_callback(self.tasks.discard)
                        
                        elif message_type == "private":
                            user_id = data.get("user_id")
                            raw_message = data.get("raw_message", "")
                            message = data.get("message", [])
                            
                            task = asyncio.create_task(
                                self._process_private_message(user_id, message, raw_message)
                            )
                            self.tasks.add(task)
                            task.add_done_callback(self.tasks.discard)
                    
                    self.message_queue.task_done()
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
        except asyncio.CancelledError:
            logger.debug("消息处理任务已取消")
            
    async def _process_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]], raw_message: str):
        try:
            # 如果是命令, 优先使用命令管理器处理
            text = self._extract_text_from_message(message)
            
            # 先检查是否是斜杠命令，由一个插件处理
            if raw_message.startswith("/"):
                command_handled = False
                # 特殊处理调试命令
                if raw_message.startswith("/debug") and user_id in self.bot.config["bot"]["admin"]["super_users"]:
                    parts = raw_message[1:].strip().split(" ", 1)
                    args = parts[1] if len(parts) > 1 else ""
                    response = await self._handle_debug_command(args)
                    if response:
                        await self.bot.api.send_group_msg(group_id=group_id, message=response)
                    return
                
                # 尝试让一个插件处理命令
                for plugin_name, plugin in self.plugins.items():
                    try:
                        if await self._process_command(plugin, raw_message, user_id, group_id):
                            command_handled = True
                            break
                    except Exception as e:
                        logger.error(f"插件 {plugin_name} 处理群消息命令时出错: {e}")
                
                # 如果斜杠命令已处理，直接返回
                if command_handled:
                    return
            
            # 检查是否是普通命令(不带斜杠前缀)
            elif text and self.bot.plugin_manager.command_manager.is_command(text):
                cmd_info = self.bot.plugin_manager.command_manager.parse_command(text)
                if cmd_info:
                    await self.bot.plugin_manager._handle_command(cmd_info, user_id, group_id)
                    return
            
            # 非命令或命令处理失败后，正常处理消息
            for plugin_name, plugin in self.plugins.items():
                try:
                    if hasattr(plugin, "handle_group_message"):
                        await plugin.handle_group_message(group_id, user_id, message)
                except Exception as e:
                    logger.error(f"插件 {plugin_name} 处理群消息时出错: {e}")
        except Exception as e:
            logger.error(f"处理群消息时出错: {e}")
            
    async def _process_private_message(self, user_id: int, message: List[Dict[str, Any]], raw_message: str):
        try:
            # 如果是命令, 优先使用命令管理器处理
            text = self._extract_text_from_message(message)
            
            # 先检查是否是斜杠命令，由一个插件处理
            if raw_message.startswith("/"):
                command_handled = False
                # 特殊处理调试命令
                if raw_message.startswith("/debug") and user_id in self.bot.config["bot"]["admin"]["super_users"]:
                    parts = raw_message[1:].strip().split(" ", 1)
                    args = parts[1] if len(parts) > 1 else ""
                    response = await self._handle_debug_command(args)
                    if response:
                        await self.bot.api.send_private_msg(user_id=user_id, message=response)
                    return
                
                # 尝试让一个插件处理命令
                for plugin_name, plugin in self.plugins.items():
                    try:
                        if await self._process_command(plugin, raw_message, user_id):
                            command_handled = True
                            break
                    except Exception as e:
                        logger.error(f"插件 {plugin_name} 处理私聊命令时出错: {e}")
                
                # 如果斜杠命令已处理，直接返回
                if command_handled:
                    return
            
            # 检查是否是普通命令(不带斜杠前缀)
            elif text and self.bot.plugin_manager.command_manager.is_command(text):
                cmd_info = self.bot.plugin_manager.command_manager.parse_command(text)
                if cmd_info:
                    await self.bot.plugin_manager._handle_command(cmd_info, user_id)
                    return
            
            # 非命令或命令处理失败后，正常处理消息
            for plugin_name, plugin in self.plugins.items():
                try:
                    if hasattr(plugin, "handle_private_message"):
                        await plugin.handle_private_message(user_id, message)
                except Exception as e:
                    logger.error(f"插件 {plugin_name} 处理私聊消息时出错: {e}")
        except Exception as e:
            logger.error(f"处理私聊消息时出错: {e}")
            
    def _extract_text_from_message(self, message: List[Dict[str, Any]]) -> str:
        """从消息中提取文本
        
        Args:
            message: 消息对象
        
        Returns:
            提取的文本
        """
        text = ""
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
        return text.strip()
            
    async def _process_command(self, plugin, raw_message: str, user_id: int, group_id: Optional[int] = None) -> bool:
        """处理命令，返回是否成功处理
        
        Returns:
            bool: 是否成功处理命令
        """
        try:
            parts = raw_message[1:].strip().split(" ", 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            # 处理调试命令
            if command == "debug" and user_id in self.bot.config["bot"]["admin"]["super_users"]:
                response = await self._handle_debug_command(args)
                if response:
                    if group_id:
                        await self.bot.api.send_group_msg(group_id=group_id, message=response)
                    else:
                        await self.bot.api.send_private_msg(user_id=user_id, message=response)
                return True  # 调试命令总是被成功处理
            
            if hasattr(plugin, "execute_command"):
                logger.debug(f"处理原始命令: /{command} {args}")
                try:
                    response = await plugin.execute_command(command, args, user_id, group_id)
                    
                    # 如果没有返回响应或命令不匹配，认为命令没有被处理
                    if response is None or response.startswith("未知的命令:"):
                        return False
                    
                    # 发送响应
                    if response:
                        if group_id:
                            await self.bot.api.send_group_msg(group_id=group_id, message=response)
                        else:
                            await self.bot.api.send_private_msg(user_id=user_id, message=response)
                    return True  # 命令被成功处理
                except Exception as e:
                    logger.error(f"执行命令 /{command} 时出错: {e}")
                    return False  # 命令处理失败
            return False  # 插件没有execute_command方法
        except Exception as e:
            logger.error(f"处理命令时出错: {e}")
            return False  # 命令处理失败
            
    async def _handle_debug_command(self, args: str) -> str:
        """处理调试命令，允许直接修改变量或执行代码"""
        if not args:
            return "调试命令格式: /debug <表达式>\n可用命令:\n- 查询: /debug plugins.chat\n- 设置: /debug plugins.chat.debug=true\n- 获取插件命令: /debug plugins.list\n- 测试命令: /debug test.command 命令名称 参数\n- 诊断: /debug diagnose 命令名称 [参数]"
            
        try:
            # 特殊命令处理
            if args == "plugins.list":
                # 列出所有插件及其可用命令
                result = "已加载的插件:\n"
                for name, plugin in self.bot.plugin_manager.plugins.items():
                    result += f"- {name}\n"
                    
                result += "\n命令列表:\n"
                for cmd in self.bot.plugin_manager.command_manager.get_command_list():
                    result += f"- {cmd['name']} (插件: {cmd['plugin']}, 函数: {cmd['function']}, 别名: {cmd['aliases']})\n"
                    
                return result
                
            # 测试命令处理
            if args.startswith("test.command "):
                parts = args[12:].strip().split(" ", 1)
                if len(parts) < 1:
                    return "命令测试格式: /debug test.command 命令名称 [参数]"
                    
                cmd_text = parts[0]
                cmd_args = parts[1] if len(parts) > 1 else ""
                
                # 检查命令是否存在
                if not self.bot.plugin_manager.command_manager.is_command(cmd_text):
                    return f"命令 '{cmd_text}' 不存在或未启用"
                    
                # 解析命令信息
                cmd_info = self.bot.plugin_manager.command_manager.parse_command(cmd_text)
                if not cmd_info:
                    return f"无法解析命令 '{cmd_text}'"
                    
                # 返回命令详情
                result = "命令解析结果:\n"
                result += f"命令名称: {cmd_info['command']}\n"
                result += f"参数: {cmd_info['args'] if cmd_args == '' else cmd_args}\n"
                result += f"插件: {cmd_info['plugin']}\n"
                result += f"函数: {cmd_info['function']}\n"
                result += f"仅管理员: {cmd_info['admin_only']}\n"
                
                # 获取插件
                plugin = self.bot.plugin_manager.plugins.get(cmd_info['plugin'])
                if not plugin:
                    result += f"\n错误: 找不到插件 {cmd_info['plugin']}"
                    return result
                
                # 尝试执行命令
                try:
                    result += "\n尝试执行命令...\n"
                    cmd_result = await plugin.execute_command(cmd_info['command'], cmd_args if cmd_args else cmd_info['args'], 0, None)
                    result += f"命令执行结果: {cmd_result}"
                except Exception as e:
                    result += f"命令执行出错: {e}"
                
                return result
                
            # 诊断命令
            if args.startswith("diagnose "):
                parts = args[9:].strip().split(" ", 1)
                if len(parts) < 1:
                    return "命令诊断格式: /debug diagnose 命令名称 [参数]"
                    
                cmd_text = parts[0]
                cmd_args = parts[1] if len(parts) > 1 else ""
                
                result = f"命令诊断: {cmd_text}\n\n"
                
                # 1. 检查命令管理器是否启用
                result += f"命令系统状态: {'已启用' if self.bot.plugin_manager.command_manager.enabled else '未启用'}\n"
                
                # 2. 尝试识别命令
                is_command = self.bot.plugin_manager.command_manager.is_command(cmd_text)
                result += f"命令识别结果: {'成功' if is_command else '失败'}\n"
                
                if not is_command:
                    # 列出所有已知命令供参考
                    result += "\n可用命令:\n"
                    for cmd in self.bot.plugin_manager.command_manager.get_command_list():
                        result += f"- {cmd['name']} (别名: {cmd['aliases']})\n"
                    return result
                
                # 3. 获取命令信息
                cmd_info = self.bot.plugin_manager.command_manager.parse_command(cmd_text)
                result += "\n命令信息:\n"
                if cmd_info:
                    for key, value in cmd_info.items():
                        result += f"- {key}: {value}\n"
                else:
                    result += "无法解析命令信息\n"
                    return result
                
                # 4. 检查插件是否存在
                plugin_name = cmd_info.get("plugin")
                plugin = self.bot.plugin_manager.plugins.get(plugin_name)
                result += f"\n插件信息:\n- 名称: {plugin_name}\n- 已加载: {plugin is not None}\n"
                
                if not plugin:
                    result += f"错误: 找不到插件 {plugin_name}\n"
                    return result
                    
                # 5. 查看插件是否有执行命令的方法
                has_execute = hasattr(plugin, "execute_command")
                result += f"- execute_command方法: {'存在' if has_execute else '不存在'}\n"
                
                if not has_execute:
                    result += "错误: 插件没有 execute_command 方法\n"
                    return result
                
                return result
                
            # 如果是赋值操作
            if "=" in args:
                # 分割变量路径和值
                var_path, value = args.split("=", 1)
                var_path = var_path.strip()
                value = value.strip()
                
                # 解析变量路径
                parts = var_path.split(".")
                
                # 定位到对象
                obj = self.bot
                for part in parts[:-1]:
                    if part == "plugins":
                        obj = self.bot.plugin_manager.plugins
                    elif isinstance(obj, dict) and part in obj:
                        obj = obj[part]
                    elif hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        return f"找不到对象: {part}"
                
                last_part = parts[-1]
                
                # 尝试执行赋值
                try:
                    # 尝试将值转换为适当的类型
                    try:
                        # 尝试作为数字
                        if value.isdigit():
                            value = int(value)
                        elif "." in value and all(p.isdigit() for p in value.split(".", 1)):
                            value = float(value)
                        # 尝试作为布尔值
                        elif value.lower() in ["true", "false"]:
                            value = value.lower() == "true"
                    except:
                        # 保持为字符串
                        pass
                    
                    # 设置属性或字典项
                    if isinstance(obj, dict):
                        obj[last_part] = value
                    else:
                        setattr(obj, last_part, value)
                    
                    return f"成功设置 {var_path} = {value}"
                except Exception as e:
                    return f"设置 {var_path} 时出错: {e}"
                
            # 如果是查询操作
            else:
                # 解析变量路径
                parts = args.split(".")
                
                # 定位到对象
                obj = self.bot
                for part in parts:
                    if part == "plugins":
                        obj = self.bot.plugin_manager.plugins
                    elif isinstance(obj, dict) and part in obj:
                        obj = obj[part]
                    elif hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        return f"找不到对象: {part}"
                
                # 返回对象的值
                return f"{args} = {obj}"
                
        except Exception as e:
            logger.error(f"执行调试命令时出错: {e}")
            return f"执行调试命令时出错: {e}"
