from src.plugins import Plugin
from loguru import logger
from typing import Dict, Any, List, Optional
import random
import time
import os
import json
import datetime

class SignInPlugin(Plugin):
    """签到插件"""
    
    async def on_load(self):
        """插件加载"""
        logger.info("签到插件已加载")
        
        # 创建数据目录
        self.data_dir = "data/sign_in"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 读取配置
        self.config = self.bot.config["features"]["sign_in"]
        self.min_reward = self.config["rewards"]["min"]
        self.max_reward = self.config["rewards"]["max"]
        
    async def on_unload(self):
        """插件卸载"""
        logger.info("签到插件已卸载")
        
    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令"""
        if command == "sign_in":
            return await self._do_sign_in(user_id, group_id)
        elif command == "show_points":
            return await self._show_points(user_id)
        return f"未知的命令: {command}"
        
    async def _do_sign_in(self, user_id: int, group_id: Optional[int] = None) -> str:
        """执行签到"""
        # 检查今天是否已经签到
        user_data = self._load_user_data(user_id)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if user_data.get("last_sign_in") == today:
            days = user_data.get("continuous_days", 1)
            return f"今天已经签到过了喵~\n当前积分: {user_data.get('points', 0)}，连续签到: {days}天"
            
        # 计算连续签到天数
        last_date = user_data.get("last_sign_in", "")
        continuous_days = user_data.get("continuous_days", 0)
        
        if last_date:
            # 判断昨天是否签到
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            if last_date == yesterday:
                continuous_days += 1
            else:
                continuous_days = 1
        else:
            continuous_days = 1
            
        # 计算奖励
        reward = random.randint(self.min_reward, self.max_reward)
        
        # 增加连续签到加成
        if continuous_days > 1:
            bonus = min(continuous_days * 0.1, 2.0)  # 最多翻倍
            reward = int(reward * (1 + bonus))
            
        # 更新用户数据
        points = user_data.get("points", 0) + reward
        user_data.update({
            "last_sign_in": today,
            "continuous_days": continuous_days,
            "points": points
        })
        
        # 保存数据
        self._save_user_data(user_id, user_data)
        
        # 生成回复
        reply = f"签到成功喵~\n获得 {reward} 积分"
        if continuous_days > 1:
            reply += f"（连续签到 {continuous_days} 天，奖励增加）"
        reply += f"\n当前积分: {points}"
        
        return reply
        
    async def _show_points(self, user_id: int) -> str:
        """查询积分"""
        user_data = self._load_user_data(user_id)
        points = user_data.get("points", 0)
        continuous_days = user_data.get("continuous_days", 0)
        last_sign_in = user_data.get("last_sign_in", "从未签到")
        
        return f"积分查询结果喵~\n当前积分: {points}\n连续签到: {continuous_days}天\n上次签到: {last_sign_in}"
        
    def _load_user_data(self, user_id: int) -> Dict[str, Any]:
        """加载用户数据"""
        file_path = os.path.join(self.data_dir, f"{user_id}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载用户 {user_id} 的签到数据失败: {e}")
        return {}
        
    def _save_user_data(self, user_id: int, data: Dict[str, Any]):
        """保存用户数据"""
        file_path = os.path.join(self.data_dir, f"{user_id}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户 {user_id} 的签到数据失败: {e}")
    
    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        """处理私聊消息"""
        pass
        
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        """处理群消息"""
        pass 