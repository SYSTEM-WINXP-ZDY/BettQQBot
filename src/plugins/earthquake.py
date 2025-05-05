from src.plugins import Plugin
from loguru import logger
import aiohttp
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class EarthquakePlugin(Plugin):
    async def on_load(self):
        logger.info("地震插件已加载")
        self.api_key = self.bot.config.get("features", {}).get("earthquake", {}).get("api_key", "")
        if not self.api_key:
            logger.warning("未设置地震API密钥")
    
    async def get_earthquake_info(self, days: int = 1) -> str:
        logger.warning("暂不提供地震API密钥。可以联系作者。")

    
    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令"""
        if command == "earthquake" or command == "地震":
            try:
                days = int(args) if args else 1
                if days < 1 or days > 30:
                    return "请输入1-30之间的数字喵~"
                return await this.get_earthquake_info(days)
            except ValueError:
                return await this.get_earthquake_info(1)
        