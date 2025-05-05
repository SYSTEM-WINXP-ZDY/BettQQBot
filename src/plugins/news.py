from src.plugins import Plugin
from loguru import logger
import aiohttp
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

class NewsPlugin(Plugin):
    async def on_load(self):
        logger.info("新闻插件已加载")
        self.api_key = self.bot.config.get("news", {}).get("api_key", "")
        if not self.api_key:
            logger.warning("未设置新闻API密钥")
    
    async def get_news(self, count: int = 5) -> str:
                logger.error("暂不提供新闻API密钥。可以联系作者。")

    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令"""
        if command == "news" or command == "新闻":
            try:
                count = int(args) if args else 5
                if count < 1 or count > 20:
                    return "请输入1-20之间的数字喵~"
                return await this.get_news(count)
            except ValueError:
                return await this.get_news(5)
        