import os
import re
import json
import pytz
import time
import requests
from typing import List, Tuple
from datetime import datetime, timedelta
from playwright.sync_api import Playwright, sync_playwright, expect, TimeoutError

# 定义账户凭证类型
AccountCredentials = List[Tuple[str, str]]
def parse_accounts(accounts_str: str) -> AccountCredentials:
    # 从账户字符串中解析账户凭证。 "邮箱1,密码1 邮箱2,密码2"
    accounts: AccountCredentials = []

    # 账户之间用空格分隔
    account_pairs = [pair.strip() for pair in accounts_str.split(' ') if pair.strip()]

    for pair in account_pairs:
        # 邮箱和密码之间用逗号分隔
        parts = [part.strip() for part in pair.split(',') if part.strip()]

        if len(parts) == 2:
            accounts.append((parts[0], parts[1]))
        else:
            print(f"⚠️ 警告：跳过格式错误的账户对 '{pair}'。请使用 '邮箱,密码' 格式。")
    return accounts

def run(playwright: Playwright) -> None:
    # --- 环境变量配置 ---
    # ---------------------------------------------------------------------------------
    # 用户可编辑区域：在这里直接填写您的 Leaflow 多账户 (格式: "邮箱1,密码1 邮箱2,密码2")
    # 如果设置了 LEAFLOW_ACCOUNTS 环境变量，它将覆盖此处的默认值。
    # ---------------------------------------------------------------------------------
    # 示例: "test1@example.com,pass1 test2@example.com,pass2"
    DEFAULT_LEAFLOW_ACCOUNTS_STR = ""

    # 获取账户源字符串：优先从环境变量 'LEAFLOW_ACCOUNTS' 获取，否则使用默认字符串。
    accounts_source_str = os.environ.get('LEAFLOW_ACCOUNTS', DEFAULT_LEAFLOW_ACCOUNTS_STR)
    # Leaflow 多账户配置
    LEAFLOW_ACCOUNTS = parse_accounts(accounts_source_str)

    # Weirdhost 单账户配置
    WEIRDHOST_EMAIL = os.environ.get('WEIRDHOST_EMAIL', '')
    WEIRDHOST_PASSWORD = os.environ.get('WEIRDHOST_PASSWORD', '')
    WEIRDHOST_LOGIN_URL = os.environ.get('WEIRDHOST_LOGIN_URL', '')
    WEIRDHOST_COOKIE_FILE = os.environ.get('WEIRDHOST_COOKIE_FILE', '')
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE', '')

    # Telegram Bot 通知配置（可选）
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    # 启用无头模式
    browser = playwright.chromium.launch(headless=True)

    # 推送telegram消息
    def send_telegram_message(message):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("Telegram bot token or chat ID not configured. Skipping Telegram notification.")
            return False

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print("Telegram notification sent successfully.")
            return True
        except Exception as e:
            print(f"Failed to send Telegram notification: {e}")
            return False

    # 保存cookies到指定文件。
    def save_cookies(context, file_path: str):
      cookies = context.cookies()
      try:
          with open(file_path, 'w', encoding='utf-8') as f:
              json.dump(cookies, f, indent=4)
          print(f"✅ Cookies 已成功保存到 '{file_path}'")
      except Exception as e:
          print(f"❌ 错误：保存 cookies 文件时发生未知错误：{e}")

    # 从文件加载 cookies
    def load_cookies_from_file(file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                if isinstance(cookies, list):
                    print(f"✅ 已从文件 '{file_path}' 成功加载 {len(cookies)} 个 cookies。")
                    return cookies
                else:
                    print(f"❌ 错误：文件 '{file_path}' 内容格式不正确，期望是一个列表。")
                    return None
        except FileNotFoundError:
            print(f"⚠️ 警告：文件 '{file_path}' 不存在，将返回 None。")
            return None
        except json.JSONDecodeError:
            print(f"❌ 错误：文件 '{file_path}' JSON 格式错误，无法解析。")
            return None
        except Exception as e:
            print(f"❌ 错误：加载文件 '{file_path}' 时发生未知错误：{e}")
            return None

    # 尝试使用指定的 cookies 登录并返回是否成功
    def try_cookie_login(
        context,
        page,
        cookies_to_add: list,
        VERIFY_URL: str,
        # 登录成功标志 - 至少提供一个
        SUCCESS_SELECTOR: str = None,           # CSS 或 XPath 字符串 (例如 "a[href*='logout']")
        SUCCESS_ROLE_NAME: str = None,          # Playwright 角色名 (例如 "登出")
        LOGIN_URL_PATTERN: str = None           # 辅助判断：登录页 URL 包含的模式 (例如 "login.php")
    ) -> bool:
        if not cookies_to_add or (SUCCESS_SELECTOR is None and SUCCESS_ROLE_NAME is None):
            print("⚠️ 未提供 cookies 或成功判断标志。")
            return False

        try:
            if cookies_to_add:
              # 1. 设置 Cookie
              context.add_cookies(cookies_to_add)
              print("🍪 Cookies 已添加到浏览器上下文。")

            # 2. 访问验证页面
            # page.goto(VERIFY_URL, wait_until='domcontentloaded')
            page.goto(VERIFY_URL, wait_until='networkidle')
            print(f"尝试访问验证 URL: {VERIFY_URL}")

            # 3. 确定用于判断成功的 Locator
            locator_success = None
            if SUCCESS_ROLE_NAME:
                # 优先使用最精确的 get_by_role
                locator_success = page.get_by_role("link", name=SUCCESS_ROLE_NAME)
            elif SUCCESS_SELECTOR:
                # 否则使用 CSS/XPath
                locator_success = page.locator(SUCCESS_SELECTOR)

            # 4. 精确判断：检查登录成功的标志元素
            # 使用 is_visible() 只检查第一个匹配项是否可见
            if locator_success and locator_success.first.is_visible():
                print(f"✅ Cookie 登录成功! 找到了登际成功标志。")
                return True
            else:
                # 5. 辅助判断：检查是否被强制重定向回登录页 (可选)
                if LOGIN_URL_PATTERN and LOGIN_URL_PATTERN in page.url:
                    print(f"❌ Cookie 登录失败，页面被重定向回登录页。匹配模式: {LOGIN_URL_PATTERN}")
                else:
                    print(f"❌ Cookie 登录失败，未在 {page.url} 上找到登录成功标志。")

                page.screenshot(path="cookie_login_fail_screenshot.png")
                return False
        except Exception as e:
            print(f"⚠️ Cookie 登录尝试时发生错误：{e}")
            return False

    # --- LEAFLOW 多账户执行步骤 ---
    if LEAFLOW_ACCOUNTS:
        print(f"\n--- 开始执行 Leaflow 多账户签到任务 ({len(LEAFLOW_ACCOUNTS)} 个账户) ---")

        for index, (email, password) in enumerate(LEAFLOW_ACCOUNTS):
            # 为每个账户创建新的、隔离的浏览器上下文和页面
            context = browser.new_context()
            page = context.new_page()
            email_id = email.split('@')[0]
            print(f"\n[Leaflow - {email_id}] 账号 #{index + 1} ({email}) 开始执行...")

            try:
                print(f"[{email_id}] 🚀 导航至 leaflow.net...")
                page.goto(
                    "https://leaflow.net/",
                    timeout=60000,
                    wait_until="domcontentloaded"
                )

                page.get_by_role("button", name="登录", exact=True).click()
                page.get_by_role("textbox", name="邮箱或手机号").fill(email)
                page.get_by_role("textbox", name="密码").fill(password)

                page.get_by_role("button", name="登录 / 注册").click()

                page.wait_for_selector('text="工作区"', timeout=20000)
                print(f"[{email_id}] 已完成登录尝试。")

                page.get_by_role("link", name="工作区").click()
                page.get_by_text("签到试用").click()
                print(f"[{email_id}] 已进入签到页面...")

                try:
                    page.locator("#app iframe").content_frame.get_by_role("button", name=" 立即签到").click()
                    print(f"✅ 任务执行成功: [{email_id}] 签到操作已完成。")
                    content = f"🆔LEAFLOW帐号: {email_id}\n"
                    content += f"🚀签到状态: 签到操作已完成\n"
                    telegram_message = f"**LEAFLOW签到信息**\n{content}"
                    send_telegram_message(telegram_message)
                except Exception as e:
                    print(f"✅ [{email_id}] 今日已经签到！")
                    content = f"🆔LEAFLOW帐号: {email_id}\n"
                    content += f"🚀签到状态: 今日已经签到！\n"
                    telegram_message = f"**LEAFLOW签到信息**\n{content}"
                    send_telegram_message(telegram_message)

            except TimeoutError as te:
                print(f"❌ 任务执行失败：Playwright (操作超时：{te})")
                page.screenshot(path="leaflow_error_screenshot.png")
                content = f"🆔LEAFLOW帐号: {email_id}\n"
                content += f"🚀签到状态: 任务执行失败：Playwright 操作超时\n"
                telegram_message = f"**LEAFLOW签到信息**\n{content}"
                send_telegram_message(telegram_message)
            except Exception as e:
                print("❌ 任务执行失败：详细错误信息: {e}")
                page.screenshot(path="leaflow_final_error_screenshot.png") # 失败时强制截图
                content = f"🆔LEAFLOW帐号: {email_id}\n"
                content += f"🚀签到状态: 任务执行失败 (未知错误: {e})\n"
                telegram_message = f"**LEAFLOW签到信息**\n{content}"
                send_telegram_message(telegram_message)
            finally:
                # 隔离清理：关闭当前账户的页面和上下文
                page.close()
                context.close()
                time.sleep(10) # 账户间延迟，确保资源释放

        time.sleep(30) # 两个主要任务之间的延迟
    else:
         print("\n--- ℹ️ 跳过 Leaflow 任务：未配置 LEAFLOW_ACCOUNTS。 ---")
         time.sleep(5) # 保持延迟

    # --- WEIRDHOST 单账户执行步骤 (保持原样，并增加隔离) ---
    weirdhost_is_logged_in = False
    if WEIRDHOST_EMAIL or remember_web_cookie or os.path.exists(WEIRDHOST_COOKIE_FILE):
        print(f"\n--- 开始执行weirdhost继期任务...")
        context = browser.new_context() # 新的上下文
        page = context.new_page()       # 新的页面

        try:
            # --- 方案一：优先尝试使用 Cookie 会话登录 ---
            if os.path.exists(WEIRDHOST_COOKIE_FILE):
              loaded_cookies = load_cookies_from_file(WEIRDHOST_COOKIE_FILE)
              if loaded_cookies:
                  weirdhost_is_logged_in = try_cookie_login(
                      context,
                      page,
                      loaded_cookies,
                      WEIRDHOST_LOGIN_URL,
                      SUCCESS_ROLE_NAME="콘솔"
                  )

            if not weirdhost_is_logged_in and remember_web_cookie:
                print("检测到 REMEMBER_WEB_COOKIE，尝试使用单一 Cookie 登录...")
                context.clear_cookies()

                session_cookie = [
                    {
                        'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                        'value': remember_web_cookie,
                        'domain': 'hub.weirdhost.xyz',
                        'path': '/',
                        'expires': int(time.time()) + 3600 * 24 * 365,
                        'httpOnly': True,
                        'secure': True,
                        'sameSite': 'Lax'
                    }
                ]
                weirdhost_is_logged_in = try_cookie_login(
                    context,
                    page,
                    session_cookie,
                    WEIRDHOST_LOGIN_URL,
                    SUCCESS_ROLE_NAME="콘솔"
                )
                # if weirdhost_is_logged_in: save_cookies(context, WEIRDHOST_COOKIE_FILE)

            # --- 方案二：如果 Cookie 方案失败或未提供，则使用邮箱密码登录 ---
            if not weirdhost_is_logged_in and WEIRDHOST_EMAIL and WEIRDHOST_PASSWORD:
                print("❌ Cookie 无效或不存在，使用 EMAIL/PASSWORD 开始执行登录任务...")
                print(f"🚀 导航至 https://hub.weirdhost.xyz/auth/login ...")
                page.goto(
                    "https://hub.weirdhost.xyz/auth/login",
                    timeout=60000,
                    wait_until="domcontentloaded"
                )

                page.locator("input[name=\"username\"]").fill(WEIRDHOST_EMAIL)
                page.locator("input[name=\"password\"]").fill(WEIRDHOST_PASSWORD)
                try:
                    page.get_by_role("checkbox", name="만14").check(timeout=5000)
                except TimeoutError:
                    pass

                page.get_by_role("button", name="로그인", exact=True).click()
                page.wait_for_url("https://hub.weirdhost.xyz/")
                print("用户名密码登录成功。")
                weirdhost_is_logged_in = True
                save_cookies(context)

                page.get_by_role("link", name="Discord's Bot Server").click()
                page.wait_for_url(WEIRDHOST_LOGIN_URL, timeout=15000)
                print("已进入继期页面...")

            # --- 继期操作 ---
            content = f"🆔WEIRDHOST帐号: {WEIRDHOST_EMAIL}\n"
            if weirdhost_is_logged_in:
                KST = pytz.timezone('Asia/Seoul')
                # 从页面查找过期日期
                def get_expiration_date():
                    try:
                        date_locator = page.get_by_text(re.compile(r"유통기한\s\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:"))
                        # text_content() 使用 Playwright 的默认操作超时，通常是 30 秒 (30000ms)。
                        full_text = date_locator.text_content(timeout=20000)
                        print(f"定位到的元素内容: {full_text}")
                        match = re.search(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})", full_text)
                        if not match:
                            print("❌ 未能在定位到的文本中找到有效日期字符串。")
                            return None

                        expiration_str = match.group(1)
                        print(f"找到到期日期字符串: {expiration_str}")

                        naive_dt = datetime.strptime(expiration_str, "%Y-%m-%d %H:%M")
                        return KST.localize(naive_dt)
                    except Exception as e:
                        print(f"查找过期时间时发生错误: {e}")
                        return None

                # 1. 获取过期时间
                expiration_dt = get_expiration_date()
                # 2. 获取当前时间
                now_kst = datetime.now(KST)
                if expiration_dt:
                    print(f"Now KST time: {now_kst.strftime('%Y-%m-%d %H:%M')}")
                    # 3. 缓冲时间，提前一天  days hours minutes seconds
                    buffer_time = timedelta(days=1)
                    # 4. 逻辑判断
                    if expiration_dt > now_kst + buffer_time:
                        print("✅ 未到24小时继期窗口，不执行操作")
                        content += f"⏰服务器过期时间：{expiration_dt.strftime('%Y-%m-%d %H:%M')}\n"
                        content += f"🚀续期状态: 未到24小时继期窗口，不执行操作\n"
                    else:
                        # 执行继期操作
                        try:
                            page.get_by_role("button", name="시간추가").click()
                            print("✅ 已经进入24小时继期窗口，成功完成继期。")

                            print("⏳ 等待 10 秒，以确保服务器过期时间数据已更新...")
                            time.sleep(10)

                            CST = pytz.timezone('Asia/Shanghai')
                            current_time = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
                            next_expiration_dt = get_expiration_date()

                            content += f"⏰运行继期脚本时间: {current_time}\n"
                            content += f"🚀续期状态: 成功\n"
                            content += f"⏰服务器下次过期时间: {next_expiration_dt.strftime('%Y-%m-%d %H:%M')}\n"
                        except Exception as e:
                            print(f"❌ 继期操作失败：点击 '시간추가' 按钮时发生错误: {e}")
                            content += f"❌续期状态: 继期操作失败：点击 '시간추가' 按钮时发生错误\n"
                else:
                    print("❌ 未能在页面上找到有效的过期时间，无法执行续期判断。")
                    content += f"❌续期状态: 未能在页面上找到有效的过期时间，无法执行续期判断\n"
            else:
                print("❌ 无法登录（Cookie 已失效或EMAIL/PASSWORD登陆失败），任务终止。")
                content += f"❌续期状态: 无法登录（Cookie已失效或EMAIL/PASSWORD登陆失败）\n"
            telegram_message = f"**Weirdhost继期信息**\n{content}"
            send_telegram_message(telegram_message)
        except TimeoutError as te:
            print(f"❌ 任务执行失败：Playwright 操作超时 ({te})")
            page.screenshot(path="weirdhost_error_screenshot.png")
        except Exception as e:
            print("❌ 任务执行失败！")
            page.screenshot(path="weirdhost_final_error_screenshot.png")
            print(f"详细错误信息: {e}")

        finally:
            page.close()
            context.close()
    else:
        print("\n--- ℹ️ 跳过 Weirdhost 任务：未配置 WEIRDHOST_EMAIL/PASSWORD 或 remember_web_cookie。 ---")


    # ---------------------
    browser.close()
    print("\n--- 所有任务执行完毕 ---")


if __name__ == '__main__':
    with sync_playwright() as playwright:
        run(playwright)
