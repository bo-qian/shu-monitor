import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime
import urllib3
import time  # 引入时间库，用于控制发送速度
import posixpath
import re
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit

# 忽略证书错误警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置区域 ---
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = "bo.qian@foxmail.com"
MAIL_PASS = os.getenv("MAIL_PASS")
RECEIVER_EMAIL = MAIL_USER

HISTORY_FILE = "history.txt"

SCHOOLS = [
    {
        "name": "力工学院-通知公告",
        "urls": ["https://smes.shu.edu.cn/index/tzgg.htm"],
        "keywords": ["info/1015/"],
        "selectors": ["a"]
    },
    {
        "name": "力工学院-学生信息",
        "urls": ["https://smes.shu.edu.cn/index/xsxx.htm"],
        "keywords": ["info/1016/", "mp.weixin.qq.com", "r.xiumi.us"],
        "selectors": ["a"]
    },
    {
        "name": "力工学院-学术报告",
        "urls": ["https://smes.shu.edu.cn/index/xsbg.htm"],
        "keywords": ["info/1014/"],
        "selectors": ["a"]
    },
    {
        "name": "上大研究生院-综合",
        "urls": ["https://gs.shu.edu.cn/xwlb/zh.htm"],
        "keywords": ["info/1027/"],
        "selectors": ["a"]
    },
    {
        "name": "上大研究生院-培养",
        "urls": ["https://gs.shu.edu.cn/xwlb/py.htm"],
        "keywords": ["info/1029/"],
        "selectors": ["a"]
    },
    {
        "name": "上大研究生院-学位",
        "urls": ["https://gs.shu.edu.cn/xwlb/xw.htm"],
        "keywords": ["info/1031/"],
        "selectors": ["a"]
    },
    {
        "name": "上大研究生院-国际交流",
        "urls": ["https://gs.shu.edu.cn/xwlb/gjjl.htm"],
        "keywords": ["info/1030/"],
        "selectors": ["a"]
    },
    {
        "name": "上大研究生院-招生",
        "urls": ["https://gs.shu.edu.cn/xwlb/zs.htm"],
        "keywords": ["info/1028/", "yjszs.shu.edu.cn/info/"],
        "selectors": ["a"] 
    }
]

SKIP_TITLES = {"公告", "综合", "招生", "培养", "国际交流", "学位", "信息", "博士后", "所有"}

def normalize_url(url):
    """Canonicalize notice URLs so the same page is not sent twice."""
    clean_url = urldefrag(url.strip())[0]
    parts = urlsplit(clean_url)
    if not parts.scheme or not parts.netloc:
        return clean_url

    path = posixpath.normpath(parts.path)
    if parts.path.endswith("/") and not path.endswith("/"):
        path += "/"
    if not path.startswith("/"):
        path = "/" + path

    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        path,
        parts.query,
        ""
    ))

def clean_title(link):
    title = link.get('title') or link.get_text(" ", strip=True)
    title = re.sub(r'\s*\d{4}[-/]\d{2}[-/]\d{2}.*$', '', title).strip()
    return title

def extract_publish_date(link):
    candidates = [
        link.get_text(" ", strip=True),
        link.parent.get_text(" ", strip=True) if link.parent else "",
        link.find_parent("li").get_text(" ", strip=True) if link.find_parent("li") else "",
    ]
    for text in candidates:
        match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', text)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
    return "未识别"

def send_email(title, link, source_name, publish_date="未识别"):
    if not MAIL_USER or not MAIL_PASS:
        print(f"⚠️ 邮箱配置不完整，跳过发送: {title}")
        return
    try:
        subject = f"【新通知】{source_name}: {title}"
        content = (
            f"来源: {source_name}\n"
            f"发布时间: {publish_date}\n"
            f"检测时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"标题: {title}\n"
            f"链接: {link}"
        )
        
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = MAIL_USER
        message['To'] = RECEIVER_EMAIL
        message['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(MAIL_USER, MAIL_PASS)
        server.sendmail(MAIL_USER, [RECEIVER_EMAIL], message.as_string())
        server.quit()
        print(f"📧 [已发送] {title}")
        
        # === 核心保护机制 ===
        # 每发完一封，强制休息 10 秒
        # 这是为了防止 QQ 邮箱把你当成发垃圾广告的直接封号
        print("   (休息 10 秒)...")
        time.sleep(10) 
        
    except Exception as e:
        print(f"❌ 发送失败: {e}")

def run_test_email():
    print("手动测试模式：只发送一封测试邮件，不抓取通知，也不修改 history.txt。")
    send_email(
        "School Monitor 测试邮件",
        "https://github.com/bo-qian/shu-monitor/actions",
        "School Monitor",
        datetime.datetime.now().strftime('%Y-%m-%d')
    )

def run_task():
    print(f"[{datetime.datetime.now()}] 开始抓取...")

    if os.getenv("SEND_TEST_EMAIL", "").lower() == "true":
        run_test_email()
        return
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 读取历史记录
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = normalize_url(line)
                if url:
                    history.add(url)
    
    new_history = history.copy()
    has_new = False
    sent_count = 0

    for school in SCHOOLS:
        print(f"\n正在连接: {school['name']}")
        soup = None
        used_url = ""

        # 尝试连接
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
        
        if not soup: continue

        # 提取链接
        found_links = []
        if "keywords" in school: # 关键词模式(研究生院)
            all_a = soup.find_all('a')
            for a in all_a:
                href = a.get('href')
                if href and any(k in href for k in school['keywords']):
                    found_links.append(a)
        else: # 选择器模式(力工学院)
            for sel in school['selectors']:
                found_links = soup.select(sel)
                if found_links: break

        print(f"    > 找到 {len(found_links)} 个相关链接")

        # 倒序处理（让旧通知先发，新通知后发，或者保持网页顺序）
        # 这里保持网页默认顺序
        for link in found_links:
            href = link.get('href')
            title = clean_title(link)
            publish_date = extract_publish_date(link)
            
            if not href or len(title) < 4 or title in SKIP_TITLES: continue
            
            # 链接补全并规范化，避免 ../ 和重复链接造成重复通知。
            full_url = normalize_url(urljoin(used_url, href))

            # === 核心逻辑修改 ===
            # 用 new_history 判断，避免同一次运行里重复链接发多封邮件。
            if full_url not in new_history:
                send_email(title, full_url, school['name'], publish_date)
                
                new_history.add(full_url)
                has_new = True
                sent_count += 1

    # 全部发完后，保存记录
    # 这样下次运行，这些已经在 new_history 里的就不会再发了
    if has_new:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for url in sorted(list(new_history)):
                f.write(url + "\n")
        print(f"\n✅ 初始化完成！已发送 {sent_count} 封邮件，记录已更新。")
    else:
        print("\n暂无新内容")

if __name__ == "__main__":
    run_task()
