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

        extra_headers = {}
        if token:
            extra_headers["Authorization"] = f"Bearer {token}"
        
        logger.info(f"正在连接到 WebSocket: {ws_url}")
        
        try:

            websocket = await websockets.connect(ws_url, extra_headers=extra_headers)
            self.ws = websocket
            self.connected = True
            logger.success(f"WebSocket 连接成功！")
            
            try:

                await asyncio.gather(
                    self._heartbeat(websocket),
                    self._receive_messages(websocket),
                    self._process_messages()
                )
            except Exception as e:
                logger.error(f"WebSocket 任务执行错误: {e}")
            finally:

                if not websocket.closed:
                    await websocket.close()

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

                    if "echo" in data:
                        self.bot.api.handle_api_response(data)
                        continue
                    
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
            for plugin_name, plugin in self.plugins.items():
                try:
                    if hasattr(plugin, "handle_group_message"):
                        await plugin.handle_group_message(group_id, user_id, message)
                        
                    if raw_message.startswith("/"):
                        await self._process_command(plugin, raw_message, user_id, group_id)
                        
                except Exception as e:
                    logger.error(f"插件 {plugin_name} 处理群消息时出错: {e}")
        except Exception as e:
            logger.error(f"处理群消息时出错: {e}")
            
    async def _process_private_message(self, user_id: int, message: List[Dict[str, Any]], raw_message: str):
        try:
            for plugin_name, plugin in self.plugins.items():
                try:
                    if hasattr(plugin, "handle_private_message"):
                        await plugin.handle_private_message(user_id, message)
                        
                    if raw_message.startswith("/"):
                        await self._process_command(plugin, raw_message, user_id)
                        
                except Exception as e:
                    logger.error(f"插件 {plugin_name} 处理私聊消息时出错: {e}")
        except Exception as e:
            logger.error(f"处理私聊消息时出错: {e}")
            
    async def _process_command(self, plugin, raw_message: str, user_id: int, group_id: Optional[int] = None):
        try:
            parts = raw_message[1:].strip().split(" ", 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            if hasattr(plugin, "execute_command"):
                response = await plugin.execute_command(command, args, user_id, group_id)
                
                if response:
                    if group_id:
                        await self.bot.api.send_group_msg(group_id=group_id, message=response)
                    else:
                        await self.bot.api.send_private_msg(user_id=user_id, message=response)
        except Exception as e:
            logger.error(f"处理命令时出错: {e}") 