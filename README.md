# PROJ.Amrita 🌸 - 基于 NoneBot 的 LLM 聊天机器人框架

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-GPL--3.0-orange" alt="License">
  <img src="https://img.shields.io/badge/NoneBot-2.0+-red?logo=nonebot" alt="NoneBot">
</p>

Amrita 是一个基于[NoneBot2](https://nonebot.dev/)的强大聊天机器人框架，专为快速构建和部署智能聊天机器人而设计。它不仅是一个 CLI 工具，更是一个完整的 LLM 聊天机器人解决方案，支持多种大语言模型和适配器。

## 🌟 特性亮点

- **多模型支持**: 支持 OpenAI、DeepSeek、Gemini 等多种大语言模型
- **多模态能力**: 支持处理图像等多媒体内容
- **灵活适配**: 原生支持 Onebot-V11 协议，轻松对接 QQ 等平台
- **智能会话管理**: 内置会话控制和历史记录管理
- **插件化架构**: 模块化设计，易于扩展和定制
- **开箱即用**: 预设丰富的回复模板和功能配置
- **强大 CLI 工具**: 一体化命令行管理工具，简化开发和部署流程

## 🚀 快速开始

### 安装

```bash
# 使用pip安装
pip install amrita

# 或者使用uv安装（推荐）
uv pip install amrita
```

### 创建项目

```bash
# 创建新项目
amrita create mybot

# 进入项目目录
cd mybot

# 启动机器人
amrita run
```

### 初始化现有项目

```bash
# 在当前目录初始化项目
amrita init

# 启动机器人
amrita run
```

## 🧠 核心功能

### LLM 聊天插件

Amrita 内置了 SuggarChat 插件，基于 SuggarChat 的 LLM 模型，提供智能聊天功能。详见 SuggarChat 的[文档](https://docs.suggar.top/project/suggarchat/)。

## 📦 依赖管理

Amrita 使用`uv`进行依赖管理，提供两种安装模式：

```bash
# 基础安装(包含CLI)
pip install amrita

# 完整安装（包含完整的运行依赖）
pip install amrita[full]
```

## 🛠️ CLI 命令

| 命令                        | 描述                 |
| --------------------------- | -------------------- |
| `amrita create`             | 创建新项目           |
| `amrita init`               | 初始化当前目录为项目 |
| `amrita run`                | 运行项目             |
| `amrita version`            | 查看版本信息         |
| `amrita check-dependencies` | 检查依赖             |
| `amrita proj-info`          | 显示项目信息         |
| `amrita nb`                 | 直接运行 nb-cli 命令 |
| `amrita entry`             | 生成入口文件 |

## 🧩 插件系统

**Amrita** 插件系统基于 NoneBot2 的插件系统，允许用户扩展 Amrita 的功能，内置了一些常用插件，如 LitePerm权限管理插件，以及 AMenu 菜单插件（~~这个还没写~~）。

## ⚙️ 配置文件

通常来说，配置文件位于项目根目录下的 `config` 文件夹中，此外您仍需要配置DOTENV文件，用于配置环境变量(位于机器人目录的`.env`)。

以下是`Amrita`的独有配置项

```dotenv
LOG_DIR=logs # 日志目录
ADMIN_GROUP=1233456789 # 管理员群组ID，必配，推送Bot错误日志及其他信息
DISABLED_BUILTIN_PLUGINS=[] # 禁用的内置插件 注意：如果其他插件有依赖此插件，那么它仍然会被加载。
AMRITA_LOG_LEVEL=WARNING # 记录到文件的日志等级
BOT_NAME=Amrita # 为你的机器人名称
RATE_LIMIT=5 # 聊天频率限制(秒)
```

## 📚 文档和资源

- [官方文档](https://amrita.suggar.top)
- [GitHub 仓库](https://github.com/LiteSuggarDEV/Amrita)
- [问题反馈](https://github.com/LiteSuggarDEV/Amrita/issues)
- [Chat功能文档](https://docs.suggar.top/project/suggarchat/)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进 Amrita！

## 📄 许可证

本项目采用 GPL-3.0 许可证，详见[LICENSE](LICENSE)文件。
