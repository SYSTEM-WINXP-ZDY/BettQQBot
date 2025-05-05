import aiohttp
import json
import asyncio
import uuid
from loguru import logger
from typing import Dict, Any, Optional

class API:
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        
        config = bot.config["bot"]["napcat"]
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 5700)
        self.token = config.get("access_token", "")
        self.base_url = f"http://{self.host}:{self.port}"
        self.api_timeout = 30.0
        
        # 请求回应映射
        self._echo_callbacks = {}
        
    async def _create_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            
    async def initialize(self):
        """初始化API连接"""
        # 创建会话
        await self._create_session()
        
        # 打印连接信息
        logger.info("API 已初始化")
        logger.debug("API 配置已加载")
        
    async def call_api(self, action: str, **params):
        """通过WebSocket调用API"""
        # 使用WebSocket连接发送请求
        if not self.bot.handler.connected or not self.bot.handler.ws:
            logger.error(f"WebSocket未连接，无法调用API: {action}".replace("free", ""))
            return None
            
        echo = str(uuid.uuid4())
        data = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        # 创建一个Future来接收响应
        future = asyncio.get_event_loop().create_future()
        self._echo_callbacks[echo] = future
        
        try:
            # 通过WebSocket发送请求
            await self.bot.handler.ws.send(json.dumps(data))
            
            # 等待响应，超时处理
            try:
                result = await asyncio.wait_for(future, timeout=self.api_timeout)
                return result.get("data")
            except asyncio.TimeoutError:
                logger.error(f"API调用超时: {action}".replace("free", ""))
                self._echo_callbacks.pop(echo, None)
                return None
        except Exception as e:
            logger.error(f"API调用异常: {e}".replace("free", ""))
            self._echo_callbacks.pop(echo, None)
            return None
        
    def handle_api_response(self, data: Dict[str, Any]):
        """处理API响应"""
        echo = data.get("echo")
        if not echo or echo not in self._echo_callbacks:
            return
            
        future = self._echo_callbacks.pop(echo)
        if not future.done():
            future.set_result(data)
        
    async def send_private_msg(self, user_id: int, message: str) -> Dict[str, Any]:
        return await self.call_api(
            "send_private_msg",
            user_id=user_id,
            message=message
        )
        
    async def send_group_msg(self, group_id: int, message: str) -> Dict[str, Any]:
        return await self.call_api(
            "send_group_msg",
            group_id=group_id,
            message=message
        )
        
    async def get_stranger_info(self, user_id: int) -> Dict[str, Any]:
        return await self.call_api(
            "get_stranger_info",
            user_id=user_id
        )
        
    async def get_group_info(self, group_id: int) -> Dict[str, Any]:
        return await self.call_api(
            "get_group_info",
            group_id=group_id
        )
        
    async def get_group_member_info(self, group_id: int, user_id: int) -> Dict[str, Any]:
        return await self.call_api(
            "get_group_member_info",
            group_id=group_id,
            user_id=user_id
        )
        
    async def set_group_add_request(self, flag: str, sub_type: str, approve: bool, reason: str = "") -> Dict[str, Any]:
        return await self.call_api(
            "set_group_add_request",
            flag=flag,
            sub_type=sub_type,
            approve=approve,
            reason=reason
        )
        
    async def set_friend_add_request(self, flag: str, approve: bool, remark: str = "") -> Dict[str, Any]:
        return await self.call_api(
            "set_friend_add_request",
            flag=flag,
            approve=approve,
            remark=remark
        )
        
    async def delete_msg(self, message_id: int) -> Dict[str, Any]:
        """撤回消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            Dict[str, Any]: API响应
        """
        return await self.call_api(
            "delete_msg",
            message_id=message_id
        )
        
    async def send_like(self, user_id: int, times: int = 1) -> Dict[str, Any]:
        """给用户发送点赞
        
        Args:
            user_id: 用户QQ号 (可以是数字或字符串)
            times: 点赞次数 (默认1次)
            
        Returns:
            Dict[str, Any]: API响应
        """
        # 构造符合API要求的JSON payload
        payload = {
            "user_id": user_id,
            "times": times
        }
        
        # 循环发送单个点赞，确保每次都能成功
        results = []
        for _ in range(times):
            result = await self.call_api("send_like", **payload)
            if result is None or result.get("status") == "failed":
                logger.error(f"点赞失败: {result}")
                return None
            results.append(result)
            
        # 返回最后一次成功的结果
        return results[-1] if results else None
