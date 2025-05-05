#!/usr/bin/env python
"""
配置文件全文本加密工具

用法: python encrypt_all_text.py <input_file> [output_file]

此脚本会读取指定的配置文件，并将其中所有的文本值进行加密处理，
包括键值对中的值、列表项等所有字符串，不仅限于敏感信息。

例如：
python encrypt_all_text.py config.yaml config.encrypted.yaml
"""

import os
import sys
import yaml
import base64
from loguru import logger
from src.utils.crypto import RSACrypto, ConfigEncryption
from typing import Dict, Any, Union, List

class AllTextEncryption:
    def __init__(self):
        self.crypto = RSACrypto()
        self.segment_size = 20  # 设置分段大小，每段约20个字符
    
    def encrypt_all_text(self, data):
        """递归加密所有文本值"""
        if isinstance(data, dict):
            return self._encrypt_dict(data)
        elif isinstance(data, list):
            return self._encrypt_list(data)
        elif isinstance(data, str):
            # 加密所有字符串值
            if not data:  # 跳过空字符串
                return data
            # 跳过已经加密的内容
            if data.startswith("ENC:"):
                logger.debug(f"跳过已加密的内容，长度: {len(data)}")
                return data
            
            # 对于超长文本，进行分段加密
            if len(data) > 200:  # 超过200个字符视为超长文本
                return self._segment_encrypt(data)
            
            try:
                encrypted = self.crypto.encrypt(data)
                return f"ENC:{encrypted}"
            except Exception as e:
                logger.warning(f"加密文本失败: {e}, 长度: {len(data)}")
                # 对于加密失败的长文本，尝试分段加密
                if len(data) > 50:
                    logger.info(f"尝试对长度为 {len(data)} 的文本进行分段加密")
                    return self._segment_encrypt(data)
                return data  # 仍然失败，保留原始值
        else:
            # 对于数字、布尔值等其他类型，保持不变
            return data
    
    def _segment_encrypt(self, text):
        """对长文本进行分段加密"""
        segments = []
        # 分割文本为固定大小的块
        for i in range(0, len(text), self.segment_size):
            segment = text[i:i + self.segment_size]
            try:
                encrypted = self.crypto.encrypt(segment)
                segments.append(f"ENC:{encrypted}")
            except Exception as e:
                logger.error(f"分段加密失败，索引 {i}-{i+self.segment_size}: {e}")
                segments.append(segment)  # 如果加密失败，保留原段
        
        # 返回特殊格式标记这是分段加密的内容
        return f"SEGENC:{len(segments)}:{':'.join(segments)}"
    
    def _encrypt_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """加密字典中的所有文本值"""
        result = {}
        for k, v in d.items():
            try:
                # 先加密键（如果是字符串）
                if isinstance(k, str) and k and not k.startswith("ENC:"):
                    try:
                        encrypted_key = self.crypto.encrypt(k)
                        k = f"ENC:{encrypted_key}"
                    except Exception as e:
                        logger.debug(f"键加密失败，保留原始键: {k}, 错误: {e}")
                
                # 然后加密/处理值
                result[k] = self.encrypt_all_text(v)
            except Exception as e:
                logger.error(f"处理键 '{k}' 时出错: {e}")
                result[k] = v  # 出错时保留原值
        return result
    
    def _encrypt_list(self, lst: List) -> List:
        """加密列表中的所有文本值"""
        result = []
        for item in lst:
            try:
                result.append(self.encrypt_all_text(item))
            except Exception as e:
                logger.error(f"处理列表项时出错: {e}")
                result.append(item)  # 出错时保留原值
        return result

def encrypt_file(input_path: str, output_path: str, force_mode=True):
    """加密指定文件的所有文本内容
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        force_mode: 是否使用强制模式（遇到错误继续处理）
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            logger.error(f"输入文件不存在: {input_path}")
            return False
        
        # 读取输入文件
        with open(input_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if data is None:
            logger.error(f"输入文件为空或格式错误: {input_path}")
            return False
        
        # 检查文件是否已经包含加密内容
        file_already_encrypted = False
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "ENC:" in content:
                file_already_encrypted = True
                logger.warning(f"文件 {input_path} 似乎已包含加密内容，将跳过已加密部分")
        
        # 创建加密器并加密所有文本
        encryptor = AllTextEncryption()
        
        try:
            encrypted_data = encryptor.encrypt_all_text(data)
        except Exception as e:
            if force_mode:
                logger.error(f"加密过程中出现错误（使用强制模式继续）: {e}")
                # 在强制模式下，尝试逐项处理
                encrypted_data = {}
                for k, v in data.items():
                    try:
                        # 先尝试加密键
                        new_key = k
                        if isinstance(k, str) and k and not k.startswith("ENC:"):
                            try:
                                encrypted_key = encryptor.crypto.encrypt(k)
                                new_key = f"ENC:{encrypted_key}"
                            except:
                                logger.warning(f"无法加密键 '{k}'，保留原始值")
                        
                        # 然后尝试加密值（或保留原值）
                        try:
                            encrypted_data[new_key] = encryptor.encrypt_all_text(v)
                        except:
                            logger.warning(f"无法加密键 '{k}' 的值，保留原始值")
                            encrypted_data[new_key] = v
                    except Exception as item_err:
                        logger.error(f"处理项 '{k}' 时出错: {item_err}")
                        encrypted_data[k] = v
            else:
                logger.error(f"加密失败: {e}")
                return False
        
        # 写入输出文件
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(encrypted_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.success(f"文件加密成功: {input_path} -> {output_path}")
        
        # 创建备份文件用于启动时验证
        backup_path = "config.backup.yaml"
        if output_path.lower().endswith("config.yaml"):
            with open(backup_path, 'w', encoding='utf-8') as f:
                yaml.dump(encrypted_data, f, default_flow_style=False, allow_unicode=True)
            logger.success(f"已创建加密备份文件: {backup_path}")
        
        return True
    
    except Exception as e:
        logger.error(f"加密文件失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

def main():
    """主函数"""
    # 创建命令行参数解析器
    import argparse
    parser = argparse.ArgumentParser(description='配置文件全文本加密工具')
    parser.add_argument('input_file', help='要加密的输入文件路径')
    parser.add_argument('output_file', nargs='?', help='加密后的输出文件路径（可选）')
    parser.add_argument('--force', '-f', action='store_true', help='强制模式：遇到错误继续处理')
    parser.add_argument('--skip-encrypted', '-s', action='store_true', help='跳过已经包含加密内容的文件')
    
    args = parser.parse_args()
    
    input_file = args.input_file
    
    if args.output_file:
        output_file = args.output_file
    else:
        # 如果未指定输出文件，使用输入文件名加上.encrypted后缀
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}.encrypted{ext}"
    
    # 检查是否已经包含加密内容
    if args.skip_encrypted:
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "ENC:" in content:
                    logger.warning(f"文件 {input_file} 已包含加密内容，根据 --skip-encrypted 选项跳过处理")
                    return 0
        except Exception as e:
            logger.error(f"检查文件内容时出错: {e}")
    
    # 创建原始文件的备份
    original_backup = f"{input_file}.original"
    try:
        import shutil
        shutil.copy2(input_file, original_backup)
        logger.success(f"已创建原始文件备份: {original_backup}")
    except Exception as e:
        logger.error(f"创建备份文件失败: {e}")
    
    # 执行加密
    if encrypt_file(input_file, output_file, force_mode=args.force):
        logger.success(f"加密完成！")
        logger.info(f"原始文件备份: {original_backup}")
        logger.info(f"加密后文件: {output_file}")
        return 0
    else:
        logger.error(f"加密失败！")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 