from typing import TYPE_CHECKING, List, Dict, Any, Optional
from loguru import logger
import importlib
import os
import inspect
from ..utils.command_manager import CommandManager

if TYPE_CHECKING:
    from ..bot import BettQQBot

class Plugin:
    """插件基类"""
    def __init__(self, bot: 'BettQQBot'):
        self.bot = bot
        
    async def on_load(self):
        """插件加载时调用"""
        pass
        
    async def on_unload(self):
        """插件卸载时调用"""
        pass
        
    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        """处理私聊消息"""
        pass
        
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        """处理群消息"""
        pass
        
    async def handle_group_request(self, flag: str, sub_type: str, user_id: int, group_id: int):
        """处理群请求"""
        pass
        
    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令
        
        Args:
            command: 命令名称
            args: 命令参数
            user_id: 用户ID
            group_id: 群ID，私聊消息为None
            
        Returns:
            命令执行结果
        """
        raise NotImplementedError(f"命令 {command} 未实现")

class PluginManager:
    """插件管理器"""
    def __init__(self, bot: 'BettQQBot'):
        self.bot = bot
        self.plugins: Dict[str, Plugin] = {}
        self.command_manager = CommandManager(bot.config.get("features", {}).get("commands", {"enabled": False}))
        
    async def load_plugins(self):
        """加载插件"""
        plugins_config = self.bot.config.get("plugins", [])
        if not plugins_config:
            logger.warning("没有配置任何插件")
            return
            
        for plugin_config in plugins_config:
            name = plugin_config.get("name")
            enabled = plugin_config.get("enabled", True)
            
            if not name:
                logger.warning("插件配置缺少 name 字段")
                continue
                
            if not enabled:
                logger.info(f"插件 {name} 已禁用")
                continue
                
            try:
                # 导入插件模块
                module = importlib.import_module(f".{name}", "src.plugins")
                
                # 获取插件类
                plugin_classes = inspect.getmembers(
                    module,
                    lambda x: inspect.isclass(x) and issubclass(x, Plugin) and x != Plugin
                )
                
                if not plugin_classes:
                    logger.warning(f"在模块 {name} 中找不到插件类")
                    continue
                    
                # 创建插件实例
                plugin_class = plugin_classes[0][1]
                plugin = plugin_class(self.bot)
                self.plugins[name] = plugin
                
                # 初始化插件
                await plugin.on_load()
                logger.success(f"插件 {name} 加载成功")
            except Exception as e:
                logger.error(f"加载插件 {name} 失败: {e}")
                logger.exception(e)  # 打印完整的错误堆栈
                
    async def unload_plugins(self):
        """卸载所有插件"""
        for name, plugin in list(self.plugins.items()):
            try:
                if hasattr(plugin, 'on_unload') and callable(plugin.on_unload):
                    await plugin.on_unload()
                logger.success(f"插件 {name} 卸载成功")
            except Exception as e:
                logger.error(f"卸载插件 {name} 时出错: {e}")
        self.plugins.clear()
        
    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        """处理私聊消息"""
        # 提取文本内容
        text = self._extract_text_from_message(message)
        
        # 检查是否是命令
        if text and self.command_manager.is_command(text):
            cmd_info = self.command_manager.parse_command(text)
            if cmd_info:
                await self._handle_command(cmd_info, user_id)
                return
        
        # 传递给所有插件处理
        for name, plugin in self.plugins.items():
            try:
                await plugin.handle_private_message(user_id, message)
            except Exception as e:
                logger.error(f"插件 {name} 处理私聊消息失败: {e}")
                logger.exception(e)  # 打印完整的错误堆栈
                
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        """处理群消息"""
        # 提取文本内容
        text = self._extract_text_from_message(message)
        
        # 检查是否是命令
        if text and self.command_manager.is_command(text):
            cmd_info = self.command_manager.parse_command(text)
            if cmd_info:
                await self._handle_command(cmd_info, user_id, group_id)
                return
        
        # 传递给所有插件处理
        for name, plugin in self.plugins.items():
            try:
                await plugin.handle_group_message(group_id, user_id, message)
            except Exception as e:
                logger.error(f"插件 {name} 处理群消息失败: {e}")
                logger.exception(e)  # 打印完整的错误堆栈
                
    async def handle_group_request(self, flag: str, sub_type: str, user_id: int, group_id: int):
        """处理群请求"""
        for name, plugin in self.plugins.items():
            try:
                await plugin.handle_group_request(flag, sub_type, user_id, group_id)
            except Exception as e:
                logger.error(f"插件 {name} 处理群请求失败: {e}")
                logger.exception(e)  # 打印完整的错误堆栈
                
    async def _handle_command(self, cmd_info: Dict[str, Any], user_id: int, group_id: Optional[int] = None):
        """处理命令
        
        Args:
            cmd_info: 命令信息
            user_id: 用户ID
            group_id: 群ID，私聊消息为None
        """
        command = cmd_info["command"]
        args = cmd_info["args"]
        plugin_name = cmd_info["plugin"]
        function_name = cmd_info["function"]
        admin_only = cmd_info["admin_only"]
        
        # 检查是否仅管理员可用
        if admin_only and user_id not in self.bot.config["bot"]["admin"]["super_users"]:
            logger.warning(f"用户 {user_id} 尝试执行仅管理员可用的命令 {command}")
            reply = "此命令仅管理员可用喵~"
            if group_id:
                await self.bot.api.send_group_msg(group_id=group_id, message=reply)
            else:
                await self.bot.api.send_private_msg(user_id=user_id, message=reply)
            return
        
        # 获取插件
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            logger.error(f"找不到处理命令 {command} 的插件 {plugin_name}")
            return
            
        try:
            # 调用命令处理函数
            reply = await plugin.execute_command(function_name, args, user_id, group_id)
            if reply:
                if group_id:
                    await self.bot.api.send_group_msg(group_id=group_id, message=reply)
                else:
                    await self.bot.api.send_private_msg(user_id=user_id, message=reply)
        except NotImplementedError as e:
            logger.error(f"命令 {command} 未实现: {e}")
        except Exception as e:
            logger.error(f"执行命令 {command} 失败: {e}")
            logger.exception(e)  # 打印完整的错误堆栈
            
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