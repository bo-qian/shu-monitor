import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
import datetime

# --- 配置 ---
# (为了测试，我们暂时不发邮件，只测试抓取和写入)
TARGETS = [
    {
        "name": "力工学院-通知公告",
        "url": "https://smes.shu.edu.cn/tzgg.htm",
        "selector": "div.main_conR ul li a, div.list_right ul li a, .list ul li a" # 增加了多个备选规则
    },
    {
        "name": "上大研究生院-公告",
        "url": "https://gs.shu.edu.cn/tzgg.htm",
        "selector": "div.list ul li a, .list_r ul li a" 
    }
]
HISTORY_FILE = "history.txt"

def run_debug():
    print(f"[{datetime.datetime.now()}] === 开始调试模式 ===")
    
    # 1. 检查文件权限
    print(f"当前工作目录: {os.getcwd()}")
    if os.path.exists(HISTORY_FILE):
        print("history.txt 文件存在。")
    else:
        print("history.txt 文件不存在，准备创建。")

    all_links = []
    
    # 模拟更真实的浏览器头，防止被拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    for target in TARGETS:
        print(f"\n正在尝试连接: {target['name']} -> {target['url']}")
        try:
            resp = requests.get(target['url'], headers=headers, timeout=20)
            resp.encoding = 'utf-8'
            print(f"  > 状态码: {resp.status_code} (200表示成功)")
            
            if resp.status_code != 200:
                print("  > ❌ 网页无法访问，跳过。")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 调试：打印一下网页长度，看是不是空白页
            print(f"  > 网页内容长度: {len(resp.text)} 字符")
            
            # 尝试查找链接
            # 注意：这里增加了多个选择器，尝试匹配更多情况
            links = soup.select(target['selector'])
            print(f"  > 🔍 找到链接数量: {len(links)}")
            
            if len(links) == 0:
                print("  > ⚠️ 警告：没找到任何链接！可能是选择器错了，或者网页有反爬虫验证。")
            
            for link in links:
                href = link.get('href')
                title = link.get_text(strip=True)
                if href and len(title) > 2:
                    # 简单拼接
                    full = href if href.startswith("http") else target['url'].rsplit('/', 1)[0] + '/' + href
                    all_links.append(f"{title} | {full}")
                    # 只打印前3个看看对不对
                    if len(all_links) <= 3:
                        print(f"    - 抓取样例: {title}")

        except Exception as e:
            print(f"  > ❌ 发生错误: {e}")

    # 2. 强行写入文件测试
    if len(all_links) > 0:
        print(f"\n正在写入 {len(all_links)} 条数据到 history.txt ...")
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for item in all_links:
                    f.write(item + "\n")
            print("✅ 写入完成！")
        except Exception as e:
            print(f"❌ 写入文件失败: {e}")
    else:
        print("\n❌ 没有抓取到任何数据，文件未更新。")

if __name__ == "__main__":
    run_debug()
