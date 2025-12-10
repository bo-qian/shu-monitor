import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime
import urllib3
import re

# 忽略 SSL 证书警告
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
        # 力工学院已经通了，保持原样
        "urls": ["https://smes.shu.edu.cn/index/tzgg.htm"],
        "selectors": ["div[class*='list'] li a", ".winstyle67696 a", "ul li a"]
    },
    {
        "name": "上大研究生院-综合通知(1027)",
        "urls": [
            # 🔥 方案A: 动态直连 (最稳，直接用ID 1027)
            "https://gs.shu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1027",
            # 🔥 方案B: 扫荡首页 (防止列表页挂了，首页通常有最新几条)
            "https://gs.shu.edu.cn/index.htm"
        ],
        # 只要链接里包含 info/1027 我们就认为是这个栏目的新闻
        "keyword": "info/1027", 
        "selectors": ["a"] # 抓取所有链接，然后用 keyword 过滤
    },
    {
        "name": "上大研究生院-培养管理(1029)",
        "urls": [
            # 同理，直接用ID 1029
            "https://gs.shu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1029",
            "https://gs.shu.edu.cn/index.htm"
        ],
        "keyword": "info/1029",
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
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def run_task():
    print(f"[{datetime.datetime.now()}] 开始ID直连抓取...")
    
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
        print(f"\n正在连接: {school['name']}")
        
        # 遍历该栏目的所有可能的入口URL
        for url in school['urls']:
            try:
                print(f"  Trying: {url} ...", end="")
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                resp.encoding = 'utf-8'
                
                if resp.status_code != 200:
                    print(f" ❌ {resp.status_code}")
                    continue
                
                print(" ✅ 通了")
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 提取链接
                # 如果指定了 keyword (针对研究生院)，就暴力扫描所有链接并过滤
                found_links = []
                if "keyword" in school:
                    all_tags = soup.find_all('a')
                    for tag in all_tags:
                        href = tag.get('href')
                        if href and school['keyword'] in href:
                            found_links.append(tag)
                else:
                    # 针对力工学院，用选择器
                    for sel in school['selectors']:
                        found_links = soup.select(sel)
                        if found_links: break

                print(f"    > 找到 {len(found_links)} 个相关链接")

                # 处理链接
                for link in found_links:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    
                    if not href or len(title) < 4: continue
                    
                    # 拼接完整URL
                    if not href.startswith("http"):
                        if href.startswith("/"):
                            domain = "/".join(url.split("/")[:3]) # 提取 https://gs.shu.edu.cn
                            full_url = domain + href
                        else:
                            # 即使是相对路径，只要是 info/ 开头，通常也是根目录下的
                            if href.startswith("info/"):
                                domain = "/".join(url.split("/")[:3])
                                full_url = f"{domain}/{href}"
                            else:
                                full_url = url.rsplit("/", 1)[0] + "/" + href
                    else:
                        full_url = href

                    # 去重并记录
                    if full_url not in history:
                        new_history.add(full_url)
                        has_new = True
                        
                        # 发送逻辑
                        if len(history) > 0:
                            send_email(title, full_url, school['name'])
                        else:
                            print(f"    [初始化] {title}")

            except Exception as e:
                print(f" ❌ 出错: {e}")

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
