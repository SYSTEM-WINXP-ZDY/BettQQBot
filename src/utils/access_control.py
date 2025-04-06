from typing import Dict, List, Any, Optional
from loguru import logger

class AccessControl:
    def __init__(self, config: Dict[str, Any], super_users: List[int]):
        self.enabled = config.get("enabled", False)
        self.whitelist_enabled = config.get("whitelist_enabled", False)
        self.blacklist_enabled = config.get("blacklist_enabled", True)
        
        self.user_whitelist = set(config.get("user_whitelist", []))
        self.group_whitelist = set(config.get("group_whitelist", []))
        self.user_blacklist = set(config.get("user_blacklist", []))
        self.group_blacklist = set(config.get("group_blacklist", []))
        
        self.super_users = set(super_users)
        
        logger.info(f"访问控制初始化：启用状态={self.enabled}, 白名单={self.whitelist_enabled}, 黑名单={self.blacklist_enabled}")
        
    def can_access(self, user_id: int, group_id: Optional[int] = None) -> bool:
        if not self.enabled:
            return True
            
        if user_id in self.super_users:
            return True
            
        if self.blacklist_enabled:
            if user_id in self.user_blacklist:
                return False
                
            if group_id and group_id in self.group_blacklist:
                return False
                
        if self.whitelist_enabled:
            if not (user_id in self.user_whitelist or (group_id and group_id in self.group_whitelist)):
                return False
                
        return True
        
    def add_to_whitelist(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> bool:
        if user_id:
            if user_id in self.user_whitelist:
                return False
                
            self.user_whitelist.add(user_id)
            logger.info(f"已将用户 {user_id} 添加到白名单")
            return True
            
        if group_id:
            if group_id in self.group_whitelist:
                return False
                
            self.group_whitelist.add(group_id)
            logger.info(f"已将群组 {group_id} 添加到白名单")
            return True
            
        return False
        
    def remove_from_whitelist(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> bool:
        if user_id and user_id in self.user_whitelist:
            self.user_whitelist.remove(user_id)
            logger.info(f"已将用户 {user_id} 从白名单中移除")
            return True
            
        if group_id and group_id in self.group_whitelist:
            self.group_whitelist.remove(group_id)
            logger.info(f"已将群组 {group_id} 从白名单中移除")
            return True
            
        return False
        
    def add_to_blacklist(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> bool:
        if user_id:
            if user_id in self.user_blacklist:
                return False
                
            self.user_blacklist.add(user_id)
            logger.info(f"已将用户 {user_id} 添加到黑名单")
            return True
            
        if group_id:
            if group_id in self.group_blacklist:
                return False
                
            self.group_blacklist.add(group_id)
            logger.info(f"已将群组 {group_id} 添加到黑名单")
            return True
            
        return False
        
    def remove_from_blacklist(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> bool:
        if user_id and user_id in self.user_blacklist:
            self.user_blacklist.remove(user_id)
            logger.info(f"已将用户 {user_id} 从黑名单中移除")
            return True
            
        if group_id and group_id in self.group_blacklist:
            self.group_blacklist.remove(group_id)
            logger.info(f"已将群组 {group_id} 从黑名单中移除")
            return True
            
        return False 