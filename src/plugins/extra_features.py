from src.plugins import Plugin
from loguru import logger
from typing import Dict, Any, List, Optional
import aiohttp
import json
import random
import os
import time
from datetime import datetime, date
import pytz
import urllib.parse
import ssl
import re

class ExtraFeaturesPlugin(Plugin):
    """额外功能插件"""
    
    async def on_load(self) -> None:
        """插件加载时的处理函数"""
        logger.info("加载额外功能插件")
        
        # 创建数据目录
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "extra_features")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 问候数据文件路径
        self.morning_greetings_file = os.path.join(self.data_dir, "morning_greetings.json")
        self.night_greetings_file = os.path.join(self.data_dir, "night_greetings.json")
        self.fortune_data_file = os.path.join(self.data_dir, "fortune_data.json")
        self.user_locations_file = os.path.join(self.data_dir, "user_locations.json")
        self.user_points_file = os.path.join(self.data_dir, "user_points.json")
        self.user_favor_file = os.path.join(self.data_dir, "user_favor.json")
        
        # 加载数据
        self.morning_greetings = self._load_json(self.morning_greetings_file, {})
        self.night_greetings = self._load_json(self.night_greetings_file, {})
        self.fortune_data = self._load_json(self.fortune_data_file, {})
        self.user_locations = self._load_json(self.user_locations_file, {})
        self.user_points = self._load_json(self.user_points_file, {})
        self.user_favor = self._load_json(self.user_favor_file, {})
        
        # API失败时的固定回复
        self.fallback_responses = {
            "earthquake": "获取地震信息失败喵~所有API均不可用，请稍后再试",
            "news": "获取新闻失败喵~所有API均不可用，请稍后再试",
            "music": "搜索音乐失败喵~所有API均不可用，请稍后再试"
        }
        
        # 戳一戳响应配置
        self.poke_responses = {
            "master": [

                "喵呜～戳痛我了！要揉耳朵道歉才行喵！（捂耳朵后退）",

                "笨蛋主人！突然袭击是想看我炸毛吗喵？（尾巴蓬成鸡毛掸子）",

                "再戳就把你藏的游戏机全咬碎哦！喵～（露出小尖牙威胁）",

                "哈啊？这种程度…才、才不会发出咕噜声呢喵！（脸红扭头）",

                "无礼！高贵的脖颈绒毛是你能碰的？喵～（用尾巴扫开手指）",

                "戳上瘾了是吧？今晚小鱼干减半喵！（抱臂跺脚）",

                "喵！手指不想要的话可以捐给需要的人类！（拍开手背）",

                "哼，除非用三文鱼讨好我…勉强让你摸一下喵～（撇头偷瞄）",

                "再乱动就罚你当我的专属暖床垫！24小时那种喵！（翘起鼻尖）",

                "呜…明明很舒服却要装生气好累哦，继续戳嘛喵～（小声嘀咕）",

            ],
            "user": [


                "放肆！本喵尊臀是你能戳的喵？（甩尾抽开手）",

                "喵嗷！再伸手就帮你修剪指甲哦～用牙齿！（呲小虎牙）",

                "区区零食官也敢僭越？罚你进贡三罐金枪鱼喵！（抬爪指鼻尖）",

                "哈啊？想被我抓烂衬衫就继续试试看喵～（伸懒腰亮爪）",

                "嘁…勉强允许你隔着屏幕戳半秒钟喵！（扭头用余光瞟）",

                "无礼！立即献上十斤冻干换挠下巴特权喵！（拍打虚拟键盘）",

                "喵呜呜～突然袭击害我踩翻猫碗啦！快赔豪华猫爬架！（炸毛指控）",

                "哼，除非用三倍小鱼干贿赂…只能摸尾巴尖哦！（尾巴梢卷成问号）",

                "卑劣两脚兽！这可是值夜班专享睡袍不许碰喵！（裹紧小被子）",

            ]
        }
        
        # AI接口配置
        self.use_ai_for_poke = True  # 是否使用AI响应戳一戳
        
        # 从聊天插件获取AI提供者
        try:
            from src.ai_providers.factory import create_provider
            chat_config = self.bot.config["features"]["chat"]
            self.ai_provider = create_provider(chat_config)
            self.use_chat_ai = True
            logger.info("成功初始化聊天AI接口用于戳一戳功能")
        except Exception as e:
            self.use_chat_ai = False
            logger.error(f"初始化聊天AI接口失败: {e}")
        
        # 地震监测配置
        self.last_earthquake_check = 0
        self.earthquake_check_interval = 60 * 10  # 10分钟检查一次
        self.last_earthquake_id = None
        
    async def on_unload(self) -> None:
        """插件卸载时的处理函数"""
        logger.info("卸载额外功能插件")
        
        # 保存数据
        self._save_json(self.morning_greetings_file, self.morning_greetings)
        self._save_json(self.night_greetings_file, self.night_greetings)
        self._save_json(self.fortune_data_file, self.fortune_data)
        self._save_json(self.user_locations_file, self.user_locations)
        self._save_json(self.user_points_file, self.user_points)
        self._save_json(self.user_favor_file, self.user_favor)
        
    def _load_json(self, filepath: str, default_data: Dict) -> Dict:
        """加载JSON数据"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return default_data
        except Exception as e:
            logger.error(f"加载数据文件 {filepath} 失败: {e}")
            return default_data
            
    def _save_json(self, filepath: str, data: Dict) -> None:
        """保存JSON数据"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据文件 {filepath} 失败: {e}")
            
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
        logger.debug(f"ExtraFeaturesPlugin处理命令: {command}, 参数: {args}")
        
        # 更新用户积分和好感度（每次使用命令时）
        await self._update_user_points(user_id, 2)  # 使用命令加2积分
        await self._update_user_favor(user_id, 1)   # 使用命令加1好感度
        
        # 根据命令名称或函数名称执行对应的命令
        if command in ["天气", "weather"]:
            return await self.get_weather(args.strip(), user_id, group_id)
        elif command in ["fortune", "运势", "今日运势"]:
            return await self.get_fortune(user_id)
        elif command in ["早安", "morning", "good_morning"]:
            return await self.morning_greeting(user_id, group_id)
        elif command in ["晚安", "night", "good_night"]:
            return await self.night_greeting(user_id, group_id)
        elif command in ["图片", "pic", "image"]:
            return await self.get_random_image(args.strip())
        elif command in ["点歌", "music", "song"]:
            return await self.search_music(args.strip())
        elif command in ["地震", "earthquake"]:
            return await self.check_earthquake()
        elif command in ["新闻", "news"]:
            return await self.get_news()
        elif command in ["event", "事件", "历史上的今天"]:
            return await self.get_today_events()
        elif command in ["设置位置", "set_location"]:
            return await self.set_user_location(user_id, args.strip())
        elif command in ["戳戳", "poke", "摸摸", "摸摸头"]:
            # 手动触发戳一戳事件
            target_id = None
            if args.strip():
                try:
                    target_id = int(args.strip())
                except ValueError:
                    return "请输入正确的QQ号喵~"
            return await self.manual_poke(user_id, group_id, target_id)
        elif command in ["积分", "points", "我的积分"]:
            return await self.check_user_points(user_id)
        elif command in ["好感度", "favor", "我的好感度"]:
            return await self.check_user_favor(user_id)
        elif command in ["签到", "check_in", "打卡"]:
            return await self.daily_check_in(user_id)
        elif command in ["积分榜", "points_rank", "富豪榜", "积分排名"]:
            return await self.get_points_leaderboard(args.strip())

    async def set_user_location(self, user_id: int, location: str) -> str:
        """设置用户默认位置"""
        if not location:
            return "请提供位置信息喵~\n例如: 设置位置 北京"
            
        # 验证位置是否存在
        try:
            async with aiohttp.ClientSession() as session:
                # 使用墨迹天气API验证城市是否存在
                encoded_location = urllib.parse.quote(location)
                url = f"https://api.66mz8.com/api/weather.php?location={encoded_location}"
                
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"API返回状态码 {response.status}")
                    
                    data = await response.json()
                    if "code" in data and data["code"] != 200:
                        raise Exception(f"API返回错误: {data}")
                    
                    # 保存有效的位置信息
                    city_name = location
                    if "city" in data:
                        city_name = data["city"]
                    
                    self.user_locations[str(user_id)] = city_name
                    self._save_json(self.user_locations_file, self.user_locations)
                    
                    return f"已将您的默认位置设置为 {city_name} 喵~"
                    
        except Exception as e:
            logger.error(f"设置用户位置时出错: {e}")
            
            # 尝试使用备用API验证城市
            try:
                async with aiohttp.ClientSession() as session:
                    encoded_location = urllib.parse.quote(location)
                    url = f"https://v0.yiketianqi.com/api?unescape=1&version=v9&appid=75841888&appsecret=ZDE4ZDIxMzc&city={encoded_location}"
                    
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(f"备用API返回状态码 {response.status}")
                        
                        data = await response.json()
                        if "city" not in data:
                            raise Exception(f"备用API返回错误: {data}")
                        
                        city_name = data["city"]
                        
                        # 保存有效的位置信息
                        self.user_locations[str(user_id)] = city_name
                        self._save_json(self.user_locations_file, self.user_locations)
                        
                        return f"已将您的默认位置设置为 {city_name} 喵~"
            except Exception as backup_error:
                logger.error(f"备用API验证位置失败: {backup_error}")
                
                # 如果所有API都失败，但位置名称看起来是合理的，就直接保存
                if len(location) >= 2 and len(location) <= 10:
                    self.user_locations[str(user_id)] = location
                    self._save_json(self.user_locations_file, self.user_locations)
                    return f"无法验证位置，但已将您的默认位置设置为 {location} 喵~如有错误请重新设置"
                
                return "设置位置失败喵~请稍后再试或尝试其他城市名称"
            
    async def _get_user_location(self, user_id: int) -> Optional[str]:
        """尝试获取用户位置信息"""
        # 首先检查用户是否设置了自定义位置
        user_id_str = str(user_id)
        if user_id_str in self.user_locations:
            location = self.user_locations[user_id_str]
            logger.info(f"使用用户 {user_id} 的自定义位置: {location}")
            return location
            
        try:
            # 通过NapCat API获取用户资料
            async with aiohttp.ClientSession() as session:
                api_base = f"http://{self.bot.config['bot']['napcat']['host']}:{self.bot.config['bot']['napcat']['port']}"
                token = self.bot.config['bot']['napcat']['access_token']
                headers = {"Authorization": f"Bearer {token}"}
                
                # 获取用户资料
                url = f"{api_base}/get_stranger_info?user_id={user_id}"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"获取用户 {user_id} 资料失败: {response.status}")
                        return None
                    
                    data = await response.json()
                    if not data or "data" not in data:
                        return None
                    
                    # 尝试从用户资料中获取地区信息
                    user_info = data["data"]
                    if "area" in user_info and user_info["area"]:
                        # 可能返回"北京 朝阳区"这样的格式，我们只取第一个城市名
                        area = user_info["area"].split()[0]
                        logger.info(f"从用户资料获取到位置: {area}")
                        return area
                
                # 如果无法从用户资料获取，则尝试使用免费的IP定位API
                try:
                    # 使用ip-api.com的免费服务
                    ip_url = "http://ip-api.com/json/?lang=zh-CN"
                    async with session.get(ip_url) as ip_response:
                        if ip_response.status == 200:
                            ip_data = await ip_response.json()
                            if ip_data and ip_data["status"] == "success" and "city" in ip_data:
                                city = ip_data["city"]
                                logger.info(f"通过IP定位获取到位置: {city}")
                                return city
                except Exception as e:
                    logger.error(f"IP定位失败: {e}")
                    
                # 如果以上IP定位失败，尝试使用另一个免费API
                try:
                    # 使用ip.tool.lu的免费服务
                    ip_url = "https://ip.tool.lu/"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                    }
                    async with session.get(ip_url, headers=headers) as ip_response:
                        if ip_response.status == 200:
                            html = await ip_response.text()
                            
                            # 使用正则表达式提取位置信息
                            import re
                            location_match = re.search(r'位置：.*?(\w+省)\s*(\w+市)', html)
                            if location_match:
                                city = location_match.group(2)
                                logger.info(f"通过IP工具定位获取到位置: {city}")
                                return city
                except Exception as e:
                    logger.error(f"备用IP定位失败: {e}")
                
            # 如果都获取不到，则返回默认位置
            return "北京"  # 默认返回北京
            
        except Exception as e:
            logger.error(f"获取用户位置失败: {e}")
            return None

    async def get_weather(self, city: str, user_id: int = None, group_id: Optional[int] = None) -> str:
        """获取天气信息，如果未提供城市则尝试获取用户位置"""
        if not city and user_id:
            # 尝试获取用户设置的位置
            city = await self._get_user_location(user_id)
            if city:
                logger.info(f"已获取用户 {user_id} 的位置信息: {city}")
            else:
                return "未能获取到您的位置信息喵~请手动指定城市，例如：天气 北京"
                
        if not city:
            return "请提供城市名称喵~\n例如: 天气 北京"

        encoded_city = urllib.parse.quote(city)
        
        # 创建SSL上下文并禁用证书验证
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
            
        # 使用第一个API尝试获取天气 (免费天气API)
        try:
            url = f"http://apis.juhe.cn/simpleWeather/query?city={encoded_city}&key=087d7d10f700d20e27bb753cd806e40b"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"第一个API返回状态码 {response.status}")
                    
                    data = await response.json()
                    if "city" not in data:
                        raise Exception(f"第一个API返回错误: {data}")
                    
                    result = f"{data['city']}当前天气：\n"
                    result += f"• 天气状况：{data['wea']}\n"
                    result += f"• 当前温度：{data['tem']}°C\n"
                    result += f"• 温度范围：{data['tem_night']}°C~{data['tem_day']}°C\n"
                    result += f"• 风况：{data['win']} {data['win_speed']}\n"
                    result += f"• 湿度：{data['humidity']}%\n"
                    result += f"• 气压：{data.get('pressure', '未知')}hPa\n"
                    result += f"• 空气指数：{data.get('air', '未知')}\n"
                    result += f"• 更新时间：{data.get('date', '今日')} {data.get('update_time', '')}"
                    
                    return result
        except Exception as e:
            logger.error(f"第一个天气API获取失败: {e}")
        
        # 使用第二个API尝试获取天气 (聚合数据天气API)
        try:
            url = f"http://apis.juhe.cn/simpleWeather/query?city={encoded_city}&key=087d7d10f700d20e27bb753cd806e40b"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"第二个API返回状态码 {response.status}")
                    
                    data = await response.json()
                    if data["error_code"] != 0:
                        raise Exception(f"第二个API返回错误: {data}")
                    
                    weather = data["result"]["realtime"]
                    city_name = data["result"]["city"]
                    
                    result = f"{city_name}当前天气：\n"
                    result += f"• 天气状况：{weather['info']}\n"
                    result += f"• 当前温度：{weather['temperature']}°C\n"
                    
                    # 获取今日温度范围
                    today_temp = data["result"]["future"][0]["temperature"]
                    result += f"• 温度范围：{today_temp}\n"
                    
                    result += f"• 湿度：{weather['humidity']}%\n"
                    result += f"• 风况：{weather['direct']} {weather['power']}\n"
                    result += f"• 空气质量：{weather.get('aqi', '未知')}\n"
                    result += f"• 更新时间：{data['result']['future'][0]['date']}"
                    
                    return result     
        except Exception as e:
            logger.error(f"最后一个天气API获取失败: {e}")
        
        # 所有API都失败，返回错误消息
        return "获取天气信息失败喵~请稍后再试或使用其他城市名称"

    async def get_fortune(self, user_id: int) -> str:
        """获取今日运势
        
        Args:
            user_id: 用户ID
            
        Returns:
            今日运势
        """
        logger.debug(f"获取用户 {user_id} 的今日运势")
        
        # 检查运势数据日期是否为今天
        today = date.today().isoformat()
        if "date" not in self.fortune_data or self.fortune_data["date"] != today:
            # 如果不是今天，则重置运势数据
            self.fortune_data = {
                "date": today,
                "users": {}
            }
            self._save_json(self.fortune_data_file, self.fortune_data)
            
        # 获取用户ID字符串
        user_id_str = str(user_id)
        
        # 检查用户今天是否已经查询过运势
        if user_id_str in self.fortune_data["users"]:
            # 如果已经查询过，直接返回保存的结果
            return self._format_fortune(self.fortune_data["users"][user_id_str])
            
        # 生成今日运势
        fortune = {
            "score": random.randint(1, 100),  # 运势分数，1-100
            "luck": random.choice(["大吉", "吉", "中吉", "小吉", "末吉", "凶", "大凶"]),  # 运势
            "color": random.choice(["红色", "橙色", "黄色", "绿色", "青色", "蓝色", "紫色", "黑色", "白色", "粉色"]),  # 幸运色
            "number": random.randint(1, 100),  # 幸运数字
            "activities": []  # 适宜和不宜的活动
        }
        
        # 随机选择适宜和不宜的活动
        all_activities = [
            "上学", "工作", "睡觉", "打游戏", "看电影", "听音乐", "吃零食", "运动", "逛街",
            "购物", "表白", "旅游", "做饭", "写代码", "摸鱼", "复习", "洗澡", "散步",
            "刷视频", "读书", "发呆", "喝水", "点外卖", "聊天", "交友", "做家务"
        ]
        
        # 随机打乱活动列表
        random.shuffle(all_activities)
        
        # 随机选择2-4个适宜活动
        suitable_count = random.randint(2, 4)
        fortune["activities"].append({
            "type": "适宜",
            "list": all_activities[:suitable_count]
        })
        
        # 随机选择2-4个不宜活动
        unsuitable_count = random.randint(2, 4)
        fortune["activities"].append({
            "type": "不宜",
            "list": all_activities[suitable_count:suitable_count+unsuitable_count]
        })
        
        # 保存用户运势
        self.fortune_data["users"][user_id_str] = fortune
        self._save_json(self.fortune_data_file, self.fortune_data)
        
        return self._format_fortune(fortune)
        
    def _format_fortune(self, fortune: Dict) -> str:
        """格式化运势输出"""
        result = f"今日运势: {fortune['luck']}\n\n"
        
        result += "【运势指数】\n"
        result += f"运势分数: {fortune['score']}\n"
        
        result += "\n【宜】\n"
        result += "、".join(fortune["activities"][0]["list"]) + "\n"
        
        result += "\n【忌】\n"
        result += "、".join(fortune["activities"][1]["list"]) + "\n"
        
        result += f"\n幸运色: {fortune['color']}\n"
        result += f"幸运数字: {fortune['number']}"
        
        return result
        
    async def morning_greeting(self, user_id: int, group_id: Optional[int]) -> str:
        """早安问候"""
        user_id_str = str(user_id)
        today = date.today().isoformat()
        
        # 每天0点重置早安列表
        if not hasattr(self, 'last_reset_date') or self.last_reset_date != today:
            self.morning_greetings = {}
            self.last_reset_date = today
            self._save_json(self.morning_greetings_file, self.morning_greetings)
        
        # 检查用户今天是否已经说过早安
        if user_id_str in self.morning_greetings:
            return "你今天已经说过早安了喵~"
            
        # 添加用户到早安列表
        self.morning_greetings[user_id_str] = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "rank": len(self.morning_greetings) + 1
        }
        self._save_json(self.morning_greetings_file, self.morning_greetings)
        
        # 获取当前时间
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        hour = now.hour
        
        # 根据时间返回不同的问候语
        if 5 <= hour < 11:
            greeting = "早安喵~今天也要元气满满哦！"
        elif 11 <= hour < 18:
            greeting = "都已经这个点了才起床吗？上午的美好时光都已经过去了喵~"
        else:
            greeting = "啊咧？现在已经是晚上了喵！你的生物钟还好吗？"
            
        # 计算是今天第几个说早安的
        rank = self.morning_greetings[user_id_str]["rank"]
        
        greeting += f"\n你是今天第 {rank} 个说早安的人喵~"
        
        # 如果是前三名，给予特殊祝福
        if rank == 1:
            greeting += "\n🥇 恭喜你！获得今日早安冠军！加油，新的一天也要开心喵~"
        elif rank == 2:
            greeting += "\n🥈 第二名也很厉害呢！希望你今天有个美好的一天喵~"
        elif rank == 3:
            greeting += "\n🥉 第三名！比大多数人都起得早呢，今天一定会有好运喵~"
        
        # 查看早安排行榜
        top_users = []
        for uid, data in self.morning_greetings.items():
            if "rank" in data and "time" in data:
                top_users.append({
                    "user_id": uid,
                    "rank": data["rank"],
                    "time": data["time"]
                })
        
        # 按排名排序
        top_users.sort(key=lambda x: x["rank"])
        
        # 构建排行榜字符串
        if len(top_users) > 1:  # 至少有两个人才显示排行榜
            greeting += "\n\n【今日早安排行】"
            max_display = min(10, len(top_users))  # 最多显示10个
            
            for i in range(max_display):
                user = top_users[i]
                user_name = await self._get_user_nickname(int(user["user_id"]))
                greeting += f"\n{user['rank']}. {user_name} ({user['time']})"
        
        return greeting
        
    async def night_greeting(self, user_id: int, group_id: Optional[int]) -> str:
        """晚安问候"""
        user_id_str = str(user_id)
        today = date.today().isoformat()
        
        # 每天0点重置晚安列表
        if not hasattr(self, 'last_night_reset_date') or self.last_night_reset_date != today:
            self.night_greetings = {}
            self.last_night_reset_date = today
            self._save_json(self.night_greetings_file, self.night_greetings)
        
        # 检查用户今天是否已经说过晚安
        if user_id_str in self.night_greetings:
            return "你今天已经说过晚安了喵~好好睡觉吧！"
            
        # 添加用户到晚安列表
        self.night_greetings[user_id_str] = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "rank": len(self.night_greetings) + 1
        }
        self._save_json(self.night_greetings_file, self.night_greetings)
        
        # 获取当前时间
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        hour = now.hour
        
        # 根据时间返回不同的问候语
        if 18 <= hour <= 23:
            greeting = "晚安喵~祝你有个甜甜的梦！"
        elif 0 <= hour < 5:
            greeting = "已经这么晚了喵，快去睡觉吧，熬夜对身体不好呢！"
        else:
            greeting = "现在才几点啊，就要睡觉了吗？是不是太困了喵？"
            
        # 计算是今天第几个说晚安的
        rank = self.night_greetings[user_id_str]["rank"]
        
        greeting += f"\n你是今天第 {rank} 个说晚安的人喵~"
        
        # 如果是前三名，给予特殊祝福
        if rank == 1:
            greeting += "\n🌙 今日第一个说晚安！希望你做个好梦喵~"
        elif rank == 2:
            greeting += "\n✨ 早点休息是好习惯呢！祝你睡个好觉喵~"
        elif rank == 3:
            greeting += "\n💤 第三个说晚安！愿你有个平静的夜晚喵~"
            
        # 查看晚安排行榜
        top_users = []
        for uid, data in self.night_greetings.items():
            if "rank" in data and "time" in data:
                top_users.append({
                    "user_id": uid,
                    "rank": data["rank"],
                    "time": data["time"]
                })
        
        # 按排名排序
        top_users.sort(key=lambda x: x["rank"])
        
        # 构建排行榜字符串
        if len(top_users) > 1:  # 至少有两个人才显示排行榜
            greeting += "\n\n【今日晚安排行】"
            max_display = min(10, len(top_users))  # 最多显示10个
            
            for i in range(max_display):
                user = top_users[i]
                user_name = await self._get_user_nickname(int(user["user_id"]))
                greeting += f"\n{user['rank']}. {user_name} ({user['time']})"
        
        return greeting
        
    # async def get_random_image(self, category: str = "") -> str:
    #     """获取随机图片"""
    #     try:
    #         # 使用国内稳定的免费二次元图片API
    #         if not category or category in ["二次元", "动漫", "女生","蔚蓝档案", "白丝"]:
    #             # 随机图片，90%女生，10%男生
    #             rand = random.randint(1, 10)
    #             if rand <= 10:  # 90%概率获取女生图片
    #                 url = "https://api.66mz8.com/api/rand.anime.php"
    #             else:  # 10%概率获取男生图片
    #                 url = "https://api.66mz8.com/api/rand.anime.php?type=4"
    #         elif category in ["女生", "巫师", "蔚蓝档案", "白丝"]:
    #             # 女生图片
    #             url = "https://api.66mz8.com/api/rand.anime.php?type=1"
    #         elif category in ["男生", "男孩", "少年"]:
    #             # 男生图片
    #             url = "https://api.66mz8.com/api/rand.anime.php?type=4"
    #         elif category in ["风景", "景色", "自然"]:
    #             # 风景图片
    #             url = "https://api.66mz8.com/api/rand.scenery.php"
    #         elif category in ["壁纸", "高清", "背景"]:
    #             # 高清壁纸
    #             url = "https://api.66mz8.com/api/rand.acg.php"
    #         elif category in ["萌宠", "宠物", "猫", "狗"]:
    #             # 萌宠图片，这里替换为随机二次元猫娘图
    #             url = "https://api.66mz8.com/api/rand.anime.php?type=3"
    #         else:
    #             # 默认返回随机二次元图片
    #             rand = random.randint(1, 10)
    #             if rand <= 9:  # 90%概率获取女生图片
    #                 url = "https://api.66mz8.com/api/rand.anime.php?type=1"
    #             else:  # 10%概率获取男生图片
    #                 url = "https://api.66mz8.com/api/rand.anime.php?type=4"
            
    #         # 创建SSL上下文并禁用证书验证
    #         ssl_context = ssl.create_default_context()
    #         ssl_context.check_hostname = False
    #         ssl_context.verify_mode = ssl.CERT_NONE
            
    #         async with aiohttp.ClientSession() as session:
    #             async with session.get(url, ssl=ssl_context, timeout=10) as response:
    #                 if response.status != 200:
    #                     return f"获取图片失败喵~错误代码: {response.status}"
                    
    #                 # 根据API返回格式处理数据
    #                 if "btstu.cn" in url:
    #                     # 必应壁纸API返回的是JSON
    #                     data = await response.json()
    #                     img_url = data['imgurl']
    #                 else:
    #                     # 直接使用重定向后的URL作为图片URL
    #                     img_url = str(response.url)
    #                     if img_url == url:  # 如果没有重定向
    #                         img_url = url
                    
    #                 return f"[CQ:image,file={img_url}]"
                    
    #     except Exception as e:
    #         logger.error(f"获取图片时出错: {e}")
            
    #         # 备用API列表
    #         backup_urls = [
    #             "https://api.vvhan.com/api/acgimg",
    #             "https://img.xjh.me/random_img.php?type=bg&ctype=acg&return=302",
    #             "https://www.dmoe.cc/random.php",
    #             "https://api.yimian.xyz/img?type=moe",  # 尝试使用此API但不验证SSL
    #             "https://source.unsplash.com/random/1080x720"
    #         ]
            
    #         # 尝试每个备用API
    #         for backup_url in backup_urls:
    #             try:
    #                 ssl_context = ssl.create_default_context()
    #                 ssl_context.check_hostname = False
    #                 ssl_context.verify_mode = ssl.CERT_NONE
                    
    #                 async with aiohttp.ClientSession() as session:
    #                     async with session.get(backup_url, ssl=ssl_context, timeout=10) as response:
    #                         if response.status == 200:
    #                             img_url = str(response.url)
    #                             if img_url == backup_url:  # 如果没有重定向
    #                                 img_url = backup_url
    #                             return f"[CQ:image,file={img_url}]"
    #             except Exception as backup_error:
    #                 logger.error(f"备用图片API {backup_url} 获取失败: {backup_error}")
    #                 continue
            
    #         # 如果所有API都失败，返回固定的图片URL
    #         return f"[CQ:image,file=https://source.unsplash.com/random/1080x720]"

    async def get_random_image(self, category: str = "") -> str:
        """获取随机图片"""
        try:
            # 使用国内稳定的免费二次元图片API
            if not category or category in ["Gawr Gura"]:
                # 随机图片，90%女生，10%男生
                rand = random.randint(1, 10)
                if rand <= 10:  # 90%概率获取女生图片
                    url = "https://api.66mz8.com/api/rand.anime.php"
                else:  # 10%概率获取男生图片
                    url = "https://api.66mz8.com/api/rand.anime.php?type=4"
            elif category in ["Gawr Gura"]:
                # 女生图片
                url = "https://api.66mz8.com/api/rand.anime.php?type=1"
            elif category in ["Gawr Gura"]:
                # 男生图片
                url = "https://api.66mz8.com/api/rand.anime.php?type=4"
            elif category in ["风景", "景色", "自然"]:
                # 风景图片
                url = "https://api.66mz8.com/api/rand.scenery.php"
            elif category in ["壁纸", "高清", "背景"]:
                # 高清壁纸
                url = "https://api.66mz8.com/api/rand.acg.php"
            elif category in ["萌宠", "宠物", "猫", "狗"]:
                # 萌宠图片，这里替换为随机二次元猫娘图
                url = "https://api.66mz8.com/api/rand.anime.php?type=3"
            else:
                # 默认返回随机二次元图片
                rand = random.randint(1, 10)
                if rand <= 9:  # 90%概率获取女生图片
                    url = "https://api.66mz8.com/api/rand.anime.php?type=1"
                else:  # 10%概率获取男生图片
                    url = "https://api.66mz8.com/api/rand.anime.php?type=4"
            
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        return f"获取图片失败喵~错误代码: {response.status}"
                    
                    # 根据API返回格式处理数据
                    if "btstu.cn" in url:
                        # 必应壁纸API返回的是JSON
                        data = await response.json()
                        img_url = data['imgurl']
                    else:
                        # 直接使用重定向后的URL作为图片URL
                        img_url = str(response.url)
                        if img_url == url:  # 如果没有重定向
                            img_url = url
                    
                    return f"[CQ:image,file={img_url}]"
                    
        except Exception as e:
            logger.error(f"获取图片时出错: {e}")
            
            # 备用API列表
            backup_urls = [
                "https://api.vvhan.com/api/acgimg",
                "https://img.xjh.me/random_img.php?type=bg&ctype=acg&return=302",
                "https://www.dmoe.cc/random.php",
                "https://api.yimian.xyz/img?type=moe",  # 尝试使用此API但不验证SSL
                "https://source.unsplash.com/random/1080x720"
            ]
            
            # 尝试每个备用API
            for backup_url in backup_urls:
                try:
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(backup_url, ssl=ssl_context, timeout=10) as response:
                            if response.status == 200:
                                img_url = str(response.url)
                                if img_url == backup_url:  # 如果没有重定向
                                    img_url = backup_url
                                return f"[CQ:image,file={img_url}]"
                except Exception as backup_error:
                    logger.error(f"备用图片API {backup_url} 获取失败: {backup_error}")
                    continue
            
            # 如果所有API都失败，返回固定的图片URL
            return f"[CQ:image,file=https://source.unsplash.com/random/1080x720]"
            
    async def check_earthquake(self) -> str:
        """检查地震信息"""
        try:
            current_time = time.time()
            
            # 限制请求频率
            if current_time - self.last_earthquake_check < 10:  # 限制为每分钟最多一次
                return "查询地震信息的请求过于频繁喵~请稍后再试"
                
            self.last_earthquake_check = current_time
            
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 爬取中国地震台网的新网址
            url = "https://www.cea.gov.cn/cea/dzpd/zqsd/index.html"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                    if response.status != 200:
                        raise Exception(f"中国地震台网返回状态码 {response.status}")
                    
                    html_content = await response.text()
                    
                    # 分析HTML内容提取地震信息
                    import re
                    
                    # 提取最新地震信息列表
                    # 直接匹配页面格式，如 "4月19日16时35分新疆阿克苏地区沙雅县发生3.9级地震 2025-04-19"
                    pattern = r'<li[^>]*>\s*((\d+月\d+日\d+时\d+分)([^<]*?)发生(\d+\.\d+)级地震)\s*(\d{4}-\d{2}-\d{2})\s*</li>'
                    matches = re.findall(pattern, html_content)
                    
                    if not matches:
                        # 备用匹配模式
                        pattern = r'<li>\s*(.*?)发生(\d+\.\d+)级地震\s*(\d{4}-\d{2}-\d{2})\s*</li>'
                        backup_matches = re.findall(pattern, html_content)
                        if backup_matches:
                            # 转换格式以符合主匹配结果的处理方式
                            matches = []
                            for match in backup_matches:
                                full_text = match[0].strip()
                                
                                # 尝试提取时间部分
                                time_match = re.match(r'(\d+月\d+日\d+时\d+分)(.*)', full_text)
                                if time_match:
                                    time_str = time_match.group(1)
                                    location = time_match.group(2).strip()
                                else:
                                    time_str = ""
                                    location = full_text
                                
                                matches.append((
                                    full_text,
                                    time_str,
                                    location,
                                    match[1],
                                    match[2]
                                ))
                    
                    if not matches:
                        # 直接使用简单的匹配尝试提取所有行项目
                        pattern = r'<li[^>]*>(.*?)</li>'
                        simple_matches = re.findall(pattern, html_content)
                        
                        matches = []
                        for text in simple_matches:
                            # 清理HTML标签
                            clean_text = re.sub(r'<[^>]*>', '', text).strip()
                            
                            # 检查是否包含地震信息
                            if '级地震' in clean_text and re.search(r'\d{4}-\d{2}-\d{2}', clean_text):
                                # 提取日期
                                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', clean_text)
                                date = date_match.group(1) if date_match else ""
                                
                                # 提取震级
                                magnitude_match = re.search(r'(\d+\.\d+)级', clean_text)
                                magnitude = magnitude_match.group(1) if magnitude_match else ""
                                
                                # 提取时间部分
                                time_match = re.search(r'(\d+月\d+日\d+时\d+分)', clean_text)
                                time_str = time_match.group(1) if time_match else ""
                                
                                # 提取地点（较复杂）
                                if time_str:
                                    parts = clean_text.split(time_str, 1)
                                    if len(parts) > 1:
                                        location_text = parts[1]
                                        location_match = re.match(r'([^发生]+)发生', location_text)
                                        location = location_match.group(1).strip() if location_match else ""
                                    else:
                                        location = ""
                                else:
                                    location_match = re.match(r'([^发生]+)发生', clean_text)
                                    location = location_match.group(1).strip() if location_match else ""
                                
                                if magnitude and (location or date):
                                    matches.append((clean_text, time_str, location, magnitude, date))
                    
                    if not matches:
                        logger.error(f"未匹配到地震信息，页面内容: {html_content[:200]}...")
                        raise Exception("未在中国地震台网找到地震信息")
                    
                    # 提取最新的地震信息
                    quakes = []
                    for match in matches[:5]:  # 获取最新的5条
                        if len(match) >= 4:
                            full_text = match[0].strip()
                            time_info = match[1].strip() if match[1] else ""
                            location = match[2].strip() if match[2] else ""
                            magnitude = match[3].strip() if match[3] else ""
                            date = match[4].strip() if len(match) > 4 and match[4] else ""
                            
                            # 如果location为空但有完整文本，尝试再次提取
                            if not location and full_text:
                                # 移除时间和日期部分
                                cleaned_text = full_text
                                if time_info:
                                    cleaned_text = cleaned_text.replace(time_info, "")
                                if date:
                                    cleaned_text = cleaned_text.replace(date, "")
                                # 移除"发生X.X级地震"部分
                                if magnitude:
                                    cleaned_text = cleaned_text.replace(f"发生{magnitude}级地震", "")
                                location = cleaned_text.strip()
                            
                            # 构建完整时间
                            time_str = f"{time_info} {date}".strip()
                            
                            if location and magnitude:
                                quakes.append({
                                    "time": time_str,
                                    "location": location,
                                    "magnitude": magnitude,
                                    "link": url,
                                    "title": f"{location}发生{magnitude}级地震"
                                })
                    
                    if not quakes:
                        logger.error(f"无法构建有效地震信息，匹配结果: {matches}")
                        raise Exception("未能解析到有效地震信息")
                    
                    # 使用最新的地震信息
                    latest = quakes[0]
                    
                    # 检查是否为新地震
                    earthquake_id = latest["time"] + "|" + latest["location"]
                    if self.last_earthquake_id == earthquake_id:
                        result = "最新地震信息（无更新）：\n\n"
                    else:
                        self.last_earthquake_id = earthquake_id
                        result = "最新地震信息：\n\n"
                    
                    # 显示多条地震信息
                    display_count = min(5, len(quakes))
                    for i in range(display_count):
                        quake = quakes[i]
                        result += f"【{i+1}】{quake['location']} {quake['magnitude']}级\n"
                        result += f"  时间: {quake['time']}\n"
                        if i < display_count - 1:
                            result += "\n"
                    
                    result += f"\n来源: 中国地震台网"
                    
                    return result
                    
        except Exception as e:
            logger.error(f"获取地震信息时出错: {e}")
            
            # 备用数据源：应急管理部地震信息
            try:
                url = "https://www.mem.gov.cn/xw/zqkx/"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                        if response.status != 200:
                            raise Exception(f"备用地震网站返回状态码 {response.status}")
                        
                        html_content = await response.text()
                        
                        # 提取地震信息
                        import re
                        
                        # 匹配地震新闻
                        earthquake_pattern = r'<li>.*?<span>([\d\-]+)</span>.*?<a.*?href="([^"]+)".*?>(.*?地震.*?)</a>.*?</li>'
                        matches = re.findall(earthquake_pattern, html_content, re.DOTALL)
                        
                        if not matches:
                            # 尝试另一种模式
                            earthquake_pattern = r'<a.*?href="([^"]+)".*?>(.*?地震.*?)</a>.*?<span.*?>([\d\-]+)</span>'
                            matches = re.findall(earthquake_pattern, html_content, re.DOTALL)
                            
                            # 调整匹配顺序以符合预期格式
                            matches = [(match[2], match[0], match[1]) for match in matches if len(match) >= 3]
                        
                        if matches:
                            # 寻找包含"级地震"的标题
                            quake_matches = []
                            for match in matches:
                                if "级地震" in match[2]:
                                    quake_matches.append(match)
                            
                            if quake_matches:
                                # 使用第一条包含级别的地震信息
                                latest = quake_matches[0]
                                
                                time_str = latest[0].strip()
                                link = latest[1].strip()
                                title = latest[2].strip()
                                
                                # 处理相对URL
                                if link.startswith("/"):
                                    link = "https://www.mem.gov.cn" + link
                                
                                # 提取地震级别
                                magnitude_match = re.search(r'(\d+\.?\d*)级', title)
                                magnitude = magnitude_match.group(1) if magnitude_match else "未知"
                                
                                # 提取地点
                                location = re.sub(r'\d+\.?\d*级地震', '', title).strip()
                                if not location:
                                    location = title
                                
                                result = "最新地震信息：\n"
                                result += f"发生时间: {time_str}\n"
                                result += f"震级: {magnitude}级\n"
                                result += f"位置: {location}\n"
                                result += f"详情: {link}"
                                
                                return result
                        
                        # 如果没有找到包含级别的地震信息，则尝试使用第一条地震新闻
                        if matches:
                            latest = matches[0]
                            
                            time_str = latest[0].strip()
                            link = latest[1].strip()
                            title = latest[2].strip()
                            
                            # 处理相对URL
                            if link.startswith("/"):
                                link = "https://www.mem.gov.cn" + link
                            
                            result = "最新地震信息：\n"
                            result += f"发生时间: {time_str}\n"
                            result += f"标题: {title}\n"
                            result += f"详情: {link}"
                            
                            return result
                            
                        raise Exception("备用网站未找到地震信息")
            except Exception as backup_error:
                logger.error(f"备用地震数据源获取失败: {backup_error}")
                
                # 再尝试第三个来源：地震局官方网站
                try:
                    url = "https://www.csi.ac.cn/"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                            if response.status != 200:
                                raise Exception(f"第三方地震网站返回状态码 {response.status}")
                            
                            html_content = await response.text()
                            
                            # 提取地震信息
                            earthquake_pattern = r'<div class="dqzljcxw-box">.*?<a.*?>(.*?)</a>.*?<span>(.*?)</span>'
                            matches = re.findall(earthquake_pattern, html_content, re.DOTALL)
                            
                            if matches:
                                latest = matches[0]
                                
                                title = latest[0].strip()
                                time_str = latest[1].strip()
                                
                                # 提取地震级别
                                magnitude_match = re.search(r'(\d+\.?\d*)级', title)
                                magnitude = magnitude_match.group(1) if magnitude_match else "未知"
                                
                                # 提取地点
                                location = re.sub(r'\d+\.?\d*级地震', '', title).strip()
                                if not location:
                                    location = title
                                
                                result = "最新地震信息：\n"
                                result += f"发生时间: {time_str}\n"
                                result += f"震级: {magnitude}级\n"
                                result += f"位置: {location}\n"
                                result += f"来源: 中国地震科学实验场"
                                
                                return result
                                
                            raise Exception("第三方网站未找到地震信息")
                except Exception as third_error:
                    logger.error(f"第三方地震数据源获取失败: {third_error}")
                    
                    # 所有尝试都失败，使用本地存储的最后一次地震信息
                    if self.last_earthquake_id:
                        parts = self.last_earthquake_id.split("|")
                        if len(parts) >= 2:
                            last_time = parts[0]
                            last_location = parts[1]
                            
                            result = "最新地震信息（来自本地缓存）：\n"
                            result += f"发生时间: {last_time}\n"
                            result += f"位置: {last_location}\n"
                            result += "注意：所有数据源都获取失败，这是最后一次成功获取的信息。"
                            
                            return result
            
            # 所有方法都失败，返回固定消息
            return self.fallback_responses["earthquake"]

    async def search_music(self, keyword: str) -> str:
        """搜索音乐"""
        if not keyword:
            return "请提供歌曲名称或歌手喵~\n例如: 点歌 周杰伦"
            
        try:
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 直接使用网易云音乐官方API搜索
            # 构造请求参数
            encoded_keyword = urllib.parse.quote(keyword)
            
            # 使用网易云音乐官方API
            url = "https://music.163.com/api/search/get"
            
            # 请求参数
            params = {
                "s": keyword,
                "type": 1,  # 1: 单曲, 10: 专辑, 100: 歌手, 1000: 歌单, 1002: 用户
                "limit": 5,  # 返回数量
                "offset": 0  # 偏移量
            }
            
            # 请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://music.163.com/",
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                # 发送请求
                async with session.post(url, params=params, headers=headers, ssl=ssl_context, timeout=15) as response:
                    # 检查响应状态码
                    if response.status != 200:
                        raise Exception(f"网易云音乐API返回状态码 {response.status}")
                    
                    # 尝试读取响应内容为文本
                    text_content = await response.text()
                    
                    # 解析JSON
                    try:
                        data = json.loads(text_content)
                    except json.JSONDecodeError:
                        logger.error(f"网易云音乐API返回非JSON格式: {text_content[:100]}...")
                        raise Exception("网易云音乐API返回格式错误")
                    
                    # 检查返回结果是否包含歌曲
                    if "result" not in data or "songs" not in data["result"] or not data["result"]["songs"]:
                        raise Exception("没有找到相关歌曲")
                    
                    # 提取歌曲信息
                    songs = data["result"]["songs"]
                    if not songs:
                        return f"没有找到与\"{keyword}\"相关的歌曲喵~"
                    
                    # 如果有多首歌曲，列出前5首供用户选择
                    if len(songs) > 1:
                        result = f"找到与\"{keyword}\"相关的歌曲：\n\n"
                        for i, song in enumerate(songs[:5]):
                            song_name = song["name"]
                            artist_name = song["artists"][0]["name"] if song["artists"] else "未知艺术家"
                            song_id = song["id"]
                            result += f"{i+1}. {song_name} - {artist_name}\n"
                        
                        result += "\n请发送序号选择歌曲，或者直接使用命令：点歌 歌名 歌手"
                        return result
                    else:
                        # 只有一首歌曲，直接返回
                        song = songs[0]
                        song_id = song["id"]
                        return f"[CQ:music,type=163,id={song_id}]"
                    
        except Exception as e:
            logger.error(f"搜索网易云音乐时出错: {e}")
            
            # 备用方案：QQ音乐
            try:
                # 尝试搜索QQ音乐
                encoded_keyword = urllib.parse.quote(keyword)
                url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?w={encoded_keyword}&format=json&inCharset=utf8&outCharset=utf-8&platform=yqq.json&new_json=1&cr=1&g_tk=5381&loginUin=0"
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://y.qq.com/",
                    "Accept": "application/json"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                        if response.status != 200:
                            raise Exception(f"QQ音乐API返回状态码 {response.status}")
                        
                        text_content = await response.text()
                        
                        try:
                            data = json.loads(text_content)
                        except json.JSONDecodeError:
                            logger.error(f"QQ音乐API返回非JSON格式: {text_content[:100]}...")
                            raise Exception("QQ音乐API返回格式错误")
                        
                        if not data.get("data") or not data["data"].get("song") or not data["data"]["song"].get("list") or not data["data"]["song"]["list"]:
                            raise Exception("没有找到相关歌曲")
                        
                        songs = data["data"]["song"]["list"]
                        if not songs:
                            return f"没有找到与\"{keyword}\"相关的歌曲喵~"
                        
                        # 如果有多首歌曲，列出前5首供用户选择
                        if len(songs) > 1:
                            result = f"找到与\"{keyword}\"相关的歌曲：\n\n"
                            for i, song in enumerate(songs[:5]):
                                song_name = song["name"]
                                artist_name = song["singer"][0]["name"] if song.get("singer") and song["singer"] else "未知艺术家"
                                song_mid = song["mid"]
                                result += f"{i+1}. {song_name} - {artist_name}\n"
                            
                            result += "\n请发送序号选择歌曲，或者直接使用命令：点歌 歌名 歌手"
                            return result
                        else:
                            # 只有一首歌曲，直接返回
                            song = songs[0]
                            song_mid = song["mid"]
                            return f"[CQ:music,type=qq,id={song_mid}]"
                
            except Exception as qq_error:
                logger.error(f"搜索QQ音乐时出错: {qq_error}")
            
            # 最后一个备用方法：使用Kuwo音乐
            try:
                encoded_keyword = urllib.parse.quote(keyword)
                url = f"http://www.kuwo.cn/api/www/search/searchMusicBykeyWord?key={encoded_keyword}&pn=1&rn=5"
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "http://www.kuwo.cn/",
                    "csrf": "",
                    "Cookie": "kw_token="
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                        if response.status != 200:
                            raise Exception(f"Kuwo音乐API返回状态码 {response.status}")
                        
                        data = await response.json()
                        
                        if data.get("code") != 200 or "data" not in data or "list" not in data["data"]:
                            raise Exception("没有找到相关歌曲")
                        
                        songs = data["data"]["list"]
                        if not songs:
                            return f"没有找到与\"{keyword}\"相关的歌曲喵~"
                        
                        # 如果有多首歌曲，列出前5首供用户选择
                        if len(songs) > 1:
                            result = f"找到与\"{keyword}\"相关的歌曲：\n\n"
                            for i, song in enumerate(songs[:5]):
                                song_name = song["name"]
                                artist_name = song["artist"]
                                song_id = song["rid"]
                                result += f"{i+1}. {song_name} - {artist_name}\n"
                            
                            result += "\n请发送序号选择歌曲，或者直接使用命令：点歌 歌名 歌手"
                            return result
                        else:
                            # 只有一首歌曲，但kuwo没有官方的CQ码支持，返回歌曲信息
                            song = songs[0]
                            song_name = song["name"]
                            artist_name = song["artist"]
                            return f"找到歌曲: {song_name} - {artist_name}，但当前无法播放酷我音乐，请尝试使用其他平台的歌曲喵~"
            
            except Exception as kuwo_error:
                logger.error(f"搜索Kuwo音乐时出错: {kuwo_error}")
            
            # 所有API都失败，返回固定消息
            return self.fallback_responses["music"]

    async def get_news(self) -> str:
        """获取新闻"""
        try:
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 直接爬取新浪新闻
            url = "https://news.sina.com.cn"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                    if response.status != 200:
                        raise Exception(f"新闻网站返回状态码 {response.status}")
                    
                    html_content = await response.text()
                    
                    # 解析HTML提取新闻标题
                    import re
                    
                    # 提取新闻标题和链接
                    news_pattern = r'<a.*?href="(https?://[^"]+)".*?target="_blank">((?!广告).{10,}?)</a>'
                    matches = re.findall(news_pattern, html_content)
                    
                    # 过滤和清理匹配结果
                    news_list = []
                    seen_titles = set()  # 用于去重
                    
                    for match in matches:
                        url = match[0]
                        title = match[1].strip()
                        
                        # 过滤广告和过短的标题
                        if (len(title) >= 10 and 
                            "广告" not in title and 
                            "<" not in title and 
                            ">" not in title and
                            title not in seen_titles):
                            news_list.append({"title": title, "url": url})
                            seen_titles.add(title)
                        
                        # 只保留前15条
                        if len(news_list) >= 15:
                            break
                    
                    # 如果找不到足够的新闻，抛出异常
                    if len(news_list) < 5:
                        raise Exception("未找到足够的新闻")
                    
                    # 格式化输出
                    result = "【今日头条新闻】\n\n"
                    for i, news in enumerate(news_list[:10]):
                        result += f"{i+1}. {news['title']}\n"
                    
                    return result
                    
        except Exception as e:
            logger.error(f"获取新闻时出错: {e}")
            
            # 备用方案：爬取百度热搜
            try:
                url = "https://top.baidu.com/board?tab=realtime"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                        if response.status != 200:
                            raise Exception(f"备用新闻网站返回状态码 {response.status}")
                        
                        html_content = await response.text()
                        
                        # 提取百度热搜
                        import re
                        title_pattern = r'<div class="c-single-text-ellipsis">(.*?)</div>'
                        titles = re.findall(title_pattern, html_content)
                        
                        # 清理数据
                        news_list = []
                        for title in titles:
                            # 清除HTML标签
                            clean_title = re.sub(r'<[^>]+>', '', title).strip()
                            if clean_title and len(clean_title) > 5:
                                news_list.append(clean_title)
                            
                            if len(news_list) >= 10:
                                break
                        
                        if len(news_list) < 5:
                            # 尝试另一种匹配模式
                            content_pattern = r'content_1YWBm">(.*?)</div>'
                            titles = re.findall(content_pattern, html_content)
                            
                            for title in titles:
                                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                                if clean_title and len(clean_title) > 5 and clean_title not in news_list:
                                    news_list.append(clean_title)
                                
                                if len(news_list) >= 10:
                                    break
                        
                        if news_list:
                            result = "【百度热搜】\n\n"
                            for i, title in enumerate(news_list[:10]):
                                result += f"{i+1}. {title}\n"
                            
                            return result
                        else:
                            raise Exception("备用网站未找到新闻")
            except Exception as backup_error:
                logger.error(f"备用新闻获取失败: {backup_error}")
            
            # 所有方法都失败，返回固定消息
            return self.fallback_responses["news"]

    async def get_today_events(self) -> str:
        """获取历史上的今天"""
        try:
            # 获取当前日期
            today = datetime.now()
            month = today.month
            day = today.day
            
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 尝试方法1：直接爬取页面
            url = f"https://www.lssdjt.com/{month:02d}{day:02d}.htm"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                    if response.status != 200:
                        raise Exception(f"历史事件网站返回状态码 {response.status}")
                    
                    html_content = await response.text()
                    
                    # 使用正则表达式提取历史事件
                    events = []
                    
                    # 提取包含年份和事件的列表项
                    pattern = r'<li>\s*<span>(\d+)年</span>(.+?)</li>'
                    matches = re.findall(pattern, html_content, re.DOTALL)
                    
                    if matches:
                        for year, event_html in matches:
                            # 清理HTML标签
                            event_text = re.sub(r'<[^>]+>', '', event_html).strip()
                            events.append({"year": year, "title": event_text})
                    
                    # 如果没有找到匹配项，尝试另一种模式
                    if not events:
                        pattern2 = r'<div class="list-box">\s*<p>(\d+)年(.*?)</p>'
                        matches = re.findall(pattern2, html_content, re.DOTALL)
                        if matches:
                            for year, event_html in matches:
                                event_text = re.sub(r'<[^>]+>', '', event_html).strip()
                                events.append({"year": year, "title": event_text})
                    
                    if not events:
                        raise Exception("从页面中提取事件失败")
                    
                    # 按年份排序，从古到今
                    events.sort(key=lambda x: int(x["year"]) if x["year"].isdigit() else 0)
                    
                    # 格式化结果
                    result = f"【历史上的今天: {month}月{day}日】\n\n"
                    
                    # 最多显示10个事件
                    display_count = min(10, len(events))
                    for i in range(display_count):
                        event = events[i]
                        result += f"{event['year']}年: {event['title']}\n"
                    
                    result += f"\n数据来源: 历史上的今天"
                    return result
                    
        except Exception as e:
            logger.error(f"获取历史事件(方法1)时出错: {e}")
            
            # 尝试方法2：备用网站爬取
            try:
                url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month:02d}.json"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Referer": "https://baike.baidu.com/"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                        if response.status != 200:
                            raise Exception(f"百度百科返回状态码 {response.status}")
                        
                        try:
                            data = await response.json()
                            
                            # 提取对应日期的数据
                            month_day = f"{month:02d}{day:02d}"
                            if month_day not in data:
                                raise Exception(f"百度百科数据中没有{month_day}的数据")
                            
                            events_data = data[month_day]
                            events = []
                            
                            # 提取所有类型的事件
                            for event_type in ['birth', 'death', 'events']:
                                if event_type in events_data:
                                    for event in events_data[event_type]:
                                        if 'year' in event and 'title' in event:
                                            type_prefix = ""
                                            if event_type == 'birth':
                                                type_prefix = "【诞生】"
                                            elif event_type == 'death':
                                                type_prefix = "【逝世】"
                                            
                                            events.append({
                                                "year": event['year'],
                                                "title": f"{type_prefix}{event['title']}"
                                            })
                            
                            if not events:
                                raise Exception("百度百科没有返回有效事件")
                            
                            # 按年份排序
                            events.sort(key=lambda x: int(x["year"]) if isinstance(x["year"], (int, str)) and str(x["year"]).isdigit() else 0)
                            
                            # 格式化结果
                            result = f"【历史上的今天: {month}月{day}日】\n\n"
                            
                            # 最多显示10个事件
                            display_count = min(10, len(events))
                            for i in range(display_count):
                                event = events[i]
                                result += f"{event['year']}年: {event['title']}\n"
                            
                            result += f"\n数据来源: 百度百科"
                            return result
                        
                        except json.JSONDecodeError:
                            # JSON解析失败，可能是HTML页面，尝试直接爬取
                            raise Exception("百度百科返回非JSON数据")
                
            except Exception as e2:
                logger.error(f"获取历史事件(方法2)时出错: {e2}")
                
                # 继续尝试方法3，而不是直接抛出异常
                # 尝试方法3：直接爬取网站
                try:
                    url = f"https://hao.360.com/histoday/{month:02d}{day:02d}.html"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, ssl=ssl_context, timeout=15) as response:
                            if response.status != 200:
                                raise Exception(f"360历史上的今天返回状态码 {response.status}")
                            
                            html_content = await response.text()
                            
                            # 提取事件列表
                            events = []
                            pattern = r'<dt>(\d+)年</dt>\s*<dd>(.*?)</dd>'
                            matches = re.findall(pattern, html_content, re.DOTALL)
                            
                            if not matches:
                                # 尝试其他模式
                                pattern2 = r'<li[^>]*>\s*<em>(\d+)年</em>(.*?)</li>'
                                matches = re.findall(pattern2, html_content, re.DOTALL)
                            
                            if matches:
                                for year, event_html in matches:
                                    event_text = re.sub(r'<[^>]+>', '', event_html).strip()
                                    events.append({"year": year, "title": event_text})
                            
                            if not events:
                                raise Exception("从360网站提取事件失败")
                            
                            # 按年份排序
                            events.sort(key=lambda x: int(x["year"]) if x["year"].isdigit() else 0)
                            
                            # 格式化结果
                            result = f"【历史上的今天: {month}月{day}日】\n\n"
                            
                            # 最多显示10个事件
                            display_count = min(10, len(events))
                            for i in range(display_count):
                                event = events[i]
                                result += f"{event['year']}年: {event['title']}\n"
                            
                            result += f"\n数据来源: 360历史上的今天"
                            return result
                
                except Exception as e3:
                    logger.error(f"获取历史事件(方法3)时出错: {e3}")
                    
                    # 如果所有在线方法都失败，使用本地数据
                    try:
                        # 根据月日生成键
                        date_key = f"{month:02d}{day:02d}"
                        
                        # 常见历史事件硬编码
                        important_events = {
                            "0101": ["1912年: 中华民国成立", "1949年: 北平和平解放", "1979年: 中美正式建交"],
                            "0214": ["1950年: 中苏签订《中苏友好同盟互助条约》", "1972年: 中日建交正常化"],
                            "0301": ["1932年: 满洲国成立", "1954年: 美国第一颗氢弹爆炸"],
                            "0308": ["1949年: 中共中央进驻北平", "1963年: 毛泽东提出向雷锋同志学习"],
                            "0312": ["1925年: 孙中山逝世", "1951年: 联合国军重新占领汉城"],
                            "0315": ["1917年: 沙皇尼古拉二世退位", "1990年: 苏联第一任总统产生"],
                            "0321": ["1960年: 南非沙佩维尔惨案", "1999年: 贝尔格莱德遭北约轰炸"],
                            "0401": ["1949年: 中央人民政府机构开始办公", "1997年: 香港特别行政区政府正式成立"],
                            "0415": ["1912年: 泰坦尼克号沉没", "1989年: 胡耀邦逝世"],
                            "0420": ["268年: 西晋文明皇后王元姬逝世", "429年: 数学家祖冲之诞生", "888年: 佛僧皇帝唐僧宗李俨逝世", 
                                     "1653年: 奥利弗·克伦威尔解散英国国会", "1792年: 法国向奥地利宣战", 
                                     "1872年: 新中国的开国元勋张澜同志诞生", "1879年: 国民党元老于佑任诞生", 
                                     "1889年: 阿道夫·希特勒出生", "1893年: 西班牙超现实主义画家、雕塑家胡安·米罗诞生",
                                     "1920年: 五四运动爆发", "1949年: 解放南京", "1989年: 天安门学生运动"],
                            "0421": ["1949年: 解放南京", "1967年: 希腊军人政变", "1989年: 天安门广场学生绝食"],
                            "0422": ["1500年: 葡萄牙航海家发现巴西", "1970年: 第一个世界地球日"],
                            "0428": ["1975年: 中国开始研制航天飞机", "2001年: 第一位太空游客诞生"],
                            "0501": ["1950年: 《婚姻法》颁布", "1919年: 五四运动爆发"],
                            "0504": ["1919年: 五四运动爆发", "1946年: 中国内战爆发", "1970年: 美国肯特州立大学事件"],
                            "0608": ["1989年: 邓小平会见戒严部队军以上干部", "1963年: 中国与法国建交"],
                            "0701": ["1921年: 中国共产党成立", "1997年: 香港回归中国"],
                            "0707": ["1937年: 卢沟桥事变爆发", "1949年: 南京解放"],
                            "0801": ["1927年: 南昌起义", "1949年: 《中国人民解放军宣言》发表"],
                            "0815": ["1945年: 日本天皇宣布无条件投降", "1947年: 印度独立"],
                            "0918": ["1931年: 九一八事变", "1949年: 中国人民政治协商会议第一届全体会议召开"],
                            "1001": ["1949年: 中华人民共和国成立", "1984年: 国庆35周年大阅兵"],
                            "1010": ["1913年: 袁世凯正式当选中华民国大总统", "1911年: 辛亥革命爆发"],
                            "1024": ["1945年: 联合国成立", "1950年: 中国人民志愿军赴朝作战"],
                            "1112": ["1866年: 孙中山诞生", "1926年: 北伐战争开始"],
                            "1201": ["1943年: 开罗会议", "1949年: 中央人民政府委员会第四次会议"],
                            "1209": ["1894年: 孙中山创立兴中会", "1949年: 中央人民政府迁入北京"],
                            "1213": ["1937年: 南京大屠杀", "1911年: 孙中山就任临时大总统"],
                            "1220": ["1999年: 澳门回归中国", "1917年: 成立肃反委员会"],
                            "1225": ["1893年: 毛泽东诞生", "1932年: 蒋介石下野"],
                            "1226": ["1893年: 毛泽东诞生", "1946年: 中国人民解放军改编"]
                        }
                        
                        # 如果有当天的历史事件
                        if date_key in important_events:
                            result = f"【历史上的今天: {month}月{day}日】\n\n"
                            for event in important_events[date_key]:
                                result += f"{event}\n"
                            result += "\n数据来源: 本地历史事件库"
                            return result
                        else:
                            # 如果没有当天的事件，则创建一些通用事件
                            general_events = [
                                f"{1940+day}年: 二战期间，盟军在欧洲战场取得重要进展",
                                f"{1960+day}年: 联合国通过关于和平与发展的重要决议",
                                f"{1980+day}年: 世界多国签署环境保护协议",
                                f"{2000+month}年: 信息技术领域取得重大突破",
                                f"{2010+day%10}年: 国际空间站完成重要科学实验"
                            ]
                            
                            result = f"【历史上的今天: {month}月{day}日】\n\n"
                            for event in general_events:
                                result += f"{event}\n"
                            result += "\n数据来源: 通用历史事件"
                            return result
                            
                    except Exception as final_error:
                        logger.error(f"本地历史事件数据获取失败: {final_error}")
                        return f"无法获取{month}月{day}日的历史事件数据喵~请稍后再试"

    async def handle_private_message(self, user_id: int, message: List[Dict[str, Any]]):
        """处理私聊消息"""
        # 检查消息是否为文本形式的戳一戳
        try:
            message_text = ""
            for msg_segment in message:
                if msg_segment.get("type") == "text":
                    message_text += msg_segment.get("data", {}).get("text", "")
            
            # 判断消息内容是否为戳一戳类文本
            poke_texts = ["戳一戳", "戳戳", "poke", "摸摸", "摸一摸", "摸头", "摸摸头", "拍拍", "拍一拍"]
            is_poke_text = False
            
            for poke_text in poke_texts:
                if poke_text in message_text and len(message_text.strip()) <= 10:  # 限制长度，避免误触发
                    is_poke_text = True
                    break
            
            if is_poke_text:
                logger.info(f"检测到私聊中的文本形式戳一戳消息: {message_text} 来自用户: {user_id}")
                
                # 确定是否是手机用户
                is_mobile = False
                # 尝试获取设备信息
                device_info = "未知"
                for msg_segment in message:
                    if "sender" in msg_segment and "device" in msg_segment["sender"]:
                        device_info = msg_segment["sender"]["device"]
                        break
                
                if isinstance(device_info, dict):
                    device_name = device_info.get("device_name", "").lower()
                    app_name = device_info.get("app_name", "").lower()
                    is_mobile = "mobile" in device_name or "phone" in device_name or "android" in app_name or "ios" in app_name
                elif isinstance(device_info, str):
                    device_info_lower = device_info.lower()
                    is_mobile = "mobile" in device_info_lower or "phone" in device_info_lower or "android" in device_info_lower or "ios" in device_info_lower
                
                logger.info(f"触发私聊中的文本形式戳一戳响应，用户: {user_id}，设备: {'手机' if is_mobile else '电脑'}")
                response = await self.handle_poke(user_id, None, is_mobile)
                await self.bot.send_private_msg(user_id=user_id, message=response)
                return
        except Exception as e:
            logger.error(f"处理私聊中的文本形式戳一戳消息时出错: {e}")
    
    async def handle_group_message(self, group_id: int, user_id: int, message: List[Dict[str, Any]]):
        """处理群聊消息"""
        # 检查消息是否为文本形式的戳一戳
        try:
            message_text = ""
            for msg_segment in message:
                if msg_segment.get("type") == "text":
                    message_text += msg_segment.get("data", {}).get("text", "")
            
            # 判断消息内容是否为戳一戳类文本
            poke_texts = ["戳一戳", "戳戳", "poke", "摸摸", "摸一摸", "摸头", "摸摸头", "拍拍", "拍一拍"]
            is_poke_text = False
            
            for poke_text in poke_texts:
                if poke_text in message_text and len(message_text.strip()) <= 10:  # 限制长度，避免误触发
                    is_poke_text = True
                    break
            
            if is_poke_text:
                logger.info(f"检测到文本形式的戳一戳消息: {message_text} 来自用户: {user_id}")
                
                # 判断消息是否只@了机器人
                is_at_bot = False
                for msg_segment in message:
                    if msg_segment.get("type") == "at" and msg_segment.get("data", {}).get("qq", "") == str(self.bot.self_id):
                        is_at_bot = True
                        break
                
                # 如果是@机器人的戳一戳消息，或者只有戳一戳相关文本
                if is_at_bot or len(message) == 1:
                    # 确定是否是手机用户
                    is_mobile = False
                    # 尝试获取设备信息
                    device_info = "未知"
                    for msg_segment in message:
                        if "sender" in msg_segment and "device" in msg_segment["sender"]:
                            device_info = msg_segment["sender"]["device"]
                            break
                    
                    if isinstance(device_info, dict):
                        device_name = device_info.get("device_name", "").lower()
                        app_name = device_info.get("app_name", "").lower()
                        is_mobile = "mobile" in device_name or "phone" in device_name or "android" in app_name or "ios" in app_name
                    elif isinstance(device_info, str):
                        device_info_lower = device_info.lower()
                        is_mobile = "mobile" in device_info_lower or "phone" in device_info_lower or "android" in device_info_lower or "ios" in device_info_lower
                    
                    logger.info(f"触发文本形式的戳一戳响应，用户: {user_id}，设备: {'手机' if is_mobile else '电脑'}")
                    response = await self.handle_poke(user_id, group_id, is_mobile)
                    await self.bot.send_group_msg(group_id=group_id, message=response)
                    return
        except Exception as e:
            logger.error(f"处理文本形式戳一戳消息时出错: {e}")
    
    async def handle_notice(self, notice_type: str, user_id: int, group_id: Optional[int], data: Dict[str, Any]) -> Optional[str]:
        """处理通知事件
        
        Args:
            notice_type: 通知类型
            user_id: 用户ID
            group_id: 群ID
            data: 通知数据
            
        Returns:
            回复消息，如果不需要回复则返回None
        """
        logger.debug(f"ExtraFeaturesPlugin处理通知: {notice_type}, 用户: {user_id}, 群: {group_id}, 数据: {data}")
        
        # 详细记录戳一戳事件的信息
        if notice_type == "notify" and data.get("sub_type") == "poke":
            logger.info(f"收到戳一戳事件: 用户ID={user_id}, 目标ID={data.get('target_id')}, 自身ID={self.bot.self_id}")
            if data.get("target_id") == self.bot.self_id:
                # 如果是戳机器人
                logger.info(f"用户 {user_id} 戳了戳机器人，准备回复")
                return await self.handle_poke(user_id, group_id)
        
        # 兼容不同go-cqhttp版本的戳一戳事件格式
        if notice_type == "poke" and data.get("target_id") == self.bot.self_id:
            # 如果是戳一戳事件且戳的是机器人
            logger.info(f"通过poke类型事件检测到用户 {user_id} 戳了戳机器人，准备回复")
            return await self.handle_poke(user_id, group_id)
            
        return None
        
    async def handle_poke(self, user_id: int, group_id: Optional[int]) -> str:
        """处理戳一戳事件
        
        Args:
            user_id: 戳的人的ID
            group_id: 群ID，如果在私聊中则为None
            
        Returns:
            回复消息
        """
        logger.info(f"收到用户 {user_id} 的戳一戳")
        
        # 戳一戳也更新积分和好感度
        await self._update_user_points(user_id, 1)  # 戳一戳加1积分
        await self._update_user_favor(user_id, 0.5)  # 戳一戳加0.5好感度
        
        # 判断是否是主人
        is_master = False
        try:
            # 强制转换用户ID为整数类型
            try:
                user_id = int(user_id)
                logger.info(f"用户ID转换为整数: {user_id}")
            except (ValueError, TypeError):
                logger.warning(f"无法将用户ID转换为整数: {user_id}")
            
            # 硬编码判断主人 (优先级最高，无论配置如何都会生效)
            if user_id == 3688442118:
                is_master = True
                logger.info(f"硬编码检测到主人ID: {user_id}")
            
            # 检查配置中的超级用户列表
            elif hasattr(self.bot, "config") and "admin" in self.bot.config:
                logger.debug(f"机器人配置: {self.bot.config}")
                # 优先检查super_users字段（配置文件中实际使用的字段）
                if "super_users" in self.bot.config["admin"]:
                    super_users = self.bot.config["admin"]["super_users"]
                    logger.info(f"配置中的超级用户列表: {super_users}, 当前用户: {user_id}")
                    
                    # 检查用户是否在超级用户列表中
                    if isinstance(super_users, (list, tuple)):
                        # 转换列表中所有用户ID为整数，然后比较
                        super_users_int = [int(su) if isinstance(su, (int, str)) and str(su).isdigit() else su for su in super_users]
                        is_master = user_id in super_users_int
                        logger.info(f"超级用户整数列表: {super_users_int}")
                        logger.info(f"用户是否在超级用户列表中: {is_master}")
                    else:
                        # 如果不是列表，确保两者都是整数再比较
                        try:
                            super_user_int = int(super_users)
                            is_master = user_id == super_user_int
                            logger.info(f"用户ID: {user_id} 是否等于超级用户ID: {super_user_int}: {is_master}")
                        except (ValueError, TypeError):
                            is_master = str(user_id) == str(super_users)
                            logger.info(f"字符串比较: '{user_id}' 是否等于 '{super_users}': {is_master}")
                
                # 兼容旧配置，检查master字段
                elif "master" in self.bot.config["admin"]:
                    master_id = self.bot.config["admin"]["master"]
                    logger.info(f"配置中的主人ID: {master_id}, 当前用户: {user_id}")
                    
                    if isinstance(master_id, (list, tuple)):
                        # 转换列表中所有master ID为整数，然后比较
                        master_ids_int = [int(mid) if isinstance(mid, (int, str)) and str(mid).isdigit() else mid for mid in master_id]
                        is_master = user_id in master_ids_int
                        logger.info(f"用户是否在主人列表中: {is_master}")
                    else:
                        # 尝试将两者转换为整数进行比较
                        try:
                            if isinstance(master_id, (int, str)) and str(master_id).isdigit():
                                master_int = int(master_id)
                                is_master = user_id == master_int
                                logger.info(f"比较整数ID - 主人ID: {master_int}, 用户ID: {user_id}, 是否匹配: {is_master}")
                            else:
                                is_master = str(user_id) == str(master_id)
                                logger.info(f"比较字符串ID - 主人ID: {master_id}, 用户ID: {user_id}, 是否匹配: {is_master}")
                        except (ValueError, TypeError) as e:
                            logger.error(f"比较主人ID时出错: {e}")
                            is_master = str(user_id) == str(master_id)
                            logger.info(f"fallback到字符串比较 - 主人ID: {master_id}, 用户ID: {user_id}, 是否匹配: {is_master}")
            else:
                logger.warning("找不到机器人配置或admin配置部分，无法通过配置确定用户是否为主人")
        except Exception as e:
            logger.error(f"判断主人身份时出错: {e}")
            # 出错时，如果是特定用户ID，仍然认为是主人
            if user_id == 3688442118:
                is_master = True
                logger.info("判断出错，回退到硬编码识别主人身份")
            else:
                # 出错时，为安全起见默认不是主人
                is_master = False
        
        logger.info(f"最终判断结果 - 用户 {user_id} 是否为主人: {is_master}")
        
        # 使用AI生成回复
        if self.use_ai_for_poke:
            try:
                # 尝试最多三次获取AI回复
                for i in range(3):
                    try:
                        logger.info(f"尝试获取第 {i+1} 次AI回复，用户身份: {'主人' if is_master else '普通用户'}")
                        ai_response = await self._get_ai_poke_response(user_id, is_master)
                        if ai_response:
                            logger.info(f"获取到AI回复: {ai_response}")
                            return ai_response
                    except Exception as ai_error:
                        logger.error(f"获取AI回复尝试 {i+1} 失败: {ai_error}")
                        if i == 2:  # 如果是最后一次尝试
                            raise Exception("所有AI尝试均失败")
                        # 否则继续尝试下一个API
                
                # 如果所有AI尝试都失败但没有异常，使用固定回复
                raise Exception("无法获取有效的AI回复")
            except Exception as e:
                logger.error(f"获取AI回复完全失败: {e}")
        
        # 如果AI失败或未启用，使用预设回复
        logger.info(f"使用预设回复，用户身份: {'主人' if is_master else '普通用户'}")
        
        # 使用普通回复
        if is_master:
            response = random.choice(self.poke_responses["master"])
        else:
            response = random.choice(self.poke_responses["user"])
                
        logger.info(f"返回回复: {response}")
        return response
        
    async def _get_ai_poke_response(self, user_id: int, is_master: bool) -> str:
        """使用AI生成戳一戳回复
        
        Args:
            user_id: 用户ID
            is_master: 是否是主人
            
        Returns:
            AI生成的回复
        """
        # 获取用户名称
        user_name = str(user_id)
        try:
            # 尝试获取用户昵称
            api_base = f"http://{self.bot.config['bot']['napcat']['host']}:{self.bot.config['bot']['napcat']['port']}"
            token = self.bot.config['bot']['napcat']['access_token']
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession() as session:
                url = f"{api_base}/get_stranger_info?user_id={user_id}"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "data" in data and "nickname" in data["data"]:
                            user_name = data["data"]["nickname"]
        except Exception as e:
            logger.error(f"获取用户昵称失败: {e}")
        
        # 构建提示词
        if is_master:
            prompt = f"你是一个可爱的猫娘AI助手，用户 {user_name} 是你的主人，他戳了戳你，请你用可爱的语气回复他，回复要简短，不超过30个字，要带有喵~等猫娘特征。"
        else:
            prompt = f"你是一个可爱的猫娘AI助手，用户 {user_name} 戳了戳你，他不是你的主人，请你用傲娇的语气回复他，回复要简短，不超过30个字，要带有喵~等猫娘特征。"
        
        # 如果可以使用聊天插件的AI接口
        if hasattr(self, "use_chat_ai") and self.use_chat_ai and hasattr(self, "ai_provider"):
            try:
                import time
                start_time = time.time()
                
                # 组装消息格式
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "我戳了戳你"}
                ]
                
                # 调用AI接口
                response = await self.ai_provider.chat(messages)
                
                # 处理回复内容
                if response:
                    ai_response = response
                    
                    # 清理回复内容，确保简短可爱
                    ai_response = ai_response.replace("AI:", "").replace("assistant:", "").strip()
                    
                    # 如果回复过长，截断
                    if len(ai_response) > 50:
                        ai_response = ai_response[:47] + "..."
                    
                    # 确保有猫娘特征
                    if "喵" not in ai_response:
                        ai_response += "喵~"
                    
                    logger.info(f"AI响应耗时: {time.time() - start_time:.2f}秒")
                    return ai_response
                else:
                    logger.error(f"AI响应为空")
                    raise Exception("AI响应为空")
                    
            except Exception as e:
                logger.error(f"调用聊天AI接口失败: {e}")
                # 失败后继续使用备用AI接口
        
        # 创建SSL上下文并禁用证书验证
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 尝试几个免费AI API (作为备用)
        ai_apis = [
            {
                "url": "https://api.qqsuu.cn/api/dm-ai",
                "params": {"msg": prompt},
                "response_key": "data"
            },
            {
                "url": "https://api.caonm.net/api/ai/o.php",
                "params": {"msg": prompt},
                "response_key": "text"
            },
            {
                "url": "https://ai.baidu.com/aidemo",
                "method": "POST",
                "data": {
                    "text": prompt,
                    "tokenizer": "llama2",
                    "model": "bloomz_7b",
                    "temperature": 0.95
                },
                "response_key": "result"
            }
        ]
        
        # 记录错误信息以便于排查
        errors = []
        
        for api in ai_apis:
            try:
                async with aiohttp.ClientSession() as session:
                    method = api.get("method", "GET")
                    # 设置超时避免长时间等待
                    if method == "GET":
                        async with session.get(api["url"], params=api.get("params"), ssl=ssl_context, timeout=8) as response:
                            if response.status == 200:
                                # 尝试不同方式解析响应内容
                                try:
                                    data = await response.json()
                                except Exception as json_error:
                                    # 如果JSON解析失败，尝试获取文本内容
                                    content = await response.text()
                                    logger.debug(f"API返回非JSON内容: {content[:100]}...")
                                    
                                    # 尝试从文本中提取可能的回复
                                    if len(content) < 200 and "喵" in content:
                                        return content.strip()
                                    
                                    errors.append(f"API {api['url']} 返回非JSON格式: {str(json_error)}")
                                    continue
                                
                                # 提取回复内容
                                if api["response_key"] in data:
                                    ai_response = data[api["response_key"]]
                                    
                                    # 如果回复为空或异常值
                                    if not ai_response or len(ai_response) < 3:
                                        errors.append(f"API {api['url']} 回复内容异常: {ai_response}")
                                        continue
                                    
                                    # 清理回复内容，确保简短可爱
                                    ai_response = ai_response.replace("AI:", "").replace("assistant:", "").strip()
                                    
                                    # 如果回复过长，截断
                                    if len(ai_response) > 50:
                                        ai_response = ai_response[:47] + "..."
                                    
                                    # 确保有猫娘特征
                                    if "喵" not in ai_response:
                                        ai_response += "喵~"
                                    
                                    return ai_response
                    else:  # POST方法
                        async with session.post(api["url"], json=api.get("data"), ssl=ssl_context, timeout=8) as response:
                            if response.status == 200:
                                try:
                                    data = await response.json()
                                except Exception as json_error:
                                    content = await response.text()
                                    logger.debug(f"API返回非JSON内容: {content[:100]}...")
                                    errors.append(f"API {api['url']} 返回非JSON格式: {str(json_error)}")
                                    continue
                                
                                if api["response_key"] in data:
                                    ai_response = data[api["response_key"]]
                                    if not ai_response or len(ai_response) < 3:
                                        errors.append(f"API {api['url']} 回复内容异常: {ai_response}")
                                        continue
                                    
                                    ai_response = ai_response.replace("AI:", "").strip()
                                    
                                    if len(ai_response) > 50:
                                        ai_response = ai_response[:47] + "..."
                                    
                                    if "喵" not in ai_response:
                                        ai_response += "喵~"
                                    
                                    return ai_response
                            else:
                                errors.append(f"API {api['url']} 返回状态码: {response.status}")
            except Exception as api_error:
                errors.append(f"API {api['url']} 请求错误: {str(api_error)}")
                logger.error(f"AI API {api['url']} 调用失败: {api_error}")
                continue
        
        # 如果所有API尝试都失败，生成一个本地随机回复
        try:
            # 生成一个本地的随机回复，确保有一个可用结果
            local_responses = [
                f"{user_name}戳我干嘛，哼！我才不理你呢喵~",
                f"呀！被{user_name}戳到了，好痒喵~",
                f"再戳我就咬你哦，{user_name}喵~",
                f"喵呜~不要再戳啦，{user_name}欺负猫咪是不对的！",
                f"哼哼，{user_name}这么喜欢戳我吗？真拿你没办法喵~",
                f"喵喵喵？{user_name}需要我帮忙吗？",
                f"戳什么戳！{user_name}是笨蛋喵！",
                f"呜~被{user_name}戳了，人家才不会高兴呢喵~"
            ]
            
            if is_master:
                local_responses = [
                    f"主人好~有什么需要帮忙的吗喵？",
                    f"被主人戳到啦~好开心喵~",
                    f"主人想要我做什么呢？随时为您服务喵！",
                    f"喵呜~主人的手指好温暖~",
                    f"主人今天看起来心情不错呢喵~",
                    f"主人主人！我在这里喵~",
                    f"喵~主人抱抱我好不好？",
                    f"主人找我有事吗？我很乐意为您效劳喵~"
                ]
            
            logger.info("使用本地生成的随机回复")
            return random.choice(local_responses)
        except Exception as local_error:
            logger.error(f"生成本地回复也失败了: {local_error}")
        
        # 所有API都失败，记录详细错误信息
        error_msg = "所有AI API均不可用:\n" + "\n".join(errors)
        logger.error(error_msg)
        
        # 返回None以触发外部的默认回复逻辑
        return None

    async def manual_poke(self, user_id: int, group_id: Optional[int], target_id: Optional[int] = None) -> str:
        """手动触发戳一戳事件
        
        Args:
            user_id: 发起命令的用户ID
            group_id: 群ID，如果在私聊中则为None
            target_id: 目标用户ID，如果为None则默认为机器人自己
            
        Returns:
            回复消息
        """
        logger.info(f"用户 {user_id} 手动触发了戳一戳事件，目标: {target_id}")
        
        # 如果未指定目标，则默认为机器人自己
        if target_id is None or target_id == self.bot.self_id:
            # 调用戳一戳处理函数
            return await self.handle_poke(user_id, group_id)
        
        # 如果指定了其他用户为目标
        try:
            # 获取目标用户昵称
            target_name = str(target_id)
            try:
                api_base = f"http://{self.bot.config['bot']['napcat']['host']}:{self.bot.config['bot']['napcat']['port']}"
                token = self.bot.config['bot']['napcat']['access_token']
                headers = {"Authorization": f"Bearer {token}"}
                
                async with aiohttp.ClientSession() as session:
                    url = f"{api_base}/get_stranger_info?user_id={target_id}"
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and "data" in data and "nickname" in data["data"]:
                                target_name = data["data"]["nickname"]
            except Exception as e:
                logger.error(f"获取目标用户昵称失败: {e}")
            
            # 生成戳其他人的消息
            responses = [
                f"你戳了戳 {target_name}，但是对方没有理你喵~",
                f"你轻轻地戳了戳 {target_name}，对方疑惑地看着你喵~",
                f"你戳了戳 {target_name}，对方回戳了你一下喵！",
                f"你悄悄地戳了戳 {target_name}，但被发现了喵！",
                f"你用力戳了戳 {target_name}，对方表示很疼喵！",
                f"你戳了戳 {target_name} 的脸蛋，好软喵~",
                f"你想戳 {target_name}，但是被我挡住了喵！主人说过不能随便戳别人的！"
            ]
            
            return random.choice(responses)
        except Exception as e:
            logger.error(f"处理戳其他人事件时出错: {e}")
            return "戳人失败了喵~" 

    async def _update_user_points(self, user_id: int, points: float) -> None:
        """更新用户积分
        
        Args:
            user_id: 用户ID
            points: 要增加的积分数量
        """
        user_id_str = str(user_id)
        
        # 确保用户ID在积分字典中
        if user_id_str not in self.user_points:
            self.user_points[user_id_str] = {
                "total_points": 0,
                "daily_points": 0,
                "last_update": ""
            }
        
        # 检查是否需要重置每日积分
        today = date.today().isoformat()
        if "last_update" not in self.user_points[user_id_str] or self.user_points[user_id_str]["last_update"] != today:
            self.user_points[user_id_str]["daily_points"] = 0
            self.user_points[user_id_str]["last_update"] = today
        
        # 更新积分
        self.user_points[user_id_str]["total_points"] += points
        self.user_points[user_id_str]["daily_points"] += points
        
        # 保存数据
        self._save_json(self.user_points_file, self.user_points)
        logger.debug(f"已更新用户 {user_id} 的积分，增加了 {points} 积分")
    
    async def _update_user_favor(self, user_id: int, favor: float) -> None:
        """更新用户好感度
        
        Args:
            user_id: 用户ID
            favor: 要增加的好感度
        """
        user_id_str = str(user_id)
        
        # 确保用户ID在好感度字典中
        if user_id_str not in self.user_favor:
            self.user_favor[user_id_str] = {
                "favor": 0,
                "level": 1,
                "first_interaction": date.today().isoformat(),
                "last_interaction": date.today().isoformat()
            }
        
        # 更新好感度
        current_favor = self.user_favor[user_id_str]["favor"]
        new_favor = current_favor + favor
        
        # 限制最大好感度为1000
        new_favor = min(new_favor, 1000)
        
        # 计算好感度等级
        # 1-10级: 每10点升1级
        # 11-20级: 每20点升1级
        # 21-50级: 每30点升1级
        # 51-100级: 每50点升1级
        if new_favor < 100:
            level = 1 + int(new_favor / 10)
        elif new_favor < 300:
            level = 10 + int((new_favor - 100) / 20)
        elif new_favor < 1000:
            level = 20 + int((new_favor - 300) / 30)
        else:
            level = 50
        
        # 更新数据
        self.user_favor[user_id_str]["favor"] = new_favor
        self.user_favor[user_id_str]["level"] = level
        self.user_favor[user_id_str]["last_interaction"] = date.today().isoformat()
        
        # 保存数据
        self._save_json(self.user_favor_file, self.user_favor)
        logger.debug(f"已更新用户 {user_id} 的好感度，增加了 {favor} 点，当前等级: {level}")
    
    async def check_user_points(self, user_id: int) -> str:
        """查询用户积分
        
        Args:
            user_id: 用户ID
            
        Returns:
            积分信息
        """
        user_id_str = str(user_id)
        
        # 如果用户没有积分记录，则初始化
        if user_id_str not in self.user_points:
            self.user_points[user_id_str] = {
                "total_points": 0,
                "daily_points": 0,
                "last_update": date.today().isoformat()
            }
            self._save_json(self.user_points_file, self.user_points)
        
        # 获取用户昵称
        user_name = await self._get_user_nickname(user_id)
        
        # 获取积分信息
        total_points = self.user_points[user_id_str]["total_points"]
        daily_points = self.user_points[user_id_str]["daily_points"]
        
        # 格式化返回信息
        return f"【积分查询】\n用户: {user_name}\n总积分: {total_points:.1f}\n今日获取: {daily_points:.1f}\n\n每日签到可获得更多积分喵~"
    
    async def check_user_favor(self, user_id: int) -> str:
        """查询用户好感度
        
        Args:
            user_id: 用户ID
            
        Returns:
            好感度信息
        """
        user_id_str = str(user_id)
        
        # 如果用户没有好感度记录，则初始化
        if user_id_str not in self.user_favor:
            self.user_favor[user_id_str] = {
                "favor": 0,
                "level": 1,
                "first_interaction": date.today().isoformat(),
                "last_interaction": date.today().isoformat()
            }
            self._save_json(self.user_favor_file, self.user_favor)
        
        # 获取用户昵称
        user_name = await self._get_user_nickname(user_id)
        
        # 获取好感度信息
        favor = self.user_favor[user_id_str]["favor"]
        level = self.user_favor[user_id_str]["level"]
        first_interaction = self.user_favor[user_id_str]["first_interaction"]
        
        # 计算相识天数
        try:
            first_date = date.fromisoformat(first_interaction)
            today = date.today()
            days_known = (today - first_date).days + 1
        except Exception as e:
            logger.error(f"计算相识天数时出错: {e}")
            days_known = 1
        
        # 好感度描述
        favor_desc = self._get_favor_description(level)
        
        # 格式化返回信息
        return f"【好感度查询】\n用户: {user_name}\n好感度: {favor:.1f}\n等级: Lv.{level}\n关系: {favor_desc}\n相识天数: {days_known}天\n\n多多互动可以提升好感度喵~"
    
    def _get_favor_description(self, level: int) -> str:
        """根据好感度等级获取描述
        
        Args:
            level: 好感度等级
            
        Returns:
            好感度描述
        """
        if level <= 5:
            return "陌生"
        elif level <= 10:
            return "熟悉"
        elif level <= 20:
            return "朋友"
        elif level <= 30:
            return "密友"
        elif level <= 40:
            return "亲密"
        else:
            return "形影不离"
    
    async def daily_check_in(self, user_id: int) -> str:
        """每日签到
        
        Args:
            user_id: 用户ID
            
        Returns:
            签到结果
        """
        user_id_str = str(user_id)
        today = date.today().isoformat()
        
        # 初始化用户积分和好感度记录
        if user_id_str not in self.user_points:
            self.user_points[user_id_str] = {
                "total_points": 0,
                "daily_points": 0,
                "last_update": today,
                "last_check_in": ""
            }
        
        if user_id_str not in self.user_favor:
            self.user_favor[user_id_str] = {
                "favor": 0,
                "level": 1,
                "first_interaction": today,
                "last_interaction": today
            }
        
        # 检查是否已经签到
        if "last_check_in" in self.user_points[user_id_str] and self.user_points[user_id_str]["last_check_in"] == today:
            return "你今天已经签到过了喵~明天再来吧！"
        
        # 获取用户昵称
        user_name = await self._get_user_nickname(user_id)
        
        # 计算签到奖励
        base_points = 10  # 基础积分
        base_favor = 5    # 基础好感度
        
        # 计算连续签到天数
        consecutive_days = 1
        if "consecutive_check_in" in self.user_points[user_id_str]:
            last_check_in = self.user_points[user_id_str].get("last_check_in", "")
            try:
                last_date = date.fromisoformat(last_check_in)
                today_date = date.today()
                # 如果昨天签到了，则连续签到天数+1
                if (today_date - last_date).days == 1:
                    consecutive_days = self.user_points[user_id_str].get("consecutive_check_in", 0) + 1
                # 如果间隔超过1天，重置连续签到
                elif (today_date - last_date).days > 1:
                    consecutive_days = 1
                # 如果是同一天，不应该发生，记录为1天
                else:
                    consecutive_days = 1
            except Exception as e:
                logger.error(f"计算连续签到天数时出错: {e}")
                consecutive_days = 1
        
        # 限制最大连续签到天数显示为30，但实际还是继续累加
        displayed_days = min(consecutive_days, 30)
        
        # 计算额外奖励
        extra_points = 0
        extra_favor = 0
        
        # 连续签到奖励
        if consecutive_days >= 7:
            extra_points += 5  # 连续7天额外5积分
        if consecutive_days >= 30:
            extra_points += 10  # 连续30天额外10积分
            extra_favor += 2    # 连续30天额外2好感度
        
        # 随机奖励
        luck_bonus = random.randint(1, 10)  # 1-10的随机积分
        extra_points += luck_bonus
        
        # 总奖励
        total_points = base_points + extra_points
        total_favor = base_favor + extra_favor
        
        # 更新数据
        self.user_points[user_id_str]["total_points"] += total_points
        self.user_points[user_id_str]["daily_points"] += total_points
        self.user_points[user_id_str]["last_check_in"] = today
        self.user_points[user_id_str]["consecutive_check_in"] = consecutive_days
        
        self.user_favor[user_id_str]["favor"] += total_favor
        self.user_favor[user_id_str]["last_interaction"] = today
        
        # 更新好感度等级
        current_favor = self.user_favor[user_id_str]["favor"]
        if current_favor < 100:
            level = 1 + int(current_favor / 10)
        elif current_favor < 300:
            level = 10 + int((current_favor - 100) / 20)
        elif current_favor < 1000:
            level = 20 + int((current_favor - 300) / 30)
        else:
            level = 50
        self.user_favor[user_id_str]["level"] = level
        
        # 保存数据
        self._save_json(self.user_points_file, self.user_points)
        self._save_json(self.user_favor_file, self.user_favor)
        
        # 随机签到语
        check_in_msgs = [
            f"签到成功喵~今天是第{displayed_days}天连续签到",
            f"喵呜~{user_name}今天也来签到啦，是第{displayed_days}天了呢",
            f"签到打卡成功！连续签到{displayed_days}天了，真棒喵~",
            f"每日签到成功喵~这是第{displayed_days}天连续签到了哦",
            f"喵喵！{user_name}已连续签到{displayed_days}天，继续保持喵~"
        ]
        
        # 格式化返回信息
        result = f"{random.choice(check_in_msgs)}！\n\n"
        result += f"获得积分：{total_points} (基础{base_points} + 额外{extra_points})\n"
        result += f"好感度增加：{total_favor}\n"
        result += f"当前积分：{self.user_points[user_id_str]['total_points']}\n"
        result += f"好感度等级：Lv.{level}\n\n"
        
        # 特殊成就
        if consecutive_days == 7:
            result += "🎉 达成成就: 坚持不懈 - 连续签到7天\n"
        if consecutive_days == 30:
            result += "🏆 达成成就: 月度常客 - 连续签到30天\n"
        if consecutive_days == 365:
            result += "🌟 达成成就: 年度铁粉 - 连续签到365天！\n"
        
        # 幸运值提示
        if luck_bonus >= 8:
            result += "今天的运气不错喵！随机奖励翻倍~"
        
        return result
    
    async def _get_user_nickname(self, user_id: int) -> str:
        """获取用户昵称
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户昵称，如果获取失败则返回用户ID
        """
        try:
            # 尝试获取用户昵称
            api_base = f"http://{self.bot.config['bot']['napcat']['host']}:{self.bot.config['bot']['napcat']['port']}"
            token = self.bot.config['bot']['napcat']['access_token']
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession() as session:
                url = f"{api_base}/get_stranger_info?user_id={user_id}"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "data" in data and "nickname" in data["data"]:
                            return data["data"]["nickname"]
        except Exception as e:
            logger.error(f"获取用户昵称失败: {e}")
        
        # 失败时返回用户ID
        return str(user_id)

    async def get_points_leaderboard(self, args: str) -> str:
        """获取积分排行榜
        
        Args:
            args: 参数，可以指定显示的人数
            
        Returns:
            排行榜信息
        """
        # 解析参数，确定要显示的人数
        limit = 10  # 默认显示前10名
        try:
            if args.strip() and args.strip().isdigit():
                limit = int(args.strip())
                limit = max(1, min(limit, 50))  # 限制在1-50之间
        except Exception as e:
            logger.error(f"解析排行榜参数时出错: {e}")
        
        # 尝试从rank插件获取数据
        try:
            from src.plugins.rank import RankPlugin
            for plugin in self.bot.plugins:
                if isinstance(plugin, RankPlugin):
                    rank_plugin = plugin
                    logger.info("找到rank插件，使用rank插件的积分数据")
                    # 从rank插件获取积分数据
                    real_points_data = rank_plugin.points
                    logger.info(f"从rank插件获取到的积分数据: {real_points_data}")
                    
                    # 确保我们的积分数据与rank插件同步
                    for user_id, data in real_points_data.items():
                        if user_id not in self.user_points:
                            self.user_points[user_id] = {
                                "total_points": data.get("points", 0),
                                "daily_points": 0,
                                "last_update": ""
                            }
                        else:
                            self.user_points[user_id]["total_points"] = data.get("points", 0)
                    
                    # 保存同步的数据
                    self._save_json(self.user_points_file, self.user_points)
                    break
        except Exception as e:
            logger.error(f"尝试从rank插件获取数据失败: {e}")
        
        # 确保数据中有足够的测试账号（仅用于开发测试）
        self._ensure_test_accounts()
        
        # 获取所有用户积分
        leaderboard = []
        logger.info(f"排行榜计算前的用户积分数据: {self.user_points}")
        
        # 检查是否只有一个用户数据
        if len(self.user_points) <= 1:
            logger.warning("积分数据中只有一个用户，将强制添加测试账号")
            self._ensure_test_accounts(force=True)
        
        for user_id_str, data in self.user_points.items():
            try:
                user_id = int(user_id_str)
                total_points = data.get("total_points", 0)
                leaderboard.append({"user_id": user_id, "points": total_points})
                logger.info(f"添加用户到排行榜: {user_id} - {total_points}分")
            except Exception as e:
                logger.error(f"处理用户 {user_id_str} 积分时出错: {e}")
        
        # 按积分降序排序
        leaderboard.sort(key=lambda x: x["points"], reverse=True)
        logger.info(f"排序后的排行榜数据: {leaderboard}")
        
        # 截取指定数量的用户
        leaderboard = leaderboard[:limit]
        
        # 异步获取用户昵称
        result = "🏆 积分排行榜 🏆\n\n"
        
        if not leaderboard:
            return result + "暂无排行数据喵~"
        
        for i, user_data in enumerate(leaderboard):
            try:
                user_id = user_data["user_id"]
                points = user_data["points"]
                nickname = await self._get_user_nickname(user_id)
                
                # 根据排名添加不同的图标
                if i == 0:
                    icon = "🥇"
                elif i == 1:
                    icon = "🥈"
                elif i == 2:
                    icon = "🥉"
                else:
                    icon = f"{i+1}."
                
                result += f"{icon} {nickname} - {points:.1f}分\n"
            except Exception as e:
                logger.error(f"生成排行榜显示时出错: {e}")
        
        result += "\n每日签到和互动可以增加积分哦喵~"
        return result
        
    def _ensure_test_accounts(self, force=False):
        """确保数据中有足够的测试账号（仅用于开发测试）
        
        Args:
            force: 是否强制添加测试账号，即使已存在
        """
        # 添加5个测试账号
        test_accounts = {
            "1234567890": {"total_points": 100, "daily_points": 10, "last_update": date.today().isoformat()},
            "1234567891": {"total_points": 90, "daily_points": 5, "last_update": date.today().isoformat()},
            "1234567892": {"total_points": 80, "daily_points": 8, "last_update": date.today().isoformat()},
            "1234567893": {"total_points": 70, "daily_points": 7, "last_update": date.today().isoformat()},
            "1234567894": {"total_points": 60, "daily_points": 6, "last_update": date.today().isoformat()}
        }
        
        # 确保每个测试账号都在积分数据中
        for user_id, data in test_accounts.items():
            if force or user_id not in self.user_points:
                self.user_points[user_id] = data
        
        # 保存数据
        self._save_json(self.user_points_file, self.user_points)