from typing import Dict, List, Any, Callable, Optional, Union
from loguru import logger

class CommandManager:
    """命令管理器，用于处理自定义命令"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化命令管理器
        
        Args:
            config: 命令配置
        """
        self.enabled = config.get("enabled", False)
        self.prefix = config.get("prefix", "")
        self.case_sensitive = config.get("case_sensitive", False)
        self.commands = {}
        self.aliases = {}
        
        # 加载命令配置
        if self.enabled:
            self._load_commands(config.get("commands", []))
            logger.info(f"命令管理器已加载，共 {len(self.commands)} 个命令")
        else:
            logger.info("命令管理器未启用")
            
    def _load_commands(self, commands_config: List[Dict[str, Any]]):
        """加载命令配置
        
        Args:
            commands_config: 命令配置列表
        """
        for cmd_config in commands_config:
            if not cmd_config.get("enabled", True):
                continue
                
            name = cmd_config["name"]
            if not self.case_sensitive:
                name = name.lower()
                
            self.commands[name] = {
                "plugin": cmd_config["plugin"],
                "function": cmd_config["function"],
                "description": cmd_config.get("description", ""),
                "admin_only": cmd_config.get("admin_only", False)
            }
            
            # 添加别名
            for alias in cmd_config.get("aliases", []):
                if not self.case_sensitive:
                    alias = alias.lower()
                self.aliases[alias] = name
                
            logger.debug(f"已加载命令: {name}")
            
    def is_command(self, text: str) -> bool:
        """检查消息是否是命令
        
        Args:
            text: 消息文本
            
        Returns:
            是否是命令
        """
        if not self.enabled or not text:
            return False
            
        # 去除前缀
        if self.prefix and text.startswith(self.prefix):
            text = text[len(self.prefix):]
        
        # 提取命令部分
        parts = text.split(None, 1)
        cmd = parts[0] if parts else ""
        
        if not self.case_sensitive:
            cmd = cmd.lower()
            
        # 检查是否是命令或别名
        return cmd in self.commands or cmd in self.aliases
        
    def parse_command(self, text: str) -> Optional[Dict[str, Any]]:
        """解析命令
        
        Args:
            text: 消息文本
            
        Returns:
            解析后的命令信息，如果不是命令则返回None
        """
        if not self.is_command(text):
            return None
            
        # 去除前缀
        if self.prefix and text.startswith(self.prefix):
            text = text[len(self.prefix):]
        
        # 分割命令和参数
        parts = text.split(None, 1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        if not self.case_sensitive:
            cmd = cmd.lower()
            
        # 检查是否是别名，如果是则转换为原命令
        if cmd in self.aliases:
            cmd = self.aliases[cmd]
            
        # 获取命令信息
        cmd_info = self.commands.get(cmd)
        if not cmd_info:
            return None
            
        return {
            "command": cmd,
            "args": args,
            "plugin": cmd_info["plugin"],
            "function": cmd_info["function"],
            "admin_only": cmd_info["admin_only"]
        }
    
    def get_command_list(self) -> List[Dict[str, Any]]:
        """获取所有命令列表
        
        Returns:
            命令列表
        """
        result = []
        for name, info in self.commands.items():
            aliases = [alias for alias, target in self.aliases.items() if target == name]
            result.append({
                "name": name,
                "plugin": info["plugin"],
                "function": info["function"],
                "description": info["description"],
                "admin_only": info["admin_only"],
                "aliases": aliases
            })
        return result 