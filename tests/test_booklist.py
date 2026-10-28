"""推薦書單（不需要 AI）的端對端測試。

用法：
  pip install playwright && playwright install chromium
  python3 tests/test_booklist.py                 # 自動在本機起一個靜態伺服器測 index.html
  BASE_URL=https://ritakiros.github.io/library-life/ python3 tests/test_booklist.py
  SHOT_DIR=/tmp/shots python3 tests/test_booklist.py   # 另存截圖
"""
import os, sys, json, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.environ.get("SHOT_DIR")
PREFIX = os.environ.get("SHOT_PREFIX", "local")


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=ROOT)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def shot(page, name):
    if SHOT_DIR:
        os.makedirs(SHOT_DIR, exist_ok=True)
        page.screenshot(path=os.path.join(SHOT_DIR, f"{PREFIX}-{name}.png"), full_page=True)


def main():
    base = os.environ.get("BASE_URL")
    httpd = None
    if not base:
        httpd, base = serve()
    errors, failures = [], []

    def check(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            failures.append(msg)

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        page = b.new_page(viewport={"width": 1280, "height": 900})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        check(page.evaluate("typeof window.claude") == "undefined", "沒有 window.claude（單機版）")

        page.click('button[data-go="build"]')
        page.click('button[data-step="3"]')
        page.click('button[data-zoneidea="翻譯文學"]')
        block = page.locator(".spec", has_text="翻譯文學")
        btn = block.locator("button", has_text="推薦書單")
        check(btn.count() == 1, "書區有「推薦書單」按鈕")
        if btn.count() != 1:
            raise SystemExit(finish(b, httpd, errors, failures))
        btn.click()
        boxes = block.locator('.sugg input[type="checkbox"]')
        n = boxes.count()
        check(8 <= n <= 15, f"推薦書單有 8–15 本可勾選的書（實際 {n}）")
        check(block.locator('.sugg a[href*="book.tpml.edu.tw"]', has_text="北市圖館藏").count() == n, "每本書都有北市圖館藏連結")
        check(block.locator('.sugg a[href*="search.books.com.tw"]', has_text="博客來").count() == n, "每本書都有博客來連結")
        check(block.locator("form.addbook").count() == 1, "書單下方可以自己加一本書")
        titles = [block.locator(".sugg label b").nth(i).inner_text() for i in range(2)]
        boxes.nth(0).check()
        boxes.nth(1).check()
        shot(page, "booklist")
        block.locator("button", has_text="列入館藏").click()
        saved = json.loads(page.evaluate("localStorage.getItem('libbuild.v2')"))
        got = [x["title"] for x in saved["books"]]
        check(sorted(got) == sorted(titles), f"勾 2 本列入館藏並存進 localStorage（{got}）")

        # 自訂書區沒有對應書單時，退回特色或熱門書單
        page.fill("#customSpec", "貓咪")
        page.click("#customForm button[type=submit]")
        cat = page.locator(".spec", has_text="貓咪")
        cat.locator("button", has_text="推薦書單").click()
        check(cat.locator('.sugg input[type="checkbox"]').count() >= 8, "自訂書區也有備用推薦書單")
        cat.locator("form.addbook input").fill("我是貓")
        cat.locator("form.addbook button").click()
        saved = json.loads(page.evaluate("localStorage.getItem('libbuild.v2')"))
        check(any(x["title"] == "我是貓" for x in saved["books"]), "書區裡可以自己加一本書")

        # 依特色建議書區（內建）
        zb = page.locator('button[data-suggestzones]')
        if zb.count():
            check("AI" not in zb.inner_text(), "建議書區按鈕不再寫 AI")
            zb.click()
            check(page.locator(".note.bad").count() == 0, "建議書區沒有錯誤訊息")

        body = page.inner_text("body")
        check("claude.ai" not in body, "畫面沒有 claude.ai 錯誤字樣")
        check("請 AI" not in body and "AI 建議書單" not in body, "畫面沒有叫玩家去問 AI 的字樣")

        page.reload(wait_until="networkidle")
        saved = json.loads(page.evaluate("localStorage.getItem('libbuild.v2')"))
        check(all(t in [x["title"] for x in saved["books"]] for t in titles), "重新整理後館藏還在")
        page.click('button[data-go="build"]')
        page.click('button[data-step="4"]')
        page.click('button[data-nav="open"]')
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        check(all(t in body for t in titles), "館長室的館藏清單看得到新加的書")
        check("claude.ai" not in body and "請 AI" not in body, "館長室沒有 AI 字樣")
        shot(page, "collection")
        page.click('button[data-work="1"]')
        page.wait_for_timeout(1500)
        check(page.locator(".catcard").count() == 1, "上班畫面可以用館藏的書練習分類")
        check(page.locator('.catcard a[href*="book.tpml.edu.tw"]').count() == 1, "上班畫面的書有北市圖館藏連結")
        check("claude.ai" not in page.inner_text("body"), "上班畫面沒有 claude.ai 字樣")
        shot(page, "shift")
        return finish(b, httpd, errors, failures)


def finish(b, httpd, errors, failures):
    b.close()
    if httpd:
        httpd.shutdown()
    print("console errors:", errors or 0)
    if errors:
        failures.append("console errors")
    print("RESULT:", "FAIL" if failures else "OK", f"({len(failures)} failed)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
