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
        elif command in ["签到", "check_in", "checkin"]:
            return await self.daily_check_in(user_id)
        else:
            logger.warning(f"未知的额外功能插件命令: {command}")
            return f"未知的命令: {command}"

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
            url = f"https://www.yiketianqi.com/free/day?appid=43656176&appsecret=I42og6Lm&city={encoded_city}&unescape=1"
            
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
            logger.error(f"第二个天气API获取失败: {e}")
        
        # 使用第三个API尝试获取天气 (搏天API)
        try:
            url = f"https://api.btstu.cn/weather/api.php?city={encoded_city}&type=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"第三个API返回状态码 {response.status}")
                    
                    data = await response.json()
                    if data["code"] != 200:
                        raise Exception(f"第三个API返回错误: {data}")
                    
                    weather = data["data"]
                    
                    result = f"{city}当前天气：\n"
                    result += f"• 天气状况：{weather['weather']}\n"
                    result += f"• 当前温度：{weather['temp']}°C\n"
                    result += f"• 温度范围：{weather['min_temp']}°C~{weather['max_temp']}°C\n"
                    result += f"• 风况：{weather['wind_direction']} {weather['wind_level']}级\n"
                    result += f"• 湿度：{weather.get('humidity', '未知')}%\n"
                    result += f"• 空气质量：{weather.get('aqi', '未知')}\n"
                    result += f"• 更新时间：{weather.get('last_update', '今日')}"
                    
                    return result
        except Exception as e:
            logger.error(f"第三个天气API获取失败: {e}")
            
        # 使用第四个API尝试获取天气 (阿里云天气API)
        try:
            host = 'https://jisutqybmf.market.alicloudapi.com'
            path = '/weather/query'
            method = 'GET'
            appcode = '9a6d0afb57da4d4a8d1b8f7ebe1a56ca'  # 替换为您的AppCode
            
            querys = f'city={encoded_city}'
            url = host + path + '?' + querys
            
            headers = {'Authorization': 'APPCODE ' + appcode}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"第四个API返回状态码 {response.status}")
                    
                    data = await response.json()
                    if data["status"] != 0:
                        raise Exception(f"第四个API返回错误: {data}")
                    
                    result = data["result"]
                    
                    weather_text = f"{result['city']}当前天气：\n"
                    weather_text += f"• 天气状况：{result['weather']}\n"
                    weather_text += f"• 当前温度：{result['temp']}°C\n"
                    weather_text += f"• 温度范围：{result['templow']}°C~{result['temphigh']}°C\n"
                    weather_text += f"• 风况：{result['winddirect']} {result['windpower']}\n"
                    weather_text += f"• 湿度：{result['humidity']}%\n"
                    weather_text += f"• 更新时间：{result['date']} {result['updatetime']}"
                    
                    return weather_text
        except Exception as e:
            logger.error(f"第四个天气API获取失败: {e}")
        
        # 所有API都失败，尝试最后一个简单的API
        try:
            url = f"https://api.seniverse.com/v3/weather/now.json?key=S44I9_N8CcwWUr-a7&location={encoded_city}&language=zh-Hans&unit=c"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"最后一个API返回状态码 {response.status}")
                    
                    data = await response.json()
                    if "results" not in data or not data["results"]:
                        raise Exception(f"最后一个API返回错误: {data}")
                    
                    result = data["results"][0]
                    location = result["location"]
                    now = result["now"]
                    
                    weather_text = f"{location['name']}当前天气：\n"
                    weather_text += f"• 天气状况：{now['text']}\n"
                    weather_text += f"• 当前温度：{now['temperature']}°C\n"
                    weather_text += f"• 相对湿度：{now.get('humidity', '未知')}%\n"
                    weather_text += f"• 体感温度：{now.get('feels_like', '未知')}°C\n"
                    weather_text += f"• 更新时间：{result.get('last_update', '今日')}"
                    
                    return weather_text
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
        
        # 检查用户今天是否已经说过早安
        if user_id_str in self.morning_greetings:
            return "你今天已经说过早安了喵~"
            
        # 添加用户到早安列表
        self.morning_greetings[user_id_str] = True
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
        count = len(self.morning_greetings)
        
        greeting += f"\n你是今天第 {count} 个说早安的人喵~"
        
        return greeting
        
    async def night_greeting(self, user_id: int, group_id: Optional[int]) -> str:
        """晚安问候"""
        user_id_str = str(user_id)
        
        # 检查用户今天是否已经说过晚安
        if user_id_str in self.night_greetings:
            return "你今天已经说过晚安了喵~好好睡觉吧！"
            
        # 添加用户到晚安列表
        self.night_greetings[user_id_str] = True
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
        count = len(self.night_greetings)
        
        greeting += f"\n你是今天第 {count} 个说晚安的人喵~"
        
        return greeting
        
    async def get_random_image(self, category: str = "") -> str:
        """获取随机图片"""
        try:
            # 使用国内稳定的免费二次元图片API
            if not category or category in ["二次元", "动漫", "女生","蔚蓝档案", "白丝"]:
                # 随机图片，90%女生，10%男生
                rand = random.randint(1, 10)
                if rand <= 10:  # 90%概率获取女生图片
                    url = "https://api.66mz8.com/api/rand.anime.php"
                else:  # 10%概率获取男生图片
                    url = "https://api.66mz8.com/api/rand.anime.php?type=4"
            elif category in ["女生", "巫师", "蔚蓝档案", "白丝"]:
                # 女生图片
                url = "https://api.66mz8.com/api/rand.anime.php?type=1"
            elif category in ["男生", "男孩", "少年"]:
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
            
    async def search_music(self, keyword: str) -> str:
        """搜索音乐"""
        if not keyword:
            return "请提供歌曲名称或歌手喵~\n例如: 点歌 周杰伦"
            
        try:
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 使用网易云音乐API
            encoded_keyword = urllib.parse.quote(keyword)
            url = f"https://music.163.com/api/search/get?s={encoded_keyword}&type=1&limit=1"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://music.163.com/"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"音乐API返回状态码 {response.status}")
                    
                    data = await response.json()
                    
                    if "result" not in data or "songs" not in data["result"] or not data["result"]["songs"]:
                        raise Exception("没有找到相关歌曲")
                    
                    songs = data["result"]["songs"]
                    if not songs:
                        return f"没有找到与\"{keyword}\"相关的歌曲喵~"
                    
                    song = songs[0]
                    song_id = song["id"]
                    song_name = song["name"]
                    artist = song["artists"][0]["name"] if song["artists"] else "未知歌手"
                    
                    # 返回点歌结果，使用CQ码
                    return f"[CQ:music,type=163,id={song_id}]"
                    
        except Exception as e:
            logger.error(f"搜索音乐时出错: {e}")
            
            # 备用API - QQ音乐
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                encoded_keyword = urllib.parse.quote(keyword)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://y.qq.com/"
                }
                
                # 使用QQ音乐官方API
                url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?w={encoded_keyword}&format=json&inCharset=utf-8&outCharset=utf-8&platform=yqq"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                        if response.status != 200:
                            raise Exception(f"备用音乐API返回状态码 {response.status}")
                        
                        data = await response.json()
                        if "data" not in data or "song" not in data["data"] or "list" not in data["data"]["song"] or not data["data"]["song"]["list"]:
                            raise Exception("备用音乐API返回数据格式错误")
                        
                        songs = data["data"]["song"]["list"]
                        if not songs:
                            return f"没有找到与\"{keyword}\"相关的歌曲喵~"
                        
                        song = songs[0]
                        song_id = song["songid"]
                        
                        # 返回点歌结果，使用CQ码
                        return f"[CQ:music,type=qq,id={song_id}]"
            except Exception as backup_error:
                logger.error(f"备用音乐API获取失败: {backup_error}")
                
            # 所有API都失败，返回固定消息
            return self.fallback_responses["music"]

    async def check_earthquake(self) -> str:
        """检查地震信息"""
        try:
            current_time = time.time()
            
            # 限制请求频率
            if current_time - self.last_earthquake_check < 60:  # 限制为每分钟最多一次
                return "查询地震信息的请求过于频繁喵~请稍后再试"
                
            self.last_earthquake_check = current_time
            
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 使用中国地震台网API
            url = "https://api.oioweb.cn/api/common/earthquake"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"地震API返回状态码 {response.status}")
                    
                    data = await response.json()
                    
                    if data["code"] != 200 or "result" not in data:
                        raise Exception("地震API返回数据格式错误")
                    
                    # 获取最新的地震信息
                    latest = data["result"]
                    
                    # 检查是否为新地震
                    earthquake_id = latest["time"] + latest["location"]
                    if self.last_earthquake_id == earthquake_id:
                        result = "最新地震信息（无更新）：\n"
                    else:
                        self.last_earthquake_id = earthquake_id
                        result = "最新地震信息：\n"
                    
                    result += f"发生时间: {latest['time']}\n"
                    result += f"震级: {latest['magnitude']}级\n"
                    result += f"震源深度: {latest['depth']}千米\n"
                    result += f"位置: {latest['location']}\n"
                    if 'latitude' in latest and 'longitude' in latest:
                        result += f"经纬度: {latest['longitude']}, {latest['latitude']}"
                    
                    return result
                    
        except Exception as e:
            logger.error(f"获取地震信息时出错: {e}")
            
            # 备用地震API - 新的中国地震数据API
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://www.tianqiapi.com/"
                }
                
                url = "https://v1.alapi.cn/api/earthquake?token=FJXwBhIGdq9UXe38"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                        if response.status != 200:
                            raise Exception(f"备用地震API返回状态码 {response.status}")
                        
                        data = await response.json()
                        if data["code"] != 200 or "data" not in data:
                            raise Exception("备用地震API返回数据格式错误")
                        
                        latest = data["data"]["list"][0]
                        
                        result = "最新地震信息：\n"
                        result += f"发生时间: {latest.get('time', '未知')}\n"
                        result += f"震级: {latest.get('magnitude', '未知')}级\n"
                        result += f"震源深度: {latest.get('depth', '未知')}千米\n"
                        result += f"位置: {latest.get('location', '未知')}"
                        
                        return result
            except Exception as backup_error:
                logger.error(f"备用地震API获取失败: {backup_error}")
                
            # 所有API都失败，返回固定消息
            return self.fallback_responses["earthquake"]
            
    async def get_news(self) -> str:
        """获取新闻"""
        try:
            # 创建SSL上下文并禁用证书验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 使用新的百度热搜API
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            url = "https://api.vvhan.com/api/hotlist?type=baidu"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"新闻API返回状态码 {response.status}")
                    
                    data = await response.json()
                    
                    if "success" not in data or not data["success"] or "data" not in data:
                        raise Exception("新闻API返回数据格式错误")
                    
                    # 获取前10条新闻
                    news = data["data"][:10]
                    
                    result = "【百度热搜新闻】\n\n"
                    for i, item in enumerate(news):
                        title = item["title"]
                        result += f"{i+1}. {title}\n"
                    
                    return result
                    
        except Exception as e:
            logger.error(f"获取新闻时出错: {e}")
            
            # 备用微博热搜API
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                
                url = "https://api.vvhan.com/api/hotlist?type=wbHot"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, ssl=ssl_context, timeout=10) as response:
                        if response.status != 200:
                            raise Exception(f"备用新闻API返回状态码 {response.status}")
                        
                        data = await response.json()
                        if "success" not in data or not data["success"] or "data" not in data:
                            raise Exception("备用新闻API返回数据格式错误")
                        
                        news_list = data["data"][:10]
                        
                        result = "【微博热搜】\n\n"
                        for i, item in enumerate(news_list):
                            title = item["title"]
                            result += f"{i+1}. {title}\n"
                        
                        return result
            except Exception as backup_error:
                logger.error(f"备用新闻API获取失败: {backup_error}")
            
            # 所有API都失败，返回固定消息
            return self.fallback_responses["news"]
            
    async def get_today_events(self) -> str:
        """获取历史上的今天"""
        try:
            # 获取当前日期
            today = datetime.now()
            month = today.month
            day = today.day
            
            # 使用天行数据API获取历史上的今天
            url = f"http://api.tianapi.com/todayhistory/index?key=71868b9de3d003c2bb9cf410edb9ba1a"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return f"获取历史事件失败喵~错误代码: {response.status}"
                    
                    data = await response.json()
                    
                    if data["code"] != 200 or "newslist" not in data or not data["newslist"]:
                        return f"未找到{month}月{day}日的历史事件喵~"
                    
                    events = data["newslist"]
                    
                    result = f"【历史上的今天: {month}月{day}日】\n\n"
                    # 最多显示5个事件
                    for i, event in enumerate(events[:5]):
                        year = event["year"]
                        title = event["title"]
                        result += f"{year}年: {title}\n"
                    
                    return result
                    
        except Exception as e:
            logger.error(f"获取历史事件时出错: {e}")
            
            # 备用API
            try:
                url = f"https://api.66mz8.com/api/history.php?format=json"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return "获取历史事件失败喵~请稍后再试"
                        
                        data = await response.json()
                        if not data or len(data) == 0:
                            return f"未找到{month}月{day}日的历史事件喵~"
                        
                        result = f"【历史上的今天: {month}月{day}日】\n\n"
                        for i, event in enumerate(data[:5]):
                            result += f"{event['year']}年: {event['title']}\n"
                        
                        return result
            except Exception as backup_error:
                logger.error(f"备用历史事件API获取失败: {backup_error}")
                return "获取历史事件失败喵~请稍后再试"
            
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