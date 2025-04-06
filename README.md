# BettQQBot

一个基于 NapCat 和 OneBot 的 QQ 机器人项目。

作者: Ciallo (QQ: 3688442118)

## 功能特性

- 基础功能
  - 自动同意加群请求
  - 简单的 ping-pong 测试
- 聊天功能
  - 接入 OpenAI GPT 模型
  - 支持私聊和群聊
- 签到系统
  - 每日签到
  - 随机积分奖励
  - 积分统计

## 安装

1. 克隆项目：
```bash
git clone https://github.com/Ciallo/BettQQBot.git
cd BettQQBot
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置机器人：
   - 复制 `config.yaml` 并填写相关配置
   - 设置 NapCat 的连接信息
   - 配置 OpenAI API 密钥（如果需要使用聊天功能）

## 使用方法

1. 启动机器人：
```bash
python main.py
```

2. 可用命令：
   - `/chat <内容>` - 与 AI 对话
   - `/签到` - 每日签到
   - `ping` - 测试机器人是否在线

## 配置说明

配置文件 `config.yaml` 包含以下主要部分：

```yaml
bot:
  napcat:
    host: "127.0.0.1"  # NapCat 服务器地址
    port: 8080         # 服务器端口
    access_token: ""   # 访问令牌

features:
  chat:
    enabled: true
    openai_api_key: "" # OpenAI API 密钥
    model: "gpt-3.5-turbo"
    max_tokens: 2000
    temperature: 0.7

  sign_in:
    enabled: true
    rewards:
      min: 10  # 最小积分
      max: 50  # 最大积分
```

## 开发说明

项目结构：
```
BettQQBot/
├── main.py           # 主程序入口
├── config.yaml       # 配置文件
├── requirements.txt  # 项目依赖
├── src/
│   ├── bot.py       # 机器人核心
│   ├── api.py       # NapCat API 封装
│   ├── handlers.py  # 消息处理器
│   ├── plugins/     # 插件目录
│   │   ├── __init__.py
│   │   ├── basic.py
│   │   ├── chat.py
│   │   └── sign_in.py
│   └── utils/       # 工具函数
│       └── config.py
└── data/            # 数据存储目录
    └── sign_in.db   # 签到数据库
```

## 许可证

MIT License 