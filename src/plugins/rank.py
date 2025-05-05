from src.plugins import Plugin
from loguru import logger
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

class RankPlugin(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        
        # 从配置文件中获取数据路径
        rank_config = self.bot.config.get("features", {}).get("rank", {})
        data_path = self.bot.config.get("data", {}).get("path", "data")
        
        self.points_file = rank_config.get("points_file", os.path.join(data_path, "points.json"))
        self.favor_file = rank_config.get("favor_file", os.path.join(data_path, "favor.json"))
        self.checkin_file = rank_config.get("checkin_file", os.path.join(data_path, "checkin.json"))
        self.default_limit = rank_config.get("default_limit", 10)
        self.max_limit = rank_config.get("max_limit", 20)
        
        self.points = {}
        self.favor = {}
        self.checkin = {}
    
    async def on_load(self):
        logger.info("排行榜插件已加载")
        await self.load_data()
    
    async def load_data(self):
        """加载所有数据"""
        # 加载积分数据
        if os.path.exists(self.points_file):
            try:
                with open(self.points_file, "r", encoding="utf-8") as f:
                    self.points = json.load(f)
                    # 确保键是字符串类型
                    self.points = {str(k): v for k, v in self.points.items()}
            except Exception as e:
                logger.error(f"加载积分数据失败: {e}")
                self.points = {}
        
        # 加载好感度数据
        if os.path.exists(self.favor_file):
            try:
                with open(self.favor_file, "r", encoding="utf-8") as f:
                    self.favor = json.load(f)
                    # 确保键是字符串类型
                    self.favor = {str(k): v for k, v in self.favor.items()}
            except Exception as e:
                logger.error(f"加载好感度数据失败: {e}")
                self.favor = {}
        
        # 加载签到数据
        if os.path.exists(self.checkin_file):
            try:
                with open(self.checkin_file, "r", encoding="utf-8") as f:
                    self.checkin = json.load(f)
                    # 确保键是字符串类型
                    self.checkin = {str(k): v for k, v in self.checkin.items()}
            except Exception as e:
                logger.error(f"加载签到数据失败: {e}")
                self.checkin = {}
        
        # 记录数据加载情况
        logger.info(f"已加载积分数据: {len(self.points)}条记录")
        logger.info(f"已加载好感度数据: {len(self.favor)}条记录")
        logger.info(f"已加载签到数据: {len(self.checkin)}条记录")
    
    async def get_points_rank(self, limit: int = 10) -> str:
        """获取积分排行榜"""
        try:
            if not self.points:
                return "暂无积分数据喵~"
            
            # 确保显示至少10人，除非数据不足
            if limit < 10:
                limit = 10
            
            # 排序用户（按积分降序）
            # 确保key是字符串类型
            sorted_users = sorted(
                self.points.items(), 
                key=lambda x: x[1].get("points", 0), 
                reverse=True
            )[:limit]
            
            result = "🏆 积分排行榜 🏆\n\n"
            for i, (user_id, data) in enumerate(sorted_users, 1):
                # 尝试获取用户昵称
                nickname = await self._get_user_nickname(user_id)
                points = data.get("points", 0)
                
                # 前三名使用奖牌图标
                if i == 1:
                    prefix = "🥇"
                elif i == 2:
                    prefix = "🥈"
                elif i == 3:
                    prefix = "🥉"
                else:
                    prefix = f"{i}."
                
                result += f"{prefix} {nickname} - {points}分\n"
            
            return result.strip()
        except Exception as e:
            logger.error(f"获取积分排行榜失败: {e}")
            return f"获取积分排行榜失败: {str(e)}喵~"
    
    async def get_favor_rank(self, limit: int = 10) -> str:
        """获取好感度排行榜"""
        try:
            if not self.favor:
                return "暂无好感度数据喵~"
            
            # 排序用户（按好感度降序）
            sorted_users = sorted(
                self.favor.items(), 
                key=lambda x: x[1].get("favor", 0), 
                reverse=True
            )[:limit]
            
            result = "❤️ 好感度排行榜 ❤️\n\n"
            for i, (user_id, data) in enumerate(sorted_users, 1):
                # 尝试获取用户昵称
                nickname = await self._get_user_nickname(user_id)
                favor = data.get("favor", 0)
                level = self._get_favor_level(favor)
                result += f"{i}. {nickname} - {favor}点 ({level})\n"
            
            return result.strip()
        except Exception as e:
            logger.error(f"获取好感度排行榜失败: {e}")
            return f"获取好感度排行榜失败: {str(e)}喵~"
    
    async def get_checkin_rank(self, limit: int = 10) -> str:
        """获取签到排行榜"""
        try:
            if not self.checkin:
                return "暂无签到数据喵~"
            
            # 排序用户（按签到天数降序）
            sorted_users = sorted(
                self.checkin.items(), 
                key=lambda x: x[1].get("total_days", 0), 
                reverse=True
            )[:limit]
            
            result = "📅 签到排行榜 📅\n\n"
            for i, (user_id, data) in enumerate(sorted_users, 1):
                # 尝试获取用户昵称
                nickname = await self._get_user_nickname(user_id)
                total_days = data.get("total_days", 0)
                streak_days = data.get("streak_days", 0)
                result += f"{i}. {nickname} - 累计{total_days}天 (连续{streak_days}天)\n"
            
            return result.strip()
        except Exception as e:
            logger.error(f"获取签到排行榜失败: {e}")
            return f"获取签到排行榜失败: {str(e)}喵~"
    
    async def get_overall_rank(self, limit: int = 10) -> str:
        """获取综合排行榜"""
        try:
            # 合并所有数据
            all_users = set()
            for user_id in self.points.keys():
                all_users.add(user_id)
            for user_id in self.favor.keys():
                all_users.add(user_id)
            for user_id in self.checkin.keys():
                all_users.add(user_id)
            
            if not all_users:
                return "暂无排行榜数据喵~"
            
            # 计算综合分数
            user_scores = []
            for user_id in all_users:
                points = self.points.get(user_id, {}).get("points", 0)
                favor = self.favor.get(user_id, {}).get("favor", 0)
                checkin_days = self.checkin.get(user_id, {}).get("total_days", 0)
                
                # 简单的综合计分公式：积分+好感度*5+签到天数*10
                total_score = points + favor * 5 + checkin_days * 10
                user_scores.append((user_id, total_score))
            
            # 排序用户
            sorted_users = sorted(user_scores, key=lambda x: x[1], reverse=True)[:limit]
            
            result = "🌟 综合排行榜 🌟\n\n"
            for i, (user_id, score) in enumerate(sorted_users, 1):
                # 尝试获取用户昵称
                nickname = await self._get_user_nickname(user_id)
                result += f"{i}. {nickname} - {score}分\n"
            
            return result.strip()
        except Exception as e:
            logger.error(f"获取综合排行榜失败: {e}")
            return f"获取综合排行榜失败: {str(e)}喵~"
    
    async def _get_user_nickname(self, user_id: str) -> str:
        """获取用户昵称"""
        try:
            # 将user_id转换为整数
            uid = int(user_id)
            
            # 尝试获取用户信息
            user_info = await self.bot.api.get_stranger_info(user_id=uid)
            
            # 如果成功获取用户信息，返回昵称
            if user_info and "data" in user_info and "nickname" in user_info["data"]:
                return user_info["data"]["nickname"]
            
            # 如果没有获取到用户信息，返回QQ号
            return f"用户{user_id}"
        except Exception as e:
            logger.debug(f"获取用户昵称失败: {e}")
            return f"用户{user_id}"
    
    def _get_favor_level(self, favor: int) -> str:
        """获取好感度等级"""
        if favor >= 1000:
            return "形影不离"
        elif favor >= 800:
            return "心心相印"
        elif favor >= 600:
            return "亲密无间"
        elif favor >= 400:
            return "情投意合"
        elif favor >= 200:
            return "熟悉"
        elif favor >= 100:
            return "友好"
        elif favor >= 50:
            return "普通"
        else:
            return "陌生"
    
    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令"""
        logger.info(f"RankPlugin处理命令: command={command}, args='{args}', user_id={user_id}, group_id={group_id}")
        
        if command in ["points_rank", "积分排行", "积分榜"]:
            limit = self.default_limit
            if args.strip() and args.strip().isdigit():
                limit = min(int(args.strip()), self.max_limit)
            return await self.get_points_rank(limit)
        
        elif command in ["favor_rank", "好感度排行", "好感榜"]:
            limit = self.default_limit
            if args.strip() and args.strip().isdigit():
                limit = min(int(args.strip()), self.max_limit)
            return await self.get_favor_rank(limit)
        
        elif command in ["checkin_rank", "签到排行", "签到榜"]:
            limit = self.default_limit
            if args.strip() and args.strip().isdigit():
                limit = min(int(args.strip()), self.max_limit)
            return await self.get_checkin_rank(limit)
        
        elif command in ["rank", "排行榜", "排名"]:
            if not args:
                return await self.get_overall_rank(self.default_limit)
            
            args = args.strip().lower()
            if args in ["points", "积分"]:
                return await self.get_points_rank(self.default_limit)
            elif args in ["favor", "好感度"]:
                return await self.get_favor_rank(self.default_limit)
            elif args in ["checkin", "签到"]:
                return await self.get_checkin_rank(self.default_limit)
            elif args.isdigit():
                return await self.get_overall_rank(min(int(args), self.max_limit))
            else:
                return "未知的排行榜类型喵~\n可用类型：积分、好感度、签到"
        
        logger.warning(f"未知的排行榜命令: {command}")