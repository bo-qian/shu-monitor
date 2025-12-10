import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime
import urllib3

# 禁用安全警告（学校网站证书经常过期）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置区域 ---
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")
RECEIVER_EMAIL = os.getenv("MAIL_USER")

HISTORY_FILE = "history.txt"

# --- 定义目标 ---
SCHOOLS = [
    {
        "name": "力工学院-通知公告",
        # 力工学院的网址你之前已经跑通了，保持不变
        "candidates": [
            "https://smes.shu.edu.cn/index/tzgg.htm",
            "https://smes.shu.edu.cn/tzgg.htm"
        ],
        "selectors": ["div[class*='list'] li a", ".winstyle67696 a", "ul li a"]
    },
    {
        "name": "上大研究生院-通知公告",
        # ✅ 这里修复了！利用你提供的线索 1027
        "candidates": [
            "https://gs.shu.edu.cn/index/1027.htm",  # 可能性1：数字ID索引 (最可能)
            "https://gs.shu.edu.cn/tzgg.htm"         # 可能性2：备用
        ],
        # 选择器保持宽泛，只要是列表里的链接都抓
        "selectors": ["div[class*='list'] li a", ".winstyle196036 a", "ul li a", "table.winstyle126615 a"]
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
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def run_task():
    print(f"[{datetime.datetime.now()}] 开始抓取...")
    
    # 伪装成浏览器
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

        # === 1. 寻找正确的网址 ===
        for url in school['candidates']:
            try:
                print(f"  Trying: {url} ...", end="")
                # verify=False 忽略证书错误
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                resp.encoding = 'utf-8'
                
                if resp.status_code == 200:
                    # 简单检查一下页面有没有内容，防止假死
                    if len(resp.text) > 500:
                        print(" ✅ 通了！")
                        valid_soup = BeautifulSoup(resp.text, 'html.parser')
                        used_url = url
                        break
                    else:
                        print(" ⚠️ 内容过短(可能被屏蔽)")
                else:
                    print(f" ❌ {resp.status_code}")
            except Exception as e:
                print(f" ❌ 出错")
        
        if not valid_soup:
            print(f"⚠️ {school['name']} 无法访问，跳过。")
            continue

        # === 2. 抓取内容 ===
        links = []
        for selector in school['selectors']:
            found = valid_soup.select(selector)
            if found:
                links = found
                break
        
        found_count = 0
        for link in links:
            href = link.get('href')
            title = link.get_text(strip=True)
            
            # 过滤无效标题
            if not href or len(title) < 4 or "更多" in title: continue
            
            # 拼接链接
            if not href.startswith("http"):
                if href.startswith("/"):
                    # 绝对路径 /info/...
                    domain = "/".join(used_url.split("/")[:3])
                    full_url = domain + href
                else:
                    # 相对路径 info/... 或 ../info/...
                    # 简单处理：如果是 info/ 开头，直接拼域名
                    if href.startswith("info/"):
                         domain = "/".join(used_url.split("/")[:3])
                         full_url = f"{domain}/{href}"
                    else:
                         full_url = used_url.rsplit("/", 1)[0] + "/" + href
            else:
                full_url = href

            found_count += 1
            
            # === 核心逻辑 ===
            if full_url not in history:
                new_history.add(full_url)
                has_new = True
                
                # ✅ 这里的逻辑是：
                # 如果历史记录不是空的（说明不是第一次跑），就发邮件
                # 如果你想立刻测试研究生院的邮件，可以暂时把 "and len(history) > 0" 删掉
                if len(history) > 0:
                    send_email(title, full_url, school['name'])
                else:
                    print(f"  [初始化收录] {title}")

        print(f"  > 解析出 {found_count} 条通知")

    # 保存
    if has_new:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for url in sorted(list(new_history)):
                f.write(url + "\n")
        print("\n✅ 历史记录已更新")
    else:
        print("\n暂无新内容")

if __name__ == "__main__":
    run_task()
