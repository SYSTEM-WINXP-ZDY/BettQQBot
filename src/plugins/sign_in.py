from src.plugins import Plugin
from loguru import logger
from typing import Dict, Any, List, Optional
import random
import time
import os
import json
import datetime
from datetime import datetime, timedelta

class SignInPlugin(Plugin):
    """签到插件"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.commands = {
            "sign_in": {
                "function": self._do_sign_in,
                "description": "每日签到",
                "admin_only": False
            },
            "points": {
                "function": self._show_points,
                "description": "查看积分",
                "admin_only": False
            },
            "rank": {
                "function": self.rank_command,
                "description": "查看积分排行榜",
                "admin_only": False
            },
            "help": {
                "function": self.help_command,
                "description": "查看帮助信息",
                "admin_only": False
            },
            "喵": {
                "function": self.catgirl_command,
                "description": "与猫娘互动",
                "admin_only": False
            }
        }
        
        # 猫娘互动回复列表
        self.catgirl_responses = [
            "没有配置互动。"
        ]
    
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
        
        # 创建事件字典
        event = {
            "user_id": user_id,
            "group_id": group_id
        }
        
        # 根据命令名称或函数名称执行对应的命令
        if command in ["sign_in", "签到", "打卡", "check in"]:
            await self._do_sign_in(event)
            return ""
        elif command in ["show_points", "我的积分", "积分", "points", "查询积分"]:
            await self._show_points(event)
            return ""
        elif command in ["rank"]:
            await self.rank_command(event)
            return ""
        elif command in ["help"]:
            await self.help_command(event)
            return ""
        elif command in ["喵", "猫娘", "neko"]:
            await self.catgirl_command(event)
            return ""
        else:
            logger.warning(f"未知的签到插件命令: {command}")
            return f"未知的命令: {command}"
        
    async def _do_sign_in(self, event: Dict[str, Any]) -> None:
        """处理签到命令"""
        user_id = event["user_id"]
        group_id = event.get("group_id")
        
        # 从积分文件读取最新数据
        points_file = os.path.join(self.data_dir, "points.json")
        points_data = {}
        if os.path.exists(points_file):
            try:
                with open(points_file, "r", encoding="utf-8") as f:
                    points_data = json.load(f)
            except Exception as e:
                logger.error(f"读取积分数据失败: {e}")
        
        # 确保用户ID存在于数据中
        user_id_str = str(user_id)
        if user_id_str not in points_data:
            points_data[user_id_str] = {
                "points": 0,
                "last_sign_in": None,
                "favorability": 0
            }
        
        # 检查是否已经签到
        last_sign_in = points_data[user_id_str].get("last_sign_in")
        if last_sign_in:
            try:
                last_date = datetime.fromisoformat(last_sign_in)
                if last_date.date() == datetime.now().date():
                    if group_id:
                        await self.bot.api.send_group_msg(
                            group_id=group_id,
                            message="你今天已经签到过了哦~"
                        )
                    else:
                        await self.bot.api.send_private_msg(
                            user_id=user_id,
                            message="你今天已经签到过了哦~"
                        )
                    return
            except Exception as e:
                logger.error(f"解析签到日期失败: {e}")
        
        # 生成随机积分
        points_reward = random.randint(self.min_reward, self.max_reward)
        
        # 计算连续签到天数和额外奖励
        current_points = points_data[user_id_str].get("points", 0)
        current_favorability = points_data[user_id_str].get("favorability", 0)
        
        # 更新用户数据
        points_data[user_id_str]["points"] = current_points + points_reward
        points_data[user_id_str]["last_sign_in"] = datetime.now().isoformat()
        
        # 增加好感度（每次签到增加1点好感度）
        favorability_reward = 1
        points_data[user_id_str]["favorability"] = min(100, current_favorability + favorability_reward)
        
        # 保存更新后的数据
        try:
            with open(points_file, "w", encoding="utf-8") as f:
                json.dump(points_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存积分数据失败: {e}")
        
        # 发送签到成功消息
        total_points = points_data[user_id_str]["points"]
        total_favorability = points_data[user_id_str]["favorability"]
        
        message = f"签到成功！\n获得 {points_reward} 积分和 {favorability_reward} 点好感度！\n当前总积分：{total_points}\n当前好感度：{total_favorability}"
        
        if group_id:
            await self.bot.api.send_group_msg(
                group_id=group_id,
                message=message
            )
        else:
            await self.bot.api.send_private_msg(
                user_id=user_id,
                message=message
            )
        
    async def _show_points(self, event: Dict[str, Any]) -> None:
        """显示用户积分"""
        user_id = event["user_id"]
        group_id = event.get("group_id")
        user_data = self.bot.user_manager.get_user_data(user_id)
        points = user_data.get("points", 0)
        
        if group_id:
            await self.bot.api.send_group_msg(
                group_id=group_id,
                message=f"你当前的积分是：{points}"
            )
        else:
            await self.bot.api.send_private_msg(
                user_id=user_id,
                message=f"你当前的积分是：{points}"
            )
    
    async def rank_command(self, event: Dict[str, Any]) -> None:
        """显示积分排行榜"""
        user_id = event["user_id"]
        group_id = event.get("group_id")
        all_users = self.bot.user_manager.get_all_users()
        
        # 按积分排序
        sorted_users = sorted(
            all_users.items(),
            key=lambda x: x[1].get("points", 0),
            reverse=True
        )
        
        # 生成排行榜消息
        message = "❤️ 积分排行榜 ❤️\n"
        for i, (uid, data) in enumerate(sorted_users[:10], 1):
            points = data.get("points", 0)
            message += f"{i}. 用户 {uid} - {points} 点\n"
        
        # 根据是否在群聊中决定发送方式
        if group_id:
            await self.bot.api.send_group_msg(
                group_id=group_id,
                message=message
            )
        else:
            await self.bot.api.send_private_msg(
                user_id=user_id,
                message=message
            )
    
    async def help_command(self, event: Dict[str, Any]) -> None:
        """显示帮助信息"""
        user_id = event["user_id"]
        group_id = event.get("group_id")
        help_text = """签到系统命令：
/sign_in - 每日签到
/points - 查看积分
/rank - 查看积分排行榜
/喵 - 与猫娘互动
/help - 显示此帮助信息"""
        
        if group_id:
            await self.bot.api.send_group_msg(
                group_id=group_id,
                message=help_text
            )
        else:
            await self.bot.api.send_private_msg(
                user_id=user_id,
                message=help_text
            )
        
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
        
    async def catgirl_command(self, event: Dict[str, Any]) -> None:
        """猫娘互动命令"""
        user_id = event["user_id"]
        group_id = event.get("group_id")
        response = random.choice(self.catgirl_responses)
        
        if group_id:
            await self.bot.api.send_group_msg(
                group_id=group_id,
                message=response
            )
        else:
            await self.bot.api.send_private_msg(
                user_id=user_id,
                message=response
            ) 