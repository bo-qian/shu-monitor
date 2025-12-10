import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime

# --- 配置区域 ---
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")
RECEIVER_EMAIL = os.getenv("MAIL_USER")

HISTORY_FILE = "history.txt"

# --- 定义学校和可能的网址列表 ---
# 我们列出所有可能的地址，让程序自己去撞
SCHOOLS = [
    {
        "name": "力工学院-通知公告",
        "candidates": [
            "https://smes.shu.edu.cn/index/tzgg.htm",  # 可能性1
            "https://smes.shu.edu.cn/xyxw/tzgg.htm",   # 可能性2
            "https://smes.shu.edu.cn/tzgg.htm"         # 可能性3
        ],
        "selectors": ["div[class*='list'] li a", ".winstyle67696 a", "ul li a"]
    },
    {
        "name": "上大研究生院-公告",
        "candidates": [
            "https://gs.shu.edu.cn/index/tzgg.htm",
            "https://gs.shu.edu.cn/xwzx/tzgg.htm",
            "https://gs.shu.edu.cn/tzgg.htm"
        ],
        "selectors": ["div[class*='list'] li a", ".winstyle196036 a", "ul li a"]
    }
]

def send_email(title, link, source_name):
    if not MAIL_USER or not MAIL_PASS:
        return
    try:
        subject = f"【新通知】{source_name}: {title}"
        content = f"来源: {source_name}\n标题: {title}\n链接: {link}\n时间: {datetime.datetime.now()}"
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
    print(f"[{datetime.datetime.now()}] 开始智能抓取...")
    
    # 伪装浏览器头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 读取历史
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                history.add(line.strip())
    
    new_history = history.copy()
    has_new = False

    for school in SCHOOLS:
        print(f"\n正在尝试连接: {school['name']}")
        valid_soup = None
        used_url = ""

        # === 智能轮询：尝试列表里的每一个网址 ===
        for url in school['candidates']:
            try:
                print(f"  Trying: {url} ...", end="")
                resp = requests.get(url, headers=headers, timeout=10, verify=False)
                resp.encoding = 'utf-8'
                
                if resp.status_code == 200:
                    print(" ✅ 通了！")
                    valid_soup = BeautifulSoup(resp.text, 'html.parser')
                    used_url = url
                    break # 找到了就停止尝试，进入下一步
                else:
                    print(f" ❌ {resp.status_code}")
            except:
                print(" ❌ 连接超时")
        
        if not valid_soup:
            print(f"⚠️ {school['name']} 所有网址都试过了，无法访问。")
            continue

        # === 开始抓取 ===
        found_count = 0
        # 尝试所有选择器
        links = []
        for selector in school['selectors']:
            links = valid_soup.select(selector)
            if links: break
        
        for link in links:
            href = link.get('href')
            title = link.get_text(strip=True)
            
            if not href or len(title) < 4 or "更多" in title: continue
            
            # 拼接链接
            if not href.startswith("http"):
                if href.startswith("/"):
                    domain = "/".join(used_url.split("/")[:3])
                    full_url = domain + href
                else:
                    full_url = used_url.rsplit("/", 1)[0] + "/" + href
            else:
                full_url = href

            found_count += 1
            if full_url not in history:
                new_history.add(full_url)
                has_new = True
                
                # ⚠️ 测试开关：
                # 如果你想立刻收到邮件测试，把 "and len(history) > 0" 删掉
                if len(history) > 0:
                    send_email(title, full_url, school['name'])
                else:
                    print(f"  [初始化收录] {title}")

        print(f"  > 成功解析出 {found_count} 条通知")

    # 保存
    if has_new:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for url in sorted(list(new_history)):
                f.write(url + "\n")
        print("\n✅ 历史记录已更新")
    else:
        print("\n暂无新内容")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    run_task()
