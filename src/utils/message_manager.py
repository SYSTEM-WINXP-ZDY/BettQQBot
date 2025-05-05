from loguru import logger
from typing import Dict, Any, Optional, List, Union
import time

class MessageManager:
    """消息管理器，用于管理机器人发送的所有消息"""
    
    def __init__(self):
        self.message_counter = 0
        self.message_history: Dict[int, Dict[str, Any]] = {}
        
    def initialize(self):
        """初始化消息管理器"""
        logger.info("初始化消息管理器...")
        self.message_counter = 0
        self.message_history = {}
        logger.info("消息管理器初始化完成")
        
    def get_next_id(self) -> int:
        """获取下一个消息ID"""
        message_id = self.message_counter
        self.message_counter += 1
        return message_id
        
    def add_message(self, content: str, response: str, user_id: Union[int, str], group_id: Optional[Union[int, str]] = None) -> int:
        """添加消息到历史记录
        
        Args:
            content: 用户发送的消息内容
            response: 机器人的回复
            user_id: 用户ID (整数或字符串)
            group_id: 群ID，私聊消息为None (整数或字符串)
        
        Returns:
            消息ID
        """
        message_id = self.get_next_id()
        self.message_history[message_id] = {
            "user_id": str(user_id),  # 确保存储为字符串类型
            "group_id": str(group_id) if group_id is not None else None,  # 确保存储为字符串类型
            "content": content,
            "response": response,
            "time": time.time(),
            "real_message_id": None  # API返回的真实消息ID
        }
        
        # 不在控制台记录任何消息内容或ID
        return message_id
        
    def update_real_message_id(self, message_id: int, real_message_id: Any) -> bool:
        """更新消息的真实ID
        
        Args:
            message_id: 消息ID
            real_message_id: API返回的真实消息ID
            
        Returns:
            是否成功更新
        """
        if message_id in self.message_history:
            self.message_history[message_id]["real_message_id"] = real_message_id
            # 不在控制台显示消息ID更新信息
            return True
        return False
        
    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """获取消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            消息信息
        """
        return self.message_history.get(message_id)
        
    def remove_message(self, message_id: int) -> bool:
        """从历史记录中删除消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            是否成功删除
        """
        if message_id in self.message_history:
            del self.message_history[message_id]
            return True
        return False
        
    def format_response(self, response: str, message_id: Optional[int] = None) -> str:
        """格式化响应消息
        
        Args:
            response: 原始响应消息
            message_id: 消息ID
            
        Returns:
            str: 格式化后的消息
        """
        # 不再添加消息ID到消息中
        return response
        
    def get_user_messages(self, user_id: Union[int, str], group_id: Optional[Union[int, str]] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户的消息历史
        
        Args:
            user_id: 用户ID (整数或字符串)
            group_id: 群ID，私聊消息为None (整数或字符串)
            limit: 最大返回数量
            
        Returns:
            消息历史列表
        """
        user_id_str = str(user_id)  # 确保是字符串类型
        group_id_str = str(group_id) if group_id is not None else None  # 确保是字符串类型
        
        messages = []
        for msg_id, msg in self.message_history.items():
            if msg["user_id"] == user_id_str:
                if group_id_str is None or msg["group_id"] == group_id_str:
                    messages.append({"id": msg_id, **msg})
                    
        # 按时间排序并限制数量
        messages.sort(key=lambda x: x["time"], reverse=True)
        return messages[:limit] 