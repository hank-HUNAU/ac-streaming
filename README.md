# Academic Listening - 学术听力

10 篇葡萄多酚英文综述论文的逐句朗读与术语学习 Web App。

**在线访问**：https://hank-HUNAU.github.io/ac-streaming/app.html

## 功能

| 模块 | 说明 |
|------|------|
| 听篇章 | 逐句播放，词级高亮，4 档变速，逐句循环 |
| 听词汇 | 学术关键词朗读，英文术语 + 中文译名 |
| 术语库 | 全 10 篇去重术语，中英文实时搜索 |
| 收藏夹 | 句子 & 术语收藏，导出 TXT |
| PWA | 添加到手机桌面，独立窗口运行 |

## 技术栈

- **TTS**: Microsoft Edge-TTS (AriaNeural en-US)
- **前端**: 纯 HTML/CSS/JS 单文件（1088 行，65 函数），无外部 UI 框架
- **数据**: 句级 JSON + 词级时间对齐 JSON
- **部署**: GitHub Pages，相对路径

## 音频覆盖

10 篇论文，160 个 Section，3,097 句，总时长 553 分钟（9.2 小时）。
3,131 个术语中 2,278 个含 MP3 音频可播放。

## 添加至手机桌面

1. Safari (iOS): 分享 → 添加到主屏幕
2. Chrome (Android): 菜单 → 添加到主屏幕

## 项目结构

```
├── app.html                  # 主应用 (单文件 SPA)
├── manifest.json             # PWA Manifest
├── sw.js                     # Service Worker (离线缓存)
├── icon.svg                  # App 图标
├── data/
│   ├── papers.json           # 论文索引
│   ├── glossary.json         # 全局术语库 (1711 条)
│   └── ch01/ ~ ch10/         # 各章数据 (summary + sections + entities)
├── chpt01_audio/ ~ chpt10_audio/
│   ├── {section_id}.mp3      # 篇章音频
│   └── term_audio/           # 术语音频
└── pipeline.py               # TTS 批处理流水线
```
