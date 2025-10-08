# Leaflow 自动签到脚本

![Python](https://img.shields.io/badge/Python-3.7%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

Leaflow 多账号自动签到脚本，支持 Telegram 通知和 GitHub Actions 自动化运行。

## 功能特性

- ✅ 支持多个 Leaflow 账号自动签到
- 🤖 基于 Selenium 实现自动化操作
- 📱 自动处理网站弹窗和验证码
- 📢 支持 Telegram 通知推送
- ⏰ 支持 GitHub Actions 定时自动执行
- 🔄 智能重试机制，提高签到成功率
- 📊 详细的日志记录和错误处理

## 使用方法

#### 配置账号信息

脚本支持三种方式配置账号信息：

##### 方式一：单个账号（向后兼容）
```bash
LEAFLOW_EMAIL    your_email@example.com
LEAFLOW_PASSWORD    your_password
```

##### 方式二：多个账号（分隔符方式，向后兼容）
```bash
LEAFLOW_EMAILS    email1@example.com,email2@example.com

LEAFLOW_PASSWORDS    password1,password2 
```

##### 方式三：多个账号（推荐 JSON 格式）
```bash
LEAFLOW_ACCOUNTS

[{
		"email": "email1@example.com",
		"password": "password1"
	},
	{
		"email": "email2@example.com",
		"password": "password2"
	}
......添加更多账号
]
```


### 2. GitHub Actions 自动运行

1. Fork 本仓库
2. 在仓库 Settings > Secrets and variables > Actions 中添加以下 secrets：
   - `LEAFLOW_ACCOUNTS`: 账号信息（JSON 格式）
   - `TELEGRAM_BOT_TOKEN`（可选）: Telegram Bot Token
   - `TELEGRAM_CHAT_ID`（可选）: Telegram Chat ID

3. 启用 GitHub Actions 工作流

### 3. Telegram 通知配置

要启用 Telegram 通知，请设置以下环境变量：

```bash
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
```

## 配置说明

| 环境变量 | 必需 | 说明 |
|---------|------|------|
| `LEAFLOW_EMAIL` | 否* | 单个账号邮箱（方式一） |
| `LEAFLOW_PASSWORD` | 否* | 单个账号密码（方式一） |
| `LEAFLOW_EMAILS` | 否* | 多个账号邮箱，逗号分隔（方式二） |
| `LEAFLOW_PASSWORDS` | 否* | 多个账号密码，逗号分隔（方式二） |
| `LEAFLOW_ACCOUNTS` | 否* | 多个账号信息 JSON 字符串（方式三，推荐） |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 否 | Telegram Chat ID |

*注：以上账号配置方式至少需要配置一种

## 工作原理

1. 脚本启动后会根据环境变量配置加载账号信息
2. 对每个账号依次执行：
   - 打开 Leaflow 登录页面
   - 自动处理可能出现的弹窗
   - 输入邮箱和密码进行登录
   - 跳转到签到页面
   - 查找并点击"立即签到"按钮
   - 获取签到结果
3. 所有账号处理完成后，如果配置了 Telegram 信息，则发送汇总通知

## 注意事项

- 请确保账号信息正确无误
- 脚本会在账号间间隔 10 秒钟，避免请求过于频繁
- 在 GitHub Actions 中运行时，脚本会自动使用无头模式（headless mode）
- 请遵守网站的使用条款，合理使用自动化脚本

## 许可证


本项目采用 MIT 许可证，详情请见 [LICENSE](LICENSE) 文件。


