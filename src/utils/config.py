import yaml
import os
from loguru import logger

def load_config(config_path: str):
    try:
        if not os.path.exists(config_path):
            logger.error(f"配置文件 {config_path} 不存在")
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            
        logger.info(f"已加载配置文件 {config_path}")
        return config
    except Exception as e:
        logger.error(f"加载配置文件时出错: {e}")
        raise 