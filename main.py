import asyncio
import signal
import sys
import argparse
from loguru import logger
from src.bot import BettQQBot
from src.plugins.chat import ChatPlugin
from src.utils.config import load_config as utils_load_config
from src.utils.crypto import compare_config_files
import time
import os
import yaml
from cryptography.fernet import Fernet

# 创建命令行参数解析器
parser = argparse.ArgumentParser(description='BettQQBot启动器')
parser.add_argument('--debug', action='store_true', help='启用调试模式')
args = parser.parse_args()

# 配置日志格式
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if args.debug else "INFO",
    colorize=True,
)

# 全局变量，用于中断主循环
shutdown_event = asyncio.Event()

# 定义信号处理函数
def signal_handler(sig, frame):
    """处理终止信号"""
    ChatPlugin.on_unload()
    logger.info(f"收到信号 {signal.Signals(sig).name}...")
    # 尝试设置事件
    try:
        asyncio.get_event_loop().call_soon_threadsafe(shutdown_event.set)
    except:
        pass
    # 3秒后强制退出，给足够时间显示统计信息
    import threading
    def force_exit():
        logger.info("=" * 40)
        logger.info("程序未能正常退出，执行强制退出...")
        logger.info("=" * 40)
        import os
        os._exit(0)
    threading.Timer(3.0, force_exit).start()

async def shutdown(bot: BettQQBot, signal=None):
    """优雅关闭"""
    if signal:
        logger.info(f"收到信号 {signal.name}...")
    logger.info("正在关闭机器人...")
    
    # 显示AI会话统计
    try:
        if hasattr(bot, 'plugin_manager') and 'chat' in bot.plugin_manager.plugins:
            chat_plugin = bot.plugin_manager.plugins['chat']
            if hasattr(chat_plugin, '_show_session_stats'):
                logger.info("正在生成AI会话统计...")
                chat_plugin._show_session_stats()
    except Exception as e:
        logger.error(f"显示AI会话统计失败: {e}")
    
    try:
        await bot.shutdown()
    except Exception as e:
        logger.error(f"关闭机器人时出错: {e}")
    
    # 强制退出
    logger.info("程序将在1秒后退出...")
    await asyncio.sleep(1)
    import os
    os._exit(0)  # 使用os._exit强制退出


def handle_exception(loop, context):
    """处理未捕获的异常"""
    msg = context.get("exception", context["message"])
    logger.error(f"未捕获的异常: {msg}")

def load_config():
    """加载配置文件"""
    logger.info("正在加载配置文件...")
    try:
        config = utils_load_config()
        return config
    except Exception as e:
        logger.error(f"加载配置文件时出错: {e}")
        sys.exit(1)

def init_logger():
    """初始化日志系统"""
    # 设置日志级别
    if args.debug:
        logger.level("DEBUG")
        logger.info("调试模式已启用，日志级别设置为 DEBUG")
    else:
        logger.level("INFO")
        logger.info("调试模式已禁用，日志级别设置为 INFO")
    
    # 添加文件处理器
    logger.add("logs/bot_{time}.log", rotation="500 MB", compression="zip", retention="10 days")

async def main():
    """主函数"""
    # 初始化日志
    init_logger()

    # 加载配置
    config = load_config()
    
    # 打印启动信息
    logger.info("BettQQBot 正在启动...")
    
    # 加载插件
    logger.info("正在加载插件...")
    bot = BettQQBot(config)
    
    # 初始化机器人
    logger.info("正在初始化机器人...")
    await bot.initialize()

    # 设置日志级别
    if args.debug:
        logger.info("调试模式已启用，日志级别设置为 DEBUG")
    else:
        logger.info("调试模式已禁用，日志级别设置为 INFO")
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):  # Windows 环境可能没有 SIGTERM
        signal.signal(signal.SIGTERM, signal_handler)

    # 启动机器人
    try:
        await bot.start()
        # 等待关闭事件
        await shutdown_event.wait()
        logger.info("收到关闭信号，准备退出...")
    except asyncio.CancelledError:
        logger.info("任务被取消")
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，正在关闭...")
    except Exception as e:
        logger.error(f"运行时出错: {e}")
    finally:
        await shutdown(bot)


if __name__ == "__main__":
    # 启动LOGO
    logger.success(f"""
  ____       _   _      ___    ___    ____        _   
 | __ )  ___| |_| |_   / _ \  / _ \  | __ )  ___ | |_ 
 |  _ \\ / _ \\ __| __| | | | | | | | | |  _ \\ / _ \| __|
 | |_) |  __/ |_| |_  | |_| | | |_| | | |_) | (_) | |_ 
 |____/ \\___/\__|\__|  \__\_\\ \\__\_\\ |____/ \___/ \__|

    make by Ciallo喵喵
    QQ:3688442118
""")
    logger.info("BettQQBot 正在启动...")
    try:
        # 设置事件循环策略
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序崩溃: {e}")
        sys.exit(1)
