import json
from pathlib import Path
from loguru import logger
from typing import Dict, Union

class UserManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.user_data = {}  # 初始化用户数据字典

    async def load(self):
        """加载用户数据"""
        try:
            if not self.db_path.exists():
                logger.info(f"用户数据文件不存在，将创建新文件: {self.db_path}")
                # 确保目录存在
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                self.user_data = {}
            else:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.user_data = json.load(f)
                logger.info(f"已加载 {len(self.user_data)} 个用户的数据")
            return True
        except Exception as e:
            logger.error(f"加载用户数据失败: {e}")
            self.user_data = {}
            return False

    def get_all_users(self) -> dict:
        """获取所有用户数据
        
        Returns:
            dict: 所有用户的数据字典
        """
        try:
            if not self.db_path.exists():
                return {}
                
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"获取所有用户数据失败: {e}")
            return {}

    def get_user(self, user_id: str) -> dict:
        """获取用户数据
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户数据
        """
        try:
            users = self.get_all_users()
            return users.get(str(user_id), {})
        except Exception as e:
            logger.error(f"获取用户数据失败: {e}")
            return {}

    def save_user(self, user_id: str, data: dict) -> bool:
        """保存用户数据
        
        Args:
            user_id: 用户ID
            data: 用户数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            users = self.get_all_users()
            users[str(user_id)] = data
            
            # 确保目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
            return False

    def update_favorability(self, user_id: str, change: int) -> tuple[int, bool]:
        """更新用户好感度
        
        Args:
            user_id: 用户ID
            change: 好感度变化值，正数为增加，负数为减少
            
        Returns:
            tuple[int, bool]: (新的好感度值, 是否更新成功)
        """
        try:
            user_data = self.get_user(user_id)
            current_favor = user_data.get("favorability", 0)
            
            # 更新好感度，确保在0-100之间
            new_favor = max(0, min(100, current_favor + change))
            user_data["favorability"] = new_favor
            
            # 保存更新后的数据
            success = self.save_user(user_id, user_data)
            return new_favor, success
        except Exception as e:
            logger.error(f"更新好感度失败: {e}")
            return 0, False

    def get_user_data(self, user_id: Union[int, str]) -> Dict:
        """获取用户数据"""
        user_id = str(user_id)
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "points": 0,
                "last_sign_in": None,
                "favorability": 0
            }
        return self.user_data[user_id]
        
    def get_favorability(self, user_id: Union[int, str]) -> int:
        """获取用户好感度"""
        user_data = self.get_user_data(user_id)
        return user_data.get("favorability", 0)
        
    def get_favorability_level(self, favorability: int) -> str:
        """根据好感度获取等级"""
        if favorability >= 100:
            return "挚友"
        elif favorability >= 50:
            return "友好"
        elif favorability >= 20:
            return "熟悉"
        elif favorability >= 0:
            return "普通"
        elif favorability >= -20:
            return "陌生"
        elif favorability >= -50:
            return "冷淡"
        else:
            return "敌对"
            
    def save_user_data(self, user_id: Union[int, str], data: Dict) -> bool:
        """保存用户数据
        
        Args:
            user_id: 用户ID
            data: 用户数据字典
            
        Returns:
            bool: 是否保存成功
        """
        try:
            user_id = str(user_id)
            self.user_data[user_id] = data
            
            # 保存到文件
            users = self.get_all_users()
            users[user_id] = data
            
            # 确保目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
                
            logger.info(f"用户 {user_id} 的数据已保存")
            return True
        except Exception as e:
            logger.error(f"保存用户 {user_id} 的数据失败: {e}")
            return False 