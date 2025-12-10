import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime

# --- 配置区域 (从 GitHub Secrets 读取) ---
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = os.getenv("MAIL_USER")    # 你的邮箱
MAIL_PASS = os.getenv("MAIL_PASS")    # 你的授权码
RECEIVER_EMAIL = os.getenv("MAIL_USER") # 收件人(默认发给自己)

# --- 监控目标 ---
TARGETS = [
    {
        "name": "力工学院-通知公告",
        "url": "https://smes.shu.edu.cn/tzgg.htm",
        "selector": "div.main_conR ul li a"
    },
    {
        "name": "上大研究生院-公告",
        "url": "https://gs.shu.edu.cn/tzgg.htm",
        "selector": "div.list ul li a"
    }
]

HISTORY_FILE = "history.txt"

# --- 核心代码 ---
def send_email(title, link, source_name):
    """发送邮件"""
    if not MAIL_USER or not MAIL_PASS:
        print("错误：未配置邮箱 Secrets")
        return

    try:
        subject = f"【新通知】{source_name}: {title}"
        content = f"检测时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n标题: {title}\n来源: {source_name}\n链接: {link}"
        
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = MAIL_USER
        message['To'] = RECEIVER_EMAIL
        message['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(MAIL_USER, MAIL_PASS)
        server.sendmail(MAIL_USER, [RECEIVER_EMAIL], message.as_string())
        server.quit()
        print(f"邮件已发送: {title}")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def run_task():
    print("开始检查...")
    # 读取历史记录
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = set(line.strip() for line in f)
    else:
        history = set()

    new_history = history.copy()
    has_new = False
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"}

    for target in TARGETS:
        try:
            resp = requests.get(target['url'], headers=headers, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.select(target['selector'])
            
            for link in links:
                href = link.get('href')
                title = link.get_text(strip=True)
                if not href: continue

                # 处理链接
                full_url = href if href.startswith("http") else f"{target['url'].rsplit('/', 1)[0]}/{href}"
                if full_url.startswith("/"): # 处理根目录绝对路径
                     domain = "/".join(target['url'].split("/")[:3])
                     full_url = domain + full_url

                if full_url not in history:
                    new_history.add(full_url)
                    has_new = True
                    # 只有当历史记录不为空时才发邮件(防止第一次运行炸邮箱)
                    if len(history) > 0:
                        send_email(title, full_url, target['name'])
                    else:
                        print(f"初始化收录: {title}")

        except Exception as e:
            print(f"错误: {e}")

    # 保存记录
    if has_new:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for url in new_history:
                f.write(url + "\n")
        print("历史记录已更新")
    else:
        print("暂无新通知")

if __name__ == "__main__":
    run_task()