from src.plugins import Plugin
from loguru import logger
from typing import Dict, Any, List, Optional

class BasicPlugin(Plugin):
    """基础功能插件"""
    
    async def on_load(self):
        """插件加载"""
        logger.info("基础插件已加载")
        
    async def on_unload(self):
        """插件卸载"""
        logger.info("基础插件已卸载")
        
    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令"""
        if command == "show_help":
            return await self._show_help(args, user_id, group_id)
        return f"未知的命令: {command}"
        
    async def _show_help(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """显示帮助信息"""
        command_list = self.bot.plugin_manager.command_manager.get_command_list()
        
        help_text = "=== 命令帮助 ===\n"
        
        for cmd in command_list:
            if cmd["admin_only"] and user_id not in self.bot.config["bot"]["admin"]["super_users"]:
                continue

            help_text += f"\n• {cmd['name']}"

            if cmd["aliases"]:
                aliases = "、".join(cmd["aliases"])
                help_text += f" (别名: {aliases})"

            if cmd["description"]:
                help_text += f"\n  {cmd['description']}"

            if cmd["admin_only"]:
                help_text += " [仅管理员]"
                
        help_text += "\n\n提示: 直接发送命令即可使用，例如\"签到\"、\"帮助\"等。"
        
        return help_text
        
    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        text = ""
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
                
        if text == "ping":
            await self.bot.api.send_private_msg(user_id=user_id, message="pong!")
            
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        text = ""
        for msg in message:
            if msg["type"] == "text":
                text += msg["data"]["text"]
                
        if text == "ping":
            await self.bot.api.send_group_msg(group_id=group_id, message="pong!")
            
    async def handle_group_request(self, flag: str, sub_type: str, user_id: int, group_id: int):
        """处理加群请求"""
        await self.bot.api.set_group_add_request(
            flag=flag,
            sub_type=sub_type,
            approve=True
        ) 