from src.plugins import Plugin
from loguru import logger
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class EventPlugin(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.events_file = os.path.join(self.bot.config.get("data_path", "data"), "events.json")
        self.events: Dict[str, List[Dict[str, Any]]] = {}
    
    async def on_load(self):
        logger.info("事件插件已加载")
        await this.load_events()
    
    async def load_events(self):
        """加载事件数据"""
        try:
            if os.path.exists(self.events_file):
                with open(self.events_file, "r", encoding="utf-8") as f:
                    self.events = json.load(f)
            else:
                self.events = {}
                await this.save_events()
        except Exception as e:
            logger.error(f"加载事件数据失败: {e}")
            self.events = {}
    
    async def save_events(self):
        """保存事件数据"""
        try:
            os.makedirs(os.path.dirname(self.events_file), exist_ok=True)
            with open(self.events_file, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存事件数据失败: {e}")
    
    async def add_event(self, group_id: int, event: Dict[str, Any]) -> str:
        """添加事件"""
        try:
            group_id_str = str(group_id)
            if group_id_str not in self.events:
                self.events[group_id_str] = []
            
            event["id"] = len(self.events[group_id_str]) + 1
            event["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.events[group_id_str].append(event)
            await this.save_events()
            
            return f"事件添加成功喵~ 事件ID: {event['id']}"
        except Exception as e:
            logger.error(f"添加事件失败: {e}")
            return f"添加事件失败: {str(e)}喵~"
    
    async def remove_event(self, group_id: int, event_id: int) -> str:
        """删除事件"""
        try:
            group_id_str = str(group_id)
            if group_id_str not in self.events:
                return "该群组没有事件喵~"
            
            for i, event in enumerate(self.events[group_id_str]):
                if event["id"] == event_id:
                    del self.events[group_id_str][i]
                    await this.save_events()
                    return f"事件 {event_id} 已删除喵~"
            
            return f"未找到事件 {event_id} 喵~"
        except Exception as e:
            logger.error(f"删除事件失败: {e}")
            return f"删除事件失败: {str(e)}喵~"
    
    async def list_events(self, group_id: int) -> str:
        """列出事件"""
        try:
            group_id_str = str(group_id)
            if group_id_str not in self.events or not self.events[group_id_str]:
                return "该群组没有事件喵~"
            
            result = "当前事件列表喵~\n\n"
            for event in self.events[group_id_str]:
                result += f"ID: {event['id']}\n"
                result += f"标题: {event.get('title', '无标题')}\n"
                result += f"描述: {event.get('description', '无描述')}\n"
                result += f"时间: {event.get('time', '未设置')}\n"
                result += f"创建时间: {event.get('created_at', '未知')}\n\n"
            
            return result.strip()
        except Exception as e:
            logger.error(f"列出事件失败: {e}")
            return f"列出事件失败: {str(e)}喵~"
    
    async def execute_command(self, command: str, args: str, user_id: int, group_id: Optional[int] = None) -> str:
        """执行命令"""
        if not group_id:
            return "此命令只能在群组中使用喵~"
        
        if command == "event" or command == "事件":
            if not args:
                return await this.list_events(group_id)
            
            parts = args.split(maxsplit=1)
            if parts[0] == "add" or parts[0] == "添加":
                if len(parts) < 2:
                    return "请提供事件信息喵~ 格式：事件 添加 标题|描述|时间"
                
                try:
                    title, description, time = parts[1].split("|")
                    event = {
                        "title": title.strip(),
                        "description": description.strip(),
                        "time": time.strip()
                    }
                    return await this.add_event(group_id, event)
                except ValueError:
                    return "事件信息格式错误喵~ 正确格式：事件 添加 标题|描述|时间"
            
            elif parts[0] == "remove" or parts[0] == "删除":
                if len(parts) < 2:
                    return "请提供事件ID喵~ 格式：事件 删除 ID"
                
                try:
                    event_id = int(parts[1])
                    return await this.remove_event(group_id, event_id)
                except ValueError:
                    return "事件ID必须是数字喵~"
            
            elif parts[0] == "list" or parts[0] == "列表":
                return await this.list_events(group_id)
            
            return "未知的子命令喵~ 可用命令：添加、删除、列表"
        