# BettQQBot 可执行文件说明

这是BettQQBot的独立可执行文件版本，无需安装Python环境即可运行。

## 快速开始

1. 确保配置文件 (`config.yaml` 或 `config.encrypted.yaml`) 存在
2. 确保 `keys` 目录存在并包含正确的密钥文件
3. 双击 `start.cmd` 
## 必要依赖

此版本已包含以下必要依赖:

- openai - 聊天模块依赖
- pytz - 时区处理依赖
- aiohttp - 异步HTTP请求
- loguru - 日志记录
- cryptography - 配置加密

## 文件结构说明

分发包包含以下文件和目录:

```
BettQQBot_v20250420/
├─ BettQQBot.exe        # 主程序可执行文件
├─ 启动BettQQBot.bat    # 快速启动脚本
├─ config.encrypted.yaml # 加密的配置文件
├─ keys/                # 密钥目录
│  ├─ private_key.pem   # RSA私钥
│  └─ public_key.pem    # RSA公钥
├─ data/                # 数据目录
│  ├─ sign_in/          # 签到数据
│  └─ memories/         # 聊天记忆数据
└─ logs/                # 日志目录
```

## 故障排除

### 缺少模块错误

如果遇到类似 `No module named 'xxx'` 的错误，这可能是因为某些模块未被正确打包。解决方法:

1. 在有Python环境的机器上运行以下命令安装缺失的模块:
   ```
   pip install openai pytz aiohttp pyyaml loguru cryptography
   ```

2. 重新运行打包脚本构建可执行文件

### 如何在你自己的机器上构建

如果希望在自己的机器上构建可执行文件:

1. 克隆或下载BettQQBot项目源码
2. 安装所需依赖: `pip install -r requirements.txt` 
3. 运行: `python build_exe.py` 或双击 `build_exe.bat`
4. 或者使用: `dist_package.bat` 创建完整的分发包

### 配置文件错误

如果出现配置文件相关错误:

1. 确保配置文件路径正确
2. 确保keys目录中包含正确的RSA密钥文件
3. 可以尝试使用明文配置文件 `config.yaml` 替代加密配置

### 运行时依赖

运行此程序需要安装 Microsoft Visual C++ 2015-2022 Redistributable。
如果运行时出现 `vcruntime140.dll 缺失` 等错误，请安装:
https://aka.ms/vs/17/release/vc_redist.x64.exe

## 安全注意事项

1. 保持RSA密钥文件安全，不要泄露私钥
2. 定期备份配置文件和data目录
3. 如果部署在公共环境中，确保妥善保管密钥和配置

## 更多信息

如有问题或需要支持，请联系作者:

作者：Ciallo喵喵
QQ: 3688442118 