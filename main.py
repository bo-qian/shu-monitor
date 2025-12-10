import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime
import urllib3
import time  # <--- 引入时间库，用来"休息"

# 忽略证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置区域 ---
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")
RECEIVER_EMAIL = os.getenv("MAIL_USER")

HISTORY_FILE = "history.txt"

SCHOOLS = [
    {
        "name": "力工学院-通知公告",
        "urls": ["https://smes.shu.edu.cn/index/tzgg.htm"],
        "selectors": ["div[class*='list'] li a", ".winstyle67696 a", "ul li a"]
    },
    {
        "name": "上大研究生院-综合通知",
        "urls": [
            # 优先尝试新闻中心主页（这里通常包含最新通知）
            "https://gs.shu.edu.cn/xwzx.htm",
            "https://gs.shu.edu.cn/index.htm"
        ],
        # 只要链接包含 info/1027 (公告ID) 或 info/1029 (培养ID) 就抓取
        "keywords": ["info/1027", "info/1029"],
        "selectors": ["a"] 
    }
]

def send_email(title, link, source_name):
    if not MAIL_USER or not MAIL_PASS:
        return
    try:
        subject = f"【新通知】{source_name}: {title}"
        content = f"来源: {source_name}\n时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n标题: {title}\n链接: {link}"
        
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = MAIL_USER
        message['To'] = RECEIVER_EMAIL
        message['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(MAIL_USER, MAIL_PASS)
        server.sendmail(MAIL_USER, [RECEIVER_EMAIL], message.as_string())
        server.quit()
        print(f"📧 邮件已发送: {title}")
        
        # === 关键修改：每发一封信，休息 5 秒 ===
        print("   (休息5秒防止被封)...")
        time.sleep(5) 
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def run_task():
    print(f"[{datetime.datetime.now()}] 开始抓取...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                history.add(line.strip())
    
    new_history = history.copy()
    has_new = False

    for school in SCHOOLS:
        print(f"\n正在连接: {school['name']}")
        soup = None
        used_url = ""

        for url in school['urls']:
            try:
                print(f"  Trying: {url} ...", end="")
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                resp.encoding = 'utf-8'
                if resp.status_code == 200 and len(resp.text) > 500:
                    print(" ✅ 通了")
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    used_url = url
                    break
                else:
                    print(f" ❌ {resp.status_code}")
            except:
                print(" ❌ 超时")
        
        if not soup:
            continue

        # 抓取链接
        found_links = []
        
        # 策略A: 关键字过滤 (针对研究生院)
        if "keywords" in school:
            all_a = soup.find_all('a')
            for a in all_a:
                href = a.get('href')
                if href:
                    # 只要包含任意一个关键字
                    if any(k in href for k in school['keywords']):
                        found_links.append(a)
        
        # 策略B: 选择器 (针对力工学院)
        else:
            for sel in school['selectors']:
                found_links = soup.select(sel)
                if found_links: break

        print(f"    > 找到 {len(found_links)} 个相关链接")

        for link in found_links:
            href = link.get('href')
            title = link.get_text(strip=True)
            
            if not href or len(title) < 4: continue
            
            # 补全链接
            if not href.startswith("http"):
                if href.startswith("/"):
                    domain = "/".join(used_url.split("/")[:3])
                    full_url = domain + href
                else:
                    if href.startswith("info/"): # 修复相对路径
                         domain = "/".join(used_url.split("/")[:3])
                         full_url = f"{domain}/{href}"
                    else:
                         full_url = used_url.rsplit("/", 1)[0] + "/" + href
            else:
                full_url = href

            if full_url not in history:
                new_history.add(full_url)
                has_new = True
                
                # 发送邮件 (只要历史记录不为空就发)
                if len(history) > 0:
                    send_email(title, full_url, school['name'])
                else:
                    print(f"    [初始化] {title}")

    # 保存
    if has_new:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for url in sorted(list(new_history)):
                f.write(url + "\n")
        print("\n✅ 记录已更新")

if __name__ == "__main__":
    run_task()
