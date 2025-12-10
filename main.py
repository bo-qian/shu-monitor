import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime

# --- 1. 配置区域 (从 GitHub Secrets 读取) ---
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")
RECEIVER_EMAIL = os.getenv("MAIL_USER")

HISTORY_FILE = "history.txt"

# --- 2. 定义目标 (增加了备选规则) ---
TARGETS = [
    {
        "name": "力工学院-通知公告",
        "url": "https://smes.shu.edu.cn/tzgg.htm",
        # 尝试匹配多种常见的网页结构
        "selectors": [
            "div.main_conR ul li a", 
            "div.list_right ul li a", 
            ".winstyle67696 a",     # 常见的动态组件类名
            "div[class*='list'] ul li a", # 包含list的任何div
            "ul.news_list li a"
        ]
    },
    {
        "name": "上大研究生院-公告",
        "url": "https://gs.shu.edu.cn/tzgg.htm",
        "selectors": [
            "div.list ul li a", 
            "div.list_r ul li a",
            ".winstyle196036 a",
            "div[class*='list'] li a"
        ]
    }
]

def send_email(title, link, source_name):
    if not MAIL_USER or not MAIL_PASS:
        print("⚠️ 邮箱配置缺失，跳过发送邮件")
        return

    try:
        subject = f"【新通知】{source_name}: {title}"
        content = f"来源: {source_name}\n时间: {datetime.datetime.now()}\n标题: {title}\n链接: {link}"
        
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = MAIL_USER
        message['To'] = RECEIVER_EMAIL
        message['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(MAIL_USER, MAIL_PASS)
        server.sendmail(MAIL_USER, [RECEIVER_EMAIL], message.as_string())
        server.quit()
        print(f"📧 邮件已发送: {title}")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def run_task():
    print(f"[{datetime.datetime.now()}] 开始增强版抓取...")
    
    # 读取历史
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                history.add(line.strip())
    print(f"当前历史记录条数: {len(history)}")

    new_history = history.copy()
    has_new = False
    
    # === 关键修改：伪装成浏览器 ===
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    for target in TARGETS:
        print(f"\n正在连接: {target['name']} -> {target['url']}")
        try:
            # 增加 verify=False 防止学校证书过期报错
            resp = requests.get(target['url'], headers=headers, timeout=20, verify=False)
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                print(f"❌ 访问失败，状态码: {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            found_links = []

            # === 关键修改：轮询尝试所有选择器 ===
            for selector in target['selectors']:
                links = soup.select(selector)
                if links:
                    print(f"✅ 规则 '{selector}' 生效，找到 {len(links)} 个链接")
                    found_links = links
                    break # 找到一种能用的就行了
            
            if not found_links:
                print(f"⚠️ 警告：该网站未匹配到任何链接！可能网页结构有变。")
                # 调试用：打印网页标题看看是不是进错页面了
                print(f"网页标题: {soup.title.string if soup.title else '无标题'}")
                continue

            # 处理抓到的链接
            for link in found_links:
                href = link.get('href')
                title = link.get_text(strip=True)
                
                # 过滤掉无效链接
                if not href or len(title) < 2 or "javascript" in href:
                    continue

                # 拼接完整网址
                if not href.startswith("http"):
                    if href.startswith("/"):
                        domain = "/".join(target['url'].split("/")[:3])
                        full_url = domain + href
                    else:
                        full_url = target['url'].rsplit("/", 1)[0] + "/" + href
                else:
                    full_url = href

                # 记录逻辑
                if full_url not in history:
                    new_history.add(full_url)
                    has_new = True
                    # 如果不是初始化（历史非空），就发邮件
                    # ⚠️ 为了测试，您可以把下面这行 len(history) > 0 去掉，这样每次运行即使是新的也会强制发邮件
                    if len(history) > 0: 
                        send_email(title, full_url, target['name'])
                    else:
                        print(f"  [初始化收录] {title}")

        except Exception as e:
            print(f"❌ 发生程序错误: {e}")

    # 保存
    if has_new:
        print(f"\n正在保存 {len(new_history)} 条记录到文件...")
        # 排序保存，看着整齐
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for url in sorted(list(new_history)):
                f.write(url + "\n")
        print("✅ 历史记录已更新！")
    else:
        print("\n没有发现新内容 (或者所有内容都已在记录中)")

if __name__ == "__main__":
    # 屏蔽 SSL 警告
    requests.packages.urllib3.disable_warnings()
    run_task()
