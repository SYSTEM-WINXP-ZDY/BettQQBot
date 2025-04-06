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
        """执行命令
        
        Args:
            command: 命令名称或函数名称
            args: 命令参数
            user_id: 用户ID
            group_id: 群ID，私聊消息为None
            
        Returns:
            命令执行结果
        """
        logger.debug(f"SignInPlugin处理命令: {command}, 参数: {args}")
        
        # 根据命令名称或函数名称执行对应的命令
        if command in ["sign_in", "签到", "打卡", "check in"]:
            return await self._do_sign_in(user_id, group_id)
        elif command in ["show_points", "我的积分", "积分", "points", "查询积分"]:
            return await self._show_points(user_id)
        else:
            logger.warning(f"未知的签到插件命令: {command}")
            return f"未知的命令: {command}"
        
    async def _do_sign_in(self, user_id: int, group_id: Optional[int] = None) -> str:
        """执行签到"""
        # 检查今天是否已经签到
        user_data = self._load_user_data(user_id)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 初始化好感度
        if "favorability" not in user_data:
            user_data["favorability"] = 0
            
        # 初始化累计签到天数
        if "total_sign_days" not in user_data:
            user_data["total_sign_days"] = 0
        
        if user_data.get("last_sign_in") == today:
            days = user_data.get("continuous_days", 1)
            total_days = user_data.get("total_sign_days", 0)
            favor = user_data.get("favorability", 0)
            return f"今天已经签到过了喵~\n当前积分: {user_data.get('points', 0)}，连续签到: {days}天\n累计签到: {total_days}天，好感度: {favor}"
            
        # 计算连续签到天数
        last_date = user_data.get("last_sign_in", "")
        continuous_days = user_data.get("continuous_days", 0)
        total_sign_days = user_data.get("total_sign_days", 0) + 1  # 增加累计签到天数
        
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
        
        # 增加好感度奖励
        favor_gain = random.randint(1, 3)  # 每次签到随机增加1-3点好感度
        favorability = user_data.get("favorability", 0) + favor_gain
            
        # 更新用户数据
        points = user_data.get("points", 0) + reward
        user_data.update({
            "last_sign_in": today,
            "continuous_days": continuous_days,
            "total_sign_days": total_sign_days,
            "points": points,
            "favorability": favorability
        })
        
        # 保存数据
        self._save_user_data(user_id, user_data)
        
        # 生成回复
        reply = f"签到成功喵~\n获得 {reward} 积分"
        if continuous_days > 1:
            reply += f"（连续签到 {continuous_days} 天，奖励增加）"
        reply += f"\n当前积分: {points}"
        reply += f"\n累计签到: {total_sign_days}天"
        reply += f"\n好感度: {favorability} (+{favor_gain})"
        
        # 好感度提示
        if favorability >= 100:
            reply += "\n（好感度已满，主人对我很满意喵~）"
        elif favorability >= 80:
            reply += "\n（主人很喜欢我喵~）"
        elif favorability >= 50:
            reply += "\n（主人开始喜欢我了喵~）"
        elif favorability >= 30:
            reply += "\n（主人对我的好感提升了喵~）"
        elif favorability >= 10:
            reply += "\n（主人对我略有好感喵~）"
        else:
            reply += "\n（主人还不太了解我喵...）"
        
        return reply
        
    async def _show_points(self, user_id: int) -> str:
        """查询积分"""
        user_data = self._load_user_data(user_id)
        points = user_data.get("points", 0)
        continuous_days = user_data.get("continuous_days", 0)
        total_sign_days = user_data.get("total_sign_days", 0)
        favorability = user_data.get("favorability", 0)
        last_sign_in = user_data.get("last_sign_in", "从未签到")
        
        result = f"积分查询结果喵~\n当前积分: {points}\n连续签到: {continuous_days}天\n累计签到: {total_sign_days}天\n好感度: {favorability}\n上次签到: {last_sign_in}"
        
        # 好感度提示
        if favorability >= 100:
            result += "\n（好感度已满，主人对我很满意喵~）"
        elif favorability >= 80:
            result += "\n（主人很喜欢我喵~）"
        elif favorability >= 50:
            result += "\n（主人开始喜欢我了喵~）"
        elif favorability >= 30:
            result += "\n（主人对我的好感提升了喵~）"
        elif favorability >= 10:
            result += "\n（主人对我略有好感喵~）"
        else:
            result += "\n（主人还不太了解我喵...）"
            
        return result
        
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