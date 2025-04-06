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
        """执行命令
        
        Args:
            command: 命令名称或函数名称
            args: 命令参数
            user_id: 用户ID
            group_id: 群ID，私聊消息为None
            
        Returns:
            命令执行结果
        """
        logger.debug(f"BasicPlugin处理命令: {command}, 参数: {args}")
        
        # 根据命令名称或函数名称执行对应的命令
        if command in ["show_help", "帮助", "help", "菜单"]:
            return await self._show_help(args, user_id, group_id)
        elif command in ["test", "测试"]:
            return f"测试命令执行成功！参数: {args}, 用户ID: {user_id}, 群ID: {group_id if group_id else '私聊'}"
        else:
            logger.warning(f"未知的基础插件命令: {command}")
            return f"未知的命令: {command}"
        
    async def _show_help(self, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """显示帮助信息"""
        # 获取所有命令
        command_list = self.bot.plugin_manager.command_manager.get_command_list()
        
        # 生成帮助信息
        help_text = "=== 命令帮助 ===\n"
        
        for cmd in command_list:
            # 过滤掉仅管理员可用的命令，除非用户是管理员
            if cmd["admin_only"] and user_id not in self.bot.config["bot"]["admin"]["super_users"]:
                continue
                
            # 添加命令信息
            help_text += f"\n• {cmd['name']}"
            
            # 添加别名
            if cmd["aliases"]:
                aliases = "、".join(cmd["aliases"])
                help_text += f" (别名: {aliases})"
                
            # 添加描述
            if cmd["description"]:
                help_text += f"\n  {cmd['description']}"
                
            # 添加仅管理员标记
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
        # 自动同意加群请求
        await self.bot.api.set_group_add_request(
            flag=flag,
            sub_type=sub_type,
            approve=True
        ) 