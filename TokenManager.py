import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


class TokenManager:
    def __init__(self, tokenfile='token.cfg', headless=False):
        self.chrome_options = Options()

        # 禁用自动化检测特征
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)

        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')

        # 可选：无头模式（调试时可设置为False）
        if headless:
            self.chrome_options.add_argument('--headless')

        # 设置用户代理，避免被检测为自动化工具
        self.chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        self.driver = None
        self.wait = None
        self.token_file = tokenfile

        if not os.path.isfile(tokenfile):
            with open(tokenfile, 'w') as f:
                f.write('')


    def get_token(self, sno):
        with open(self.token_file, 'r', encoding='utf-8') as f:
            t = f.readline().strip()

        if t != '':
            return t

        t = self.get_token_automatically(sno)
        if not t:
            return None

        with open(self.token_file, 'w', encoding='utf-8') as f:
            f.write(t)

        return t


    def setup_browser(self):
        """初始化浏览器"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 20)

            # 设置窗口大小和位置，确保验证码可见
            self.driver.set_window_size(1200, 800)
            self.driver.set_window_position(100, 100)  # 确保窗口在屏幕可见位置

            return True
        except Exception as e:
            print(f"浏览器初始化失败: {e}")
            return False

    def login_to_cas(self, sno):
        """登录CAS认证系统 - 用户手动输入版本"""
        print("正在打开CAS登录页面...")

        # 打开CAS登录页面
        login_url = "https://cas.bjtu.edu.cn/auth/login/?next=/o/authorize/%3Fresponse_type%3Dcode%26client_id%3DaGex8GLTLueDZ0nW2tD3DwXnSA3F9xeFimirvhfo%26state%3D1762836296%26redirect_uri%3Dhttps%3A//mis.bjtu.edu.cn/auth/callback/%3Fredirect_to%3D/home/"
        self.driver.get(login_url)

        # 等待页面加载
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        sno_input = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.ID, "id_loginname"))
        )
        sno_input.clear()
        sno_input.send_keys(sno)

        print("\n" + "=" * 70)
        print("请手动完成以下操作：")
        print("1. 在浏览器中输入密码")
        print("2. 输入验证码")
        print("3. 点击登录按钮")
        print("4. 等待页面跳转到MIS系统")
        print("=" * 70)

        try:
            # 记录当前URL（登录前）
            original_url = self.driver.current_url

            # 等待用户手动完成登录
            print("\n等待用户手动登录...")
            print("登录成功后程序会自动继续")

            # 轮询检查是否登录成功（页面跳转）
            max_wait_time = 120  # 最大等待时间2分钟
            check_interval = 1  # 每3秒检查一次

            for i in range(max_wait_time // check_interval):
                current_url = self.driver.current_url

                # 检查是否仍在登录页面（说明还未登录）
                if current_url == original_url:
                    print(f"\r等待登录... ({i * check_interval}秒)", end="", flush=True)
                    time.sleep(check_interval)
                else:
                    # 跳转到其他页面，可能是登录成功
                    # 等待页面加载
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    print(f"\n✓ 检测到页面跳转: {current_url}")
                    return True

            # 超时处理
            print("\n❌ 登录超时，请检查是否登录成功")
            return False

        except Exception as e:
            print(f"❌ 登录过程中出错: {e}")
            return False

    def navigate_to_token_page(self):
        """导航到包含token的页面"""
        print("正在导航到目标页面...")

        token_url = "https://mis.bjtu.edu.cn/module/module/96/"
        self.driver.get(token_url)

        # 使用混合等待策略
        time.sleep(5)  # 基础等待

        try:
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # 检查特定元素是否存在来确认页面加载成功
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//body"))
            )

            print("✓ 成功访问目标页面")
            return True

        except Exception as e:
            print(f"❌ 访问失败: {str(e)}")
            # 尝试重新加载
            try:
                self.driver.refresh()
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                print("✓ 重试后成功访问")
                return True
            except:
                print("❌ 重试也失败")
                return False

    def extract_token_from_storage(self):
        """从浏览器存储中提取token"""
        print("正在从浏览器存储中提取token...")

        try:
            # 首先尝试sessionStorage
            token = self.driver.execute_script("return sessionStorage.getItem('token');")
            if token:
                print("✓ 从sessionStorage获取到token")
                return token

            # 尝试localStorage
            token = self.driver.execute_script("return localStorage.getItem('token');")
            if token:
                print("✓ 从localStorage获取到token")
                return token

            # 尝试其他可能的key
            possible_keys = ['access_token', 'jwt_token', 'auth_token', 'token']
            for key in possible_keys:
                token = self.driver.execute_script(f"return sessionStorage.getItem('{key}');") or \
                        self.driver.execute_script(f"return localStorage.getItem('{key}');")
                if token:
                    print(f"✓ 从存储中获取到token (key: {key})")
                    return token

            print("❌ 未在浏览器存储中找到token")
            return None

        except Exception as e:
            print(f"❌ 提取token过程中出错: {e}")
            return None

    def get_token_automatically(self, sno):
        """自动获取token的主函数"""
        print("开始自动获取BJTU token...")

        if not self.setup_browser():
            return None

        try:
            # 第一步：CAS登录
            if not self.login_to_cas(sno):
                return None

            # 核心代码勿动
            time.sleep(5)  # 等待mis网站完全加载

            # 第二步：导航到token页面
            if not self.navigate_to_token_page():
                return None

            # 第三步：提取token
            token = self.extract_token_from_storage()

            if token:
                print(f"\n🎉 成功获取token!")
                return token
            else:
                print("\n❌ 获取token失败")
                return None

        except Exception as e:
            print(f"❌ 自动获取token过程中出错: {e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()

    def write_token_to_file(self, t):
        with open(self.token_file, 'w', encoding='utf-8') as f:
            f.write(t)


# 使用示例
def main():
    # 创建登录实例（headless=False表示显示浏览器窗口）
    TT = TokenManager(headless=False)

    # 获取token
    token = TT.get_token('23125217')

    if token:
        print(f"\n=== TOKEN获取成功 ===")
        print(f"Token: {token}")
        print("=====================")

        # 也可以直接返回给主程序使用
        return token
    else:
        print("\n=== TOKEN获取失败 ===")
        return None


if __name__ == "__main__":
    main()