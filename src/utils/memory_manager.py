import os
import json
import time
from loguru import logger
from typing import Dict, List, Any, Optional, Tuple

class MemoryManager:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        self.max_history = config.get("max_history", 14)
        self.memory_dir = os.path.join("data", "memories")
        
        if self.enabled:
            os.makedirs(self.memory_dir, exist_ok=True)
            logger.info(f"记忆管理器已启用，最大历史记录数: {self.max_history}")
        else:
            logger.info("记忆管理器已禁用")
            
    def _get_memory_file(self, user_id: int, group_id: Optional[int] = None) -> str:
        if group_id:
            return os.path.join(self.memory_dir, f"{user_id}_{group_id}.json")
        else:
            return os.path.join(self.memory_dir, f"{user_id}.json")
            
    def _load_memories_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        memories = []
        
        if not os.path.exists(file_path):
            return []
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                memories = json.load(f)
                if not isinstance(memories, list):
                    logger.error(f"记忆文件格式错误: {file_path}")
                    return []
        except Exception as e:
            logger.error(f"加载记忆文件出错: {file_path}, {e}")
            return []
            
        return memories
        
    def _save_memories_to_file(self, file_path: str, memories: List[Dict[str, Any]]) -> bool:
        try:
            # 确保目录存在
            dir_path = os.path.dirname(file_path)
            logger.debug(f"确保记忆目录存在: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)
            
            # 添加调试日志
            logger.debug(f"正在保存记忆文件: {file_path}")
            logger.debug(f"记忆条数: {len(memories)}")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
                logger.debug(f"记忆文件保存成功: {file_path}")
                return True
        except Exception as e:
            logger.error(f"保存记忆文件出错: {file_path}, {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return False
            
    def load_memories(self, user_id: int, group_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
            
        file_path = self._get_memory_file(user_id, group_id)
        memories = self._load_memories_from_file(file_path)
        
        if memories:
            logger.debug(f"已加载 {len(memories)} 条记忆 - 用户: {user_id}{f', 群: {group_id}' if group_id else ''}")
        
        return memories
        
    def save_memory(self, user_id: int, role: str, content: str, group_id: Optional[int] = None) -> bool:
        if not self.enabled:
            return False
            
        file_path = self._get_memory_file(user_id, group_id)
        memories = self._load_memories_from_file(file_path)
        
        memory = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        
        memories.append(memory)
        
        if len(memories) > self.max_history:
            memories = memories[-self.max_history:]
            
        success = self._save_memories_to_file(file_path, memories)
        
        if success:
            logger.debug(f"已保存记忆 - 用户: {user_id}{f', 群: {group_id}' if group_id else ''}, 角色: {role}")
            
        return success
        
    def clear_memories(self, user_id: int, group_id: Optional[int] = None) -> bool:
        file_path = self._get_memory_file(user_id, group_id)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"已清除记忆 - 用户: {user_id}{f', 群: {group_id}' if group_id else ''}")
                return True
            except Exception as e:
                logger.error(f"清除记忆文件出错: {file_path}, {e}")
                return False
        return True
        
    def remove_specific_memory(self, user_id: int, user_content: str, assistant_content: str, group_id: Optional[int] = None) -> bool:
        """从记忆中移除特定的用户消息和对应的回复"""
        if not self.enabled:
            return False
        
        file_path = self._get_memory_file(user_id, group_id)
        memories = self._load_memories_from_file(file_path)
        
        # 如果没有记忆，直接返回
        if not memories:
            return True
            
        # 查找并移除特定内容的记忆
        # 我们需要同时移除用户的消息和助手的回复
        i = 0
        removed = False
        while i < len(memories) - 1:  # -1 是因为我们每次需要检查两条消息
            if (memories[i]["role"] == "user" and memories[i]["content"] == user_content and
                memories[i+1]["role"] == "assistant" and memories[i+1]["content"] == assistant_content):
                # 找到匹配的消息，移除这两条
                memories.pop(i)  # 移除用户消息
                memories.pop(i)  # 移除助手回复（之前的i+1，移除后索引变为i）
                removed = True
                logger.debug(f"已从记忆中移除特定对话 - 用户: {user_id}{f', 群: {group_id}' if group_id else ''}")
                break
            i += 1
        
        if removed:
            # 保存修改后的记忆
            success = self._save_memories_to_file(file_path, memories)
            return success
        else:
            logger.debug(f"未找到要移除的特定对话 - 用户: {user_id}{f', 群: {group_id}' if group_id else ''}")
            return False
        
    def format_memories_for_prompt(self, memories: List[Dict[str, Any]]) -> str:
        formatted = ""
        
        for i, memory in enumerate(memories):
            role = memory["role"]
            content = memory["content"]
            
            formatted += f"{role}: {content}\n\n"
            
        return formatted.strip() 