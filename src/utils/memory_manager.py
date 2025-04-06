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
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
                return True
        except Exception as e:
            logger.error(f"保存记忆文件出错: {file_path}, {e}")
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
        
    def format_memories_for_prompt(self, memories: List[Dict[str, Any]]) -> str:
        formatted = ""
        
        for i, memory in enumerate(memories):
            role = memory["role"]
            content = memory["content"]
            
            formatted += f"{role}: {content}\n\n"
            
        return formatted.strip() 