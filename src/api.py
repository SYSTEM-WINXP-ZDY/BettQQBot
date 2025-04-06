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
        
        self._echo_callbacks = {}
        
    async def _create_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            
    async def call_api(self, action: str, **params):
        """通过WebSocket调用API"""
        if not self.bot.handler.connected or not self.bot.handler.ws:
            logger.error(f"WebSocket未连接，无法调用API: {action}")
            return None
            
        echo = str(uuid.uuid4())
        data = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        future = asyncio.get_event_loop().create_future()
        self._echo_callbacks[echo] = future
        
        try:
            await self.bot.handler.ws.send(json.dumps(data))

            try:
                result = await asyncio.wait_for(future, timeout=self.api_timeout)
                return result.get("data")
            except asyncio.TimeoutError:
                logger.error(f"API调用超时: {action}")
                self._echo_callbacks.pop(echo, None)
                return None
        except Exception as e:
            logger.error(f"API调用异常: {e}")
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