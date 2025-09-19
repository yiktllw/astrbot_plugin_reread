
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_reread?name=astrbot_plugin_reread&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_reread

_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot) 复读插件 ✨_  

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

不依赖任何数据库的群聊复读姬，可单独设置文本、图片、表情、At消息的复读阈值，可设置复读概率，可要求消息要来自不同人，可设置违禁词

### ✨ 新功能：单条复读模式

现在支持两种复读模式：
- **阈值复读**：传统模式，多条相同消息达到阈值后触发复读
- **单条复读**：新增模式，收到消息后按概率直接复读，无需等待阈值

### 🐛 调试功能

新增调试模式，启用后可在控制台查看详细的运行日志：
- 消息处理流程追踪
- 概率计算详情
- 复读触发条件分析
- 错误排查信息

## 📦 安装

- 直接在astrbot的插件市场搜索astrbot_plugin_reread，点击安装，等待完成即可

- 也可以克隆源码到插件文件夹：

```bash
# 克隆仓库到插件目录
cd /AstrBot/data/plugins
git clone https://github.com/Zhalslar/astrbot_plugin_QQAdmin

# 控制台重启AstrBot
```

## ⌨️ 配置

请前往插件配置面板进行配置
![tmp8498](https://github.com/user-attachments/assets/11b1afa6-371f-4b66-a5cc-14a8b4b2037d)

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 注意复读阈值不要调太低，容易刷屏
- 单条复读概率建议设置较小的值（如0.05），避免过于频繁复读
- 冷却时间机制对两种复读模式都生效，可有效防止频繁复读
- 启用调试模式可以帮助排查问题，但会增加日志输出量
- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
