import yaml
import os
import json
from loguru import logger
from .crypto import ConfigEncryption

def load_config(config_path: str = None):
    """
    加载并解密配置文件
    
    Args:
        config_path: 配置文件路径，如果为None，则会自动尝试多个可能的路径
                    如果是字典，则直接返回这个字典
                    
    Returns:
        解密后的配置数据
    """
    try:
        # 如果输入已经是字典，直接返回
        if isinstance(config_path, dict):
            logger.debug("配置已经是字典类型，无需加载文件")
            return config_path
            
        # 定义可能的配置文件路径
        possible_paths = []
        
        # 如果指定了路径，将其添加为首选
        if config_path:
            possible_paths.append(config_path)
        
        # 添加默认路径
        possible_paths.extend(["config.yaml", "config.encrypted.yaml"])
        
        # 尝试读取所有可能的配置文件路径
        config_data = None
        used_path = None
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"尝试加载配置文件: {path}")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        config_data = yaml.safe_load(f)
                    used_path = path
                    break
                except Exception as e:
                    logger.warning(f"读取配置文件 {path} 时出错: {e}")
        
        if config_data is None:
            available_paths = ", ".join(possible_paths)
            error_msg = f"未能找到有效的配置文件。尝试过的路径: {available_paths}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 初始化解密工具
        config_encryption = ConfigEncryption()
        
        # 解密配置文件
        decrypted_config = config_encryption.decrypt_config(config_data)
        
        # 检查解密是否成功
        encrypted_count = 0
        segmented_count = 0
        
        # 用于递归检查加密状态
        def check_encrypted_items(data):
            nonlocal encrypted_count, segmented_count
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and k.startswith("ENC:"):
                        encrypted_count += 1
                    check_encrypted_items(v)
            elif isinstance(data, list):
                for item in data:
                    check_encrypted_items(item)
            elif isinstance(data, str):
                if data.startswith("ENC:"):
                    encrypted_count += 1
                elif data.startswith("SEGENC:"):
                    segmented_count += 1
        
        # 检查解密前的数据
        check_encrypted_items(config_data)
        
        # 打印解密统计
        if encrypted_count > 0 or segmented_count > 0:
            logger.info(f"配置文件 {used_path} 包含加密内容")
            if encrypted_count > 0:
                logger.info(f"检测到 {encrypted_count} 个标准加密项")
            if segmented_count > 0:
                logger.info(f"检测到 {segmented_count} 个分段加密项")
            logger.success(f"已成功解密配置文件")
        else:
            logger.info(f"配置文件 {used_path} 不包含加密内容")
        
        return decrypted_config
    except Exception as e:
        logger.error(f"加载配置文件时出错: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        raise 