# CivitAI 模型自动上传工具

[English Version](README_en.md)

## 📋 项目简介

这是一个用于自动上传模型文件到 **CivitAI** 平台的 Python 脚本。它提供了完整的上传流程自动化，包括握手认证、分块上传、并发处理和数据库同步，帮助用户快速上传大型模型文件。

## ✨ 核心特性

- 🔐 **安全认证**：支持 Cookie 令牌和 CSRF 令牌验证
- 📦 **智能分块**：自动将大文件分割成多个分块
- ⚡ **并发上传**：使用 4 线程并发上传分块，大幅提升速度
- 🔄 **自动重试**：失败分块智能重试（最多 5 次，指数退避）
- 🛣️ **路由管理**：自动获取和管理 CivitAI 服务器分配的专属路由
- 📊 **进度监控**：实时显示上传进度条
- 🔗 **数据库同步**：完成上传后自动同步到 CivitAI 数据库

## 🚀 快速开始

### 1. 环境要求

```bash
Python 3.7+
```

### 2. 安装依赖

```bash
pip install requests tqdm
```

### 3. 获取认证信息

你需要从 CivitAI 网站获取以下信息：

1. **CIVITAI_TOKEN**：你的 CivitAI 认证令牌
   - 打开 [civitai.com](https://civitai.com)
   - 登录你的账户
   - 打开浏览器开发者工具（F12）
   - 前往 `Storage` → `Cookies` → `civitai.com`
   - 找到 `__Secure-civitai-token` 的值

2. **CSRF_TOKEN**：跨站请求伪造防护令牌
   - 在同一个 Cookies 页面找到 `__Host-next-auth.csrf-token` 的值

3. **VERSION_ID**：模型版本 ID
   - 在你的模型页面 URL 中找到 `modelVersionId` 参数，或
   - 从模型编辑页面获取

### 4. 配置脚本

编辑 `auto_put.py` 文件，填入你的认证信息和文件路径：

```python
# 配置部分
CIVITAI_TOKEN = "YOUR_CIVITAI_TOKEN_HERE"
CSRF_TOKEN = "YOUR_CSRF_TOKEN_HERE"
VERSION_ID = "YOUR_MODEL_VERSION_ID_HERE"
FILE_PATH = "YOUR_FILE_PATH"  # 例如: "D:\\models\\my_model.safetensors"
```

### 5. 运行脚本

```bash
python auto_put.py
```

## 📖 工作原理

### 第 0 步：握手准备
- 访问模型页面获取服务器分配的专属路由（civitai-route）
- 这个"房间号"对后续上传操作至关重要

### 第 1 步：初始化上传
- 向 CivitAI API 发送文件信息（文件名、大小、类型等）
- 服务器返回上传 ID、密钥和 S3 分块上传地址列表

### 第 2 步：并发分块上传
- 将文件分割成多个块（块数由 S3 返回的 URL 数量决定）
- 使用 4 个线程并发上载，每个分块失败时自动重试
- 收集每个分块的 ETag 用于合并验证

### 第 3 步：物理合并
- 调用 `/api/upload/complete` 接口在服务器端合并所有分块
- 服务器验证 ETag 完整性

### 第 4 步：数据库同步
- 调用 `/api/trpc/modelFile.create` 将上传信息同步到 CivitAI 数据库
- 完成后模型即可在网页端查看

## ⚙️ 高级配置

### 硬编码 UUID（可选）

如果步骤 B（数据库同步）返回 500 或 UNAUTHORIZED 错误，可以手动指定 UUID：

```python
HARDCODED_UUID = "f5ebae8f-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # 从抓包工具中获取
```

不设置时，脚本会自动从初始化响应中使用 `uuid` 或 `uploadId`。

## 🔧 常见问题

### Q: 如何解决 "500 Internal Server Error" 错误？

**A:** 这通常是路由问题。尝试：
- 确认 `civitai-route` 已正确设置在 Cookies 中
- 重启脚本重新获取路由
- 检查 Cookie 是否过期

### Q: 上传因网络问题中断怎么办？

**A:** 脚本具有自动重试机制，每个分块最多重试 5 次。如果全部失败，请：
- 检查网络连接
- 重新运行脚本（会从头开始）

### Q: 如何提高上传速度？

**A:** 你可以修改脚本中的线程数量：

```python
with ThreadPoolExecutor(max_workers=8) as executor:  # 改为 8 个线程
```

但要注意不要超过服务器限制。

### Q: 上传的文件格式有限制吗？

**A:** 根据代码，支持的类型包括：
- `Model`（模型文件，如 `.safetensors`、`.ckpt`）
- 支持元数据设置：格式、精度、大小等

## 🛡️ 安全说明

- 🚨 **不要分享你的 Token 和 CSRF Token**
- 保管好你的配置文件，建议在 `.gitignore` 中排除包含敏感信息的版本
- 考虑使用环境变量替代硬编码配置

## 🐛 调试技巧

如果遇到问题，脚本会打印详细的日志信息：

```
📡 正在从服务器获取分配的专属路由...
✅ 握手完成！分配的专属路由: xxx-xxx-xxx
🚀 开始上传文件 (4线程 + 自动重试)...
[进度条显示]
✅ 物理文件合并成功！
...
```

查看这些日志可以帮助定位问题。

## 📝 许可证

此项目仅供学习和个人使用。使用前请阅读 CivitAI 的服务条款和使用政策。

## 💬 反馈

如有问题或建议，欢迎提出！

---

*最后更新: 2026.02.07*
