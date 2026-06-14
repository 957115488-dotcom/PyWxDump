# PyWxDump 微信解密导出模块

## 概述

本模块为 DustMirror（观尘）提供微信聊天记录导入功能。由于合规要求，本模块**不内置任何特定应用的解密逻辑**，而是通过合规确认流程后，从 GitHub 社区（如 [PyWxDump](https://github.com/xaoyaoo/PyWxDump) 等仓库）临时下载开源提取脚本并在本地沙盒中运行。

## 合规流程

1. 用户点击"导入微信记录"按钮
2. 弹出合规确认对话框，显示合规文案
3. **强制等待 3 秒**后才可点击确认按钮
4. 用户确认同意后，记录合规确认日志
5. 开始下载和运行社区脚本

## 架构

```
pywxdump/
├── __init__.py      # 模块入口
├── api.py           # FastAPI 路由（/api/pywxdump/*）
├── compliance.py    # 合规确认流程管理
├── downloader.py    # 社区脚本下载器（GitHub + SHA256 校验）
├── sandbox.py       # 沙盒运行器（隔离执行）
└── README.md        # 本文档
```

## 沙盒隔离

| 级别 | 说明 |
|------|------|
| BASIC（默认） | 限制文件系统访问到临时目录，300秒超时 |
| STRICT | 在 BASIC 基础上额外限制网络访问 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/pywxdump/compliance-text` | 获取合规文案 |
| POST | `/api/pywxdump/confirm` | 提交合规确认（3秒等待） |
| POST | `/api/pywxdump/run` | 下载并运行社区脚本 |
| GET | `/api/pywxdump/status` | 查询运行状态 |

## 安全说明

- 所有脚本在沙盒中运行，异常不影响主进程
- 下载的脚本经过 SHA256 完整性校验
- 合规确认日志完整记录（时间、IP、UA）
- 临时文件运行后自动清理