import os
import re
import json
import pytz
import time
from datetime import datetime, timedelta
from playwright.sync_api import Playwright, sync_playwright, expect, TimeoutError

def run(playwright: Playwright) -> None:
    # 环境变量
    LEAFLOW_EMAIL = os.environ.get('LEAFLOW_EMAIL', '')
    LEAFLOW_PASSWORD = os.environ.get('LEAFLOW_PASSWORD', '')

    WEIRDHOST_EMAIL = os.environ.get('WEIRDHOST_EMAIL', '')
    WEIRDHOST_PASSWORD = os.environ.get('WEIRDHOST_PASSWORD', '')
    LOGIN_URL = os.environ.get('LOGIN_URL', '')
    COOKIE_FILE = os.environ.get('COOKIE_FILE', 'cookies.json')
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE', '')

    # 启用无头模式 (在 CI/CD 中推荐)
    # 将 headless=False 改为 True 为无头模式
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    # 用于追踪登录状态
    is_logged_in = False

    # 保存为cookies.json
    def save_cookies(context):
        cookies = context.cookies()
        with open(COOKIE_FILE, 'w') as f:
            json.dump(cookies, f)
        print(f"Cookies已保存到{COOKIE_FILE}")

    # 从文件加载cookies
    def load_cookies_from_file(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                print(f"✅ 已从文件 '{file_path}' 成功加载 {len(cookies)} 个 cookies。")
                return cookies
        except Exception as e:
            print(f"❌ 错误：加载 cookies 时发生未知错误：{e}")
            return None

    # 尝试使用指定的 cookies 登录并返回是否成功
    def try_cookie_login(context, page, cookies_to_add: list, login_url: str) -> bool:
        if not cookies_to_add:
            return False

        try:
            context.add_cookies(cookies_to_add)
            print("🍪 Cookies 已添加到浏览器上下文，尝试访问目标 URL。")

            # 访问目标 URL，测试是否成功保持登录状态
            page.goto(login_url, wait_until='domcontentloaded')

            # 验证是否成功登录 (假设登录页面包含 "auth/login")
            if "auth/login" not in page.url:
                print("✅ Cookie 登录成功，已进入继期页面。")
                return True
            else:
                print("❌ Cookie 登录失败，可能已过期。")
                return False

        except Exception as e:
            print(f"⚠️ Cookie 登录尝试时发生错误：{e}")
            return False

    # --- leaflow执行步骤 ---
    try:
        print("开始执行leaflow签到任务...")
        page.goto("https://leaflow.net/")

        page.get_by_role("button", name="Close").click()
        page.get_by_role("button", name="登录", exact=True).click()
        page.get_by_role("textbox", name="邮箱或手机号").fill(LEAFLOW_EMAIL)
        page.get_by_role("textbox", name="密码").fill(LEAFLOW_PASSWORD)

        page.get_by_role("button", name="登录 / 注册").click()
        print("已完成登录尝试...")

        page.get_by_role("link", name="工作区").click()
        page.get_by_text("签到试用").click()
        print("已进入签到页面...")

        try:
            page.locator("#app iframe").content_frame.get_by_role("button", name=" 立即签到").click()
            print("✅ 任务执行成功: 签到操作已完成。")
        except Exception as e:
            print("✅ 今日已经签到！")

    except TimeoutError as te:
        print(f"❌ 任务执行失败：Playwright 操作超时 ({te})")
        page.screenshot(path="error_screenshot.png") # 超时时截图
    except Exception as e:
        print("❌ 任务执行失败！")
        page.screenshot(path="final_error_screenshot.png") # 失败时强制截图
        print(f"详细错误信息: {e}")

    time.sleep(30)

    # --- weirdhost执行步骤 ---
    try:
        print("开始执行weirdhost继期任务...")
        # --- 方案一：优先尝试使用 Cookie 会话登录 ---
        loaded_cookies = load_cookies_from_file(COOKIE_FILE)
        if loaded_cookies:
            is_logged_in = try_cookie_login(context, page, loaded_cookies, LOGIN_URL)
        if not is_logged_in and remember_web_cookie:
            print("检测到 REMEMBER_WEB_COOKIE，尝试使用单一 Cookie 登录...")
            # 清理 context 以确保新的登录是干净的
            context.clear_cookies()
            # 构造单一Cookie列表 将cookie的过期时间延长至从当前时间起大约一年
            session_cookie = {
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': remember_web_cookie,
                'domain': 'hub.weirdhost.xyz',
                'path': '/',
                'expires': int(time.time()) + 3600 * 24 * 365,
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            }
            is_logged_in = try_cookie_login(context, page, [session_cookie], LOGIN_URL)
            # 登录成功后，保存新的填入cookies为文件(可选)
            # if is_logged_in:
            #     save_cookies(context)


        # --- 方案二：如果 Cookie 方案失败或未提供，则使用邮箱密码登录 ---
        if not is_logged_in and WEIRDHOST_EMAIL and WEIRDHOST_PASSWORD:
            print("❌ Cookie 无效或不存在，使用 EMAIL/PASSWORD 开始执行登录任务...")
            page.goto("https://hub.weirdhost.xyz/auth/login")

            # 执行登录步骤...
            page.locator("input[name=\"username\"]").fill(WEIRDHOST_EMAIL)
            page.locator("input[name=\"password\"]").fill(WEIRDHOST_PASSWORD)
            page.get_by_role("checkbox", name="만14").check()
            page.get_by_role("button", name="로그인", exact=True).click()

            # 等待登录成功后的页面加载
            page.wait_for_url("https://hub.weirdhost.xyz/")
            print("用户名密码登录成功。")
            is_logged_in = True

            # 登录成功后，保存新的 cookies
            save_cookies(context)

            # 导航到最终的目标继期页面
            page.get_by_role("link", name="Discord's Bot Server").click()
            page.wait_for_url(LOGIN_URL, timeout=15000) # 额外等待直到 URL 匹配
            print("已进入继期页面...")

        # --- 继期操作 ---
        if is_logged_in:
            # 确保当前在正确的页面
            # page.goto(LOGIN_URL, wait_until='domcontentloaded')

            # 后续的日期检查和点击操作
            date_locator = page.get_by_text(re.compile(r"유통기한\s\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:"))
            full_text = date_locator.text_content(timeout=20000) # 20秒
            print(f"定位到的元素内容: {full_text}")
            match = re.search(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})", full_text)
            if match:
                expiration_str = match.group(1)
                print(f"Found Expiration Date String: {expiration_str}")

                KST = pytz.timezone('Asia/Seoul')
                naive_dt = datetime.strptime(expiration_str, "%Y-%m-%d %H:%M")
                expiration_dt = KST.localize(naive_dt)
                now_kst = datetime.now(KST)
                print(f"Now KST time: {now_kst}")

                # 提前1天继期
                buffer_time = timedelta(days=1)   # seconds minutes hours
                if expiration_dt > now_kst + buffer_time:
                    print("✅ 未到24小时继期窗口，不执行操作")
                else:
                    page.get_by_role("button", name="시간추가").click()
                    print("✅ 已经进入24小时继期窗口，成功完成继期。")
            else:
                print("❌ 未能在页面上找到有效日期字符串。")
        else:
            print("❌ 无法登录（Cookie 已失效且未提供 EMAIL/PASSWORD），任务终止。")

    except TimeoutError as te:
        print(f"❌ 任务执行失败：Playwright 操作超时 ({te})")
        page.screenshot(path="error_screenshot.png") # 超时时截图
    except Exception as e:
        print("❌ 任务执行失败！")
        page.screenshot(path="final_error_screenshot.png") # 失败时强制截图
        print(f"详细错误信息: {e}")

    finally:
        # ---------------------
        context.close()
        browser.close()

if __name__ == '__main__':
    with sync_playwright() as playwright:
        run(playwright)
