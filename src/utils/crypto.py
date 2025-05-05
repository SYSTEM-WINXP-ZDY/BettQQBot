import os
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from loguru import logger
import yaml
from typing import Dict, Any, Union, Optional
import json

class RSACrypto:
    def __init__(self, keys_dir: str = "keys"):
        self.keys_dir = keys_dir
        self.private_key_path = os.path.join(keys_dir, "private_key.pem")
        self.public_key_path = os.path.join(keys_dir, "public_key.pem")
        self.private_key = None
        self.public_key = None
        
        # 确保密钥目录存在
        if not os.path.exists(keys_dir):
            os.makedirs(keys_dir)
        
        # 检查密钥是否存在，如果不存在则生成
        if not os.path.exists(self.private_key_path) or not os.path.exists(self.public_key_path):
            self._generate_keys()
        else:
            self._load_keys()
    
    def _generate_keys(self):
        """生成RSA密钥对并保存"""
        logger.info("正在生成RSA密钥对...")
        
        # 生成私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # 从私钥获取公钥
        public_key = private_key.public_key()
        
        # 将私钥保存到文件
        with open(self.private_key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
            )
        
        # 将公钥保存到文件
        with open(self.public_key_path, "wb") as f:
            f.write(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            )
        
        self.private_key = private_key
        self.public_key = public_key
        
        logger.success(f"RSA密钥对已生成并保存到 {self.keys_dir} 目录")
    
    def _load_keys(self):
        """从文件加载RSA密钥"""
        try:
            # 加载私钥
            with open(self.private_key_path, "rb") as f:
                private_key_data = f.read()
                self.private_key = serialization.load_pem_private_key(
                    private_key_data,
                    password=None,
                    backend=default_backend()
                )
            
            # 加载公钥
            with open(self.public_key_path, "rb") as f:
                public_key_data = f.read()
                self.public_key = serialization.load_pem_public_key(
                    public_key_data,
                    backend=default_backend()
                )
            
            logger.info("RSA密钥已成功加载")
        except Exception as e:
            logger.error(f"加载RSA密钥失败: {e}")
            raise
    
    def encrypt(self, data: str) -> str:
        """使用RSA公钥加密字符串"""
        if not self.public_key:
            self._load_keys()
        
        try:
            # 将字符串转换为字节
            data_bytes = data.encode('utf-8')
            
            # 由于RSA加密长度有限制，这里使用分块加密
            # RSA-2048 可以加密的最大字节数约为 (2048/8) - 11 = 245 字节
            chunk_size = 200  # 使用较小的块大小以确保安全
            encrypted_chunks = []
            
            for i in range(0, len(data_bytes), chunk_size):
                chunk = data_bytes[i:i + chunk_size]
                try:
                    encrypted_chunk = self.public_key.encrypt(
                        chunk,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    encrypted_chunks.append(encrypted_chunk)
                except Exception as e:
                    logger.error(f"加密块 {i//chunk_size + 1} 失败: {e}")
                    logger.debug(f"问题数据块: {chunk}")
                    raise ValueError(f"加密块 {i//chunk_size + 1} 失败: {e}")
            
            # 将加密后的数据转换为Base64编码的字符串
            encrypted_data = b''.join(encrypted_chunks)
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(f"加密失败: {e}, 数据长度: {len(data)}")
            if len(data) > 1000:
                logger.error(f"数据过长，可能超出RSA加密能力。请考虑使用混合加密方式。")
            raise ValueError(f"加密失败: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """使用RSA私钥解密字符串"""
        if not self.private_key:
            self._load_keys()
        
        try:
            # 将Base64编码的字符串转换为字节
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # 由于RSA解密长度有限制，这里使用分块解密
            # RSA-2048 解密的块大小为 2048/8 = 256 字节
            chunk_size = 256
            decrypted_chunks = []
            
            for i in range(0, len(encrypted_bytes), chunk_size):
                chunk = encrypted_bytes[i:i + chunk_size]
                if len(chunk) == chunk_size:  # 确保只解密完整的块
                    try:
                        decrypted_chunk = self.private_key.decrypt(
                            chunk,
                            padding.OAEP(
                                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                algorithm=hashes.SHA256(),
                                label=None
                            )
                        )
                        decrypted_chunks.append(decrypted_chunk)
                    except Exception as e:
                        logger.error(f"解密块 {i//chunk_size + 1} 失败: {e}")
                        raise ValueError(f"解密块 {i//chunk_size + 1} 失败: {e}")
            
            # 将解密后的数据转换为字符串
            decrypted_data = b''.join(decrypted_chunks)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise ValueError(f"解密失败: {e}")

class ConfigEncryption:
    def __init__(self, keys_dir: str = "keys"):
        self.crypto = RSACrypto(keys_dir)
        self.sensitive_keys = [
            "access_token", 
            "token", 
            "api_key", 
            "password",
            "secret",
            "Authorization"
        ]
    
    def is_encrypted(self, value: str) -> bool:
        """检查值是否已经加密（通过简单的启发式方法）"""
        # 加密的数据通常以ENC: 开头
        if isinstance(value, str) and value.startswith("ENC:"):
            return True
        return False
    
    def encrypt_config(self, config: Dict[str, Any], output_path: str) -> None:
        """加密配置文件并保存"""
        encrypted_config = self._encrypt_dict(config)
        
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(encrypted_config, f, default_flow_style=False, allow_unicode=True)
        
        logger.success(f"加密后的配置已保存到 {output_path}")
    
    def encrypt_entire_config(self, config: Dict[str, Any], output_path: str) -> None:
        """加密整个配置文件（所有字符串值）"""
        encrypted_config = self._encrypt_entire_dict(config)
        
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(encrypted_config, f, default_flow_style=False, allow_unicode=True)
        
        logger.success(f"完全加密后的配置已保存到 {output_path}")
    
    def decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解密配置文件"""
        return self._decrypt_dict(config)
    
    def _encrypt_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """递归加密字典中的敏感字段"""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._encrypt_dict(value)
            elif isinstance(value, list):
                result[key] = self._encrypt_list(value)
            elif isinstance(value, str) and any(sensitive in key.lower() for sensitive in self.sensitive_keys) and not self.is_encrypted(value):
                # 对敏感字段进行加密
                encrypted_value = self.crypto.encrypt(value)
                result[key] = f"ENC:{encrypted_value}"
            else:
                result[key] = value
        return result
    
    def _encrypt_list(self, lst: list) -> list:
        """递归加密列表中的字典类型的元素"""
        result = []
        for item in lst:
            if isinstance(item, dict):
                result.append(self._encrypt_dict(item))
            elif isinstance(item, list):
                result.append(self._encrypt_list(item))
            else:
                result.append(item)
        return result
    
    def _encrypt_entire_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """递归加密字典中的所有字符串字段"""
        result = {}
        for key, value in d.items():
            try:
                if isinstance(value, dict):
                    result[key] = self._encrypt_entire_dict(value)
                elif isinstance(value, list):
                    result[key] = self._encrypt_entire_list(value)
                elif isinstance(value, str) and not self.is_encrypted(value):
                    # 跳过空字符串和仅包含空格的字符串
                    if not value.strip():
                        result[key] = value
                        continue
                    
                    # 长度超过1000的字符串给出警告
                    if len(value) > 1000:
                        logger.warning(f"字段 '{key}' 包含长度为 {len(value)} 的字符串，可能超出RSA加密能力")
                    
                    # 对所有字符串字段进行加密
                    try:
                        encrypted_value = self.crypto.encrypt(value)
                        result[key] = f"ENC:{encrypted_value}"
                    except Exception as e:
                        logger.error(f"加密字段 '{key}' 失败: {e}")
                        # 对于系统提示这类特别长的字符串，如果加密失败则保留原始值
                        if key == "system_prompt" or len(value) > 1000:
                            logger.warning(f"字段 '{key}' 加密失败，保留原始值")
                            result[key] = value
                        else:
                            raise
                else:
                    result[key] = value
            except Exception as e:
                logger.error(f"处理字段 '{key}' 时出错: {e}")
                # 保留原始值并继续处理其他字段
                result[key] = value
        return result
    
    def _encrypt_entire_list(self, lst: list) -> list:
        """递归加密列表中的所有元素"""
        result = []
        for index, item in enumerate(lst):
            try:
                if isinstance(item, dict):
                    result.append(self._encrypt_entire_dict(item))
                elif isinstance(item, list):
                    result.append(self._encrypt_entire_list(item))
                elif isinstance(item, str) and not self.is_encrypted(item):
                    # 跳过空字符串
                    if not item.strip():
                        result.append(item)
                        continue
                        
                    # 长字符串警告
                    if len(item) > 1000:
                        logger.warning(f"列表索引 {index} 包含长度为 {len(item)} 的字符串，可能超出RSA加密能力")
                    
                    # 对所有字符串进行加密
                    try:
                        encrypted_value = self.crypto.encrypt(item)
                        result.append(f"ENC:{encrypted_value}")
                    except Exception as e:
                        logger.error(f"加密列表项 {index} 失败: {e}")
                        # 如果加密失败则保留原始值
                        if len(item) > 1000:
                            logger.warning(f"列表项 {index} 加密失败，保留原始值")
                            result.append(item)
                        else:
                            raise
                else:
                    result.append(item)
            except Exception as e:
                logger.error(f"处理列表索引 {index} 时出错: {e}")
                # 保留原始值并继续处理
                result.append(item)
        return result
    
    def _decrypt_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """递归解密字典中的加密字段"""
        result = {}
        for key, value in d.items():
            try:
                # 首先检查键是否需要解密
                decrypted_key = key
                if isinstance(key, str) and key.startswith("ENC:"):
                    # 解密键
                    encrypted_key = key[4:]  # 去掉"ENC:"前缀
                    try:
                        decrypted_key = self.crypto.decrypt(encrypted_key)
                    except Exception as e:
                        logger.error(f"解密键失败: {e}")
                        decrypted_key = key  # 保留原始加密键
                
                # 然后递归处理值
                if isinstance(value, dict):
                    result[decrypted_key] = self._decrypt_dict(value)
                elif isinstance(value, list):
                    result[decrypted_key] = self._decrypt_list(value)
                elif isinstance(value, str):
                    # 处理不同类型的加密内容
                    if value.startswith("ENC:"):
                        # 标准加密内容
                        encrypted_value = value[4:]  # 去掉"ENC:"前缀
                        try:
                            decrypted_value = self.crypto.decrypt(encrypted_value)
                            result[decrypted_key] = decrypted_value
                        except Exception as e:
                            logger.error(f"解密字段 {decrypted_key} 失败: {e}")
                            result[decrypted_key] = value  # 保留原始加密值
                    elif value.startswith("SEGENC:"):
                        # 分段加密内容
                        try:
                            segments_info = value.split(":", 2)  # 分解成 SEGENC, 段数, 内容
                            if len(segments_info) >= 3:
                                num_segments = int(segments_info[1])
                                segments_data = segments_info[2]
                                # 分割为各个段
                                if num_segments > 0:
                                    segments = segments_data.split(":", num_segments)
                                    # 解密并组合各段
                                    decrypted_segments = []
                                    for segment in segments:
                                        if segment.startswith("ENC:"):
                                            try:
                                                # 解密该段
                                                enc_segment = segment[4:]  # 去掉"ENC:"前缀
                                                dec_segment = self.crypto.decrypt(enc_segment)
                                                decrypted_segments.append(dec_segment)
                                            except Exception as e:
                                                logger.error(f"解密段落失败: {e}")
                                                decrypted_segments.append(segment)  # 保留原始加密段
                                        else:
                                            # 未加密的段（可能是加密失败的段）
                                            decrypted_segments.append(segment)
                                    
                                    # 组合所有解密后的段
                                    result[decrypted_key] = "".join(decrypted_segments)
                                else:
                                    result[decrypted_key] = ""  # 没有段，返回空字符串
                            else:
                                logger.error(f"分段加密格式不正确: {value}")
                                result[decrypted_key] = value  # 保留原始格式不正确的值
                        except Exception as e:
                            logger.error(f"解析分段加密内容失败: {e}")
                            result[decrypted_key] = value  # 解析失败，保留原始值
                    else:
                        # 未加密的普通字符串
                        result[decrypted_key] = value
                else:
                    # 非字符串值（数字、布尔值等）
                    result[decrypted_key] = value
            except Exception as e:
                logger.error(f"处理字段 {key} 时出错: {e}")
                # 出错时保留原始键值对
                result[key] = value
        return result
    
    def _decrypt_list(self, lst: list) -> list:
        """递归解密列表中的字典类型的元素"""
        result = []
        for item in lst:
            try:
                if isinstance(item, dict):
                    result.append(self._decrypt_dict(item))
                elif isinstance(item, list):
                    result.append(self._decrypt_list(item))
                elif isinstance(item, str):
                    # 处理不同类型的加密内容
                    if item.startswith("ENC:"):
                        # 标准加密内容
                        encrypted_value = item[4:]  # 去掉"ENC:"前缀
                        try:
                            decrypted_value = self.crypto.decrypt(encrypted_value)
                            result.append(decrypted_value)
                        except Exception as e:
                            logger.error(f"解密列表项失败: {e}")
                            result.append(item)  # 保留原始加密值
                    elif item.startswith("SEGENC:"):
                        # 分段加密内容
                        try:
                            segments_info = item.split(":", 2)  # 分解成 SEGENC, 段数, 内容
                            if len(segments_info) >= 3:
                                num_segments = int(segments_info[1])
                                segments_data = segments_info[2]
                                # 分割为各个段
                                if num_segments > 0:
                                    segments = segments_data.split(":", num_segments)
                                    # 解密并组合各段
                                    decrypted_segments = []
                                    for segment in segments:
                                        if segment.startswith("ENC:"):
                                            try:
                                                # 解密该段
                                                enc_segment = segment[4:]  # 去掉"ENC:"前缀
                                                dec_segment = self.crypto.decrypt(enc_segment)
                                                decrypted_segments.append(dec_segment)
                                            except Exception as e:
                                                logger.error(f"解密段落失败: {e}")
                                                decrypted_segments.append(segment)  # 保留原始加密段
                                        else:
                                            # 未加密的段（可能是加密失败的段）
                                            decrypted_segments.append(segment)
                                    
                                    # 组合所有解密后的段
                                    result.append("".join(decrypted_segments))
                                else:
                                    result.append("")  # 没有段，返回空字符串
                            else:
                                logger.error(f"分段加密格式不正确: {item}")
                                result.append(item)  # 保留原始格式不正确的值
                        except Exception as e:
                            logger.error(f"解析分段加密内容失败: {e}")
                            result.append(item)  # 解析失败，保留原始值
                    else:
                        # 未加密的普通字符串
                        result.append(item)
                else:
                    result.append(item)
            except Exception as e:
                logger.error(f"处理列表项时出错: {e}")
                result.append(item)  # 出错时保留原始值
        return result

    def compare_configs(self, config1_path: str, config2_path: str) -> bool:
        """比较两个配置文件，如果内容相同返回True，否则返回False"""
        try:
            # 加载两个配置文件
            with open(config1_path, "r", encoding="utf-8") as f1:
                config1 = yaml.safe_load(f1)
            
            with open(config2_path, "r", encoding="utf-8") as f2:
                config2 = yaml.safe_load(f2)
            
            # 解密两个配置
            decrypted1 = self.decrypt_config(config1)
            decrypted2 = self.decrypt_config(config2)
            
            # 转换为JSON字符串进行比较
            json1 = json.dumps(decrypted1, sort_keys=True)
            json2 = json.dumps(decrypted2, sort_keys=True)
            
            # 比较两个解密后的配置
            return json1 == json2
        except Exception as e:
            logger.error(f"比较配置文件时出错: {e}")
            return False

def encrypt_config_file(input_path: str, output_path: Optional[str] = None):
    """加密配置文件的便捷函数"""
    if output_path is None:
        output_path = input_path
    
    try:
        # 加载原始配置
        with open(input_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 加密并保存
        encryptor = ConfigEncryption()
        encryptor.encrypt_config(config, output_path)
        
        logger.success(f"配置文件 {input_path} 已成功加密并保存到 {output_path}")
    except Exception as e:
        logger.error(f"加密配置文件失败: {e}")
        raise

def generate_key_pair(private_key_path, public_key_path):
    """生成RSA密钥对并保存到指定路径"""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    # 生成私钥
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # 将私钥保存到文件
    with open(private_key_path, 'wb') as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # 提取公钥
    public_key = private_key.public_key()
    
    # 将公钥保存到文件
    with open(public_key_path, 'wb') as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    
    return True

def encrypt_entire_config_file(input_path: str, output_path: Optional[str] = None, skip_errors: bool = True):
    """加密整个配置文件的便捷函数（所有字符串值）
    
    Args:
        input_path: 输入配置文件路径
        output_path: 输出配置文件路径，如果为None则覆盖输入文件
        skip_errors: 是否跳过加密错误（对于加密失败的字段保留原始值）
    """
    if output_path is None:
        output_path = input_path
    
    try:
        # 加载原始配置
        with open(input_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        if config is None:
            logger.error(f"配置文件 {input_path} 为空或格式不正确")
            raise ValueError(f"配置文件 {input_path} 为空或格式不正确")
        
        # 检查系统提示字段，可能很长
        if "features" in config and "chat" in config["features"] and "system_prompt" in config["features"]["chat"]:
            system_prompt = config["features"]["chat"]["system_prompt"]
            if isinstance(system_prompt, str) and len(system_prompt) > 1000:
                logger.warning(f"system_prompt 字段长度为 {len(system_prompt)}，超过1000字符，可能会导致加密问题")
                logger.info("尝试对长系统提示使用分段加密...")
        
        # 加密并保存
        encryptor = ConfigEncryption()
        encrypted_config = encryptor._encrypt_entire_dict(config)
        
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(encrypted_config, f, default_flow_style=False, allow_unicode=True)
        
        logger.success(f"配置文件 {input_path} 已完全加密并保存到 {output_path}")
        return True
    except Exception as e:
        logger.error(f"加密配置文件失败: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        if not skip_errors:
            raise
        return False

def compare_config_files(config1_path: str, config2_path: str) -> bool:
    """比较两个配置文件是否相同"""
    encryptor = ConfigEncryption()
    return encryptor.compare_configs(config1_path, config2_path)

if __name__ == "__main__":
    # 如果直接运行此文件，则加密配置文件
    import sys
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        encrypt_config_file(input_path, output_path)
    else:
        print("用法: python crypto.py <input_config.yaml> [output_config.yaml]") 