import asyncio
from loguru import logger
from .api import API
from .handlers import MessageHandler
from .utils.config import load_config
from .plugins import PluginManager

class BettQQBot:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.api = API(self)
        self.plugin_manager = PluginManager(self)
        self.handler = MessageHandler(self)
        self.task = None
        
    async def start(self):
        """启动机器人"""
        logger.info("正在启动机器人...")
        
        # 确保端口设置正确
        if "napcat" in self.config["bot"] and "port" not in self.config["bot"]["napcat"]:
            self.config["bot"]["napcat"]["port"] = 3001
            
        # 加载插件
        await self.plugin_manager.load_plugins()
        logger.success("机器人已启动")
        
        # 启动消息处理器
        await self.handler.start()
        
    async def shutdown(self):
        logger.info("正在关闭机器人...")
        
        # 关闭消息处理器
        if hasattr(self, 'handler') and self.handler:
            await self.handler.stop()
            
        # 关闭API连接
        if hasattr(self, 'api') and self.api:
            await self.api.close()
        
        # 卸载插件
        if hasattr(self, 'plugin_manager') and self.plugin_manager:
            await self.plugin_manager.unload_plugins()
            
        logger.success("机器人已关闭") 