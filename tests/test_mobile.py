"""手機版排版與操作的端對端測試（iPhone 390x844、Android 360x740 模擬）。

用法：
  python3 tests/test_mobile.py
  BASE_URL=https://ritakiros.github.io/library-life/ python3 tests/test_mobile.py
  SHOT_DIR=/tmp/shots python3 tests/test_mobile.py
"""
import os, sys, json, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.environ.get("SHOT_DIR")
PREFIX = os.environ.get("SHOT_PREFIX", "local")
IOS_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/470.0.0;FBLC/zh_TW]")
AND_UA = ("Mozilla/5.0 (Linux; Android 13; SM-A135F) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")
DEVICES = [("iphone", 390, 844, IOS_UA), ("android360", 360, 740, AND_UA)]

# 回傳目前畫面的版面量測
MEASURE = r"""()=>{
  const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};
  const name=e=>(e.tagName.toLowerCase()+(e.className&&typeof e.className==='string'?'.'+e.className.trim().replace(/\s+/g,'.'):'')+' "'+(e.innerText||e.placeholder||'').trim().slice(0,14)+'"');
  const out={scrollW:document.documentElement.scrollWidth,W:innerWidth,
    bodyFs:parseFloat(getComputedStyle(document.body).fontSize),smallInputs:[],shortTaps:[]};
  document.querySelectorAll('input:not([type=checkbox]):not([type=radio]),select,textarea').forEach(e=>{
    if(vis(e)&&parseFloat(getComputedStyle(e).fontSize)<16)out.smallInputs.push(name(e)+' '+getComputedStyle(e).fontSize)});
  document.querySelectorAll('.btn,.chip,.steps button,.sugg label,.bk').forEach(e=>{
    if(!vis(e))return;const h=e.getBoundingClientRect().height;if(h<43.5)out.shortTaps.push(name(e)+' h='+Math.round(h))});
  return out}"""


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=ROOT)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main():
    base = os.environ.get("BASE_URL")
    httpd = None
    if not base:
        httpd, base = serve()
    failures = []

    def check(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            failures.append(msg)

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        for dev, w, h, ua in DEVICES:
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=3, is_mobile=True,
                                has_touch=True, user_agent=ua, locale="zh-TW")
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base, wait_until="networkidle")
            page.evaluate("localStorage.clear()")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(800)

            def shot(n):
                if SHOT_DIR:
                    os.makedirs(SHOT_DIR, exist_ok=True)
                    page.screenshot(path=os.path.join(SHOT_DIR, f"{PREFIX}-{dev}-{n}.png"))

            def layout(label, inputs=True, taps=True):
                page.wait_for_timeout(250)
                m = page.evaluate(MEASURE)
                # 手機瀏覽器內容太寬時 innerWidth 會跟著變大，所以跟裝置寬度比
                check(m["scrollW"] <= w and m["W"] <= w, f"[{dev}] {label}：沒有左右溢出（scrollWidth {m['scrollW']}、innerWidth {m['W']}，裝置 {w}）")
                if inputs:
                    check(not m["smallInputs"], f"[{dev}] {label}：輸入框與選單字級 ≥ 16px {m['smallInputs'][:3]}")
                if taps:
                    check(not m["shortTaps"], f"[{dev}] {label}：按鈕、chip、書單列高度 ≥ 44px {m['shortTaps'][:4]}")
                return m

            bar = page.locator("#actionbar")
            m = layout("入口")
            check(m["bodyFs"] >= 17, f"[{dev}] 基本字級 ≥ 17px（{m['bodyFs']}）")
            shot("01-intro")

            page.click('button[data-go="build"]')
            layout("步驟 1 地點")
            check(bar.is_visible() and bar.locator("button", has_text="下一步").count() == 1, f"[{dev}] 手機底部操作列有「下一步」")
            shot("02-step1")

            # 在 3D 舞台上往上滑，頁面要能捲動
            page.evaluate("scrollTo(0,0)")
            page.wait_for_timeout(200)
            st = page.locator(".stage3d").bounding_box()
            cdp = ctx.new_cdp_session(page)
            x, y = st["x"] + st["width"] / 2, st["y"] + st["height"] * 0.75
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
            for i in range(1, 11):
                cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y - 15 * i}]})
                page.wait_for_timeout(16)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            page.wait_for_timeout(500)
            sy = page.evaluate("scrollY")
            check(sy > 40, f"[{dev}] 從 3D 舞台開始往上滑，頁面會捲動（scrollY={sy}）")
            check(page.locator("[data-rot]").count() == 1, f"[{dev}] 3D 舞台有「轉動」按鈕")

            for i, n in [(1, "名稱與外觀"), (2, "樓層與館員"), (3, "特色與書區")]:
                page.click(f'button[data-step="{i}"]')
                layout(f"步驟 {i+1} {n}")
                shot(f"02-step{i+1}")

            page.click('button[data-zoneidea="翻譯文學"]')
            block = page.locator(".spec", has_text="翻譯文學")
            block.locator("button", has_text="推薦書單").click()
            layout("推薦書單")
            rows = block.locator(".sugg label")
            boxes = block.locator('.sugg input[type="checkbox"]')
            rows.nth(0).locator("b").click()
            check(boxes.nth(0).is_checked(), f"[{dev}] 點書單那一列的書名就能勾選")
            rows.nth(0).locator("b").click()
            check(not boxes.nth(0).is_checked(), f"[{dev}] 再點一次取消勾選")
            rows.nth(0).locator("b").click()
            rows.nth(1).locator("b").click()
            add = bar.locator("button", has_text="列入館藏")
            check(bar.is_visible() and add.count() == 1 and "已選 2 本" in add.inner_text(),
                  f"[{dev}] 底部操作列顯示「列入館藏（已選 2 本）」")
            shot("03-booklist")
            # 3D 捲出畫面後要暫停繪圖
            page.evaluate("scrollTo(0,0)")
            page.wait_for_timeout(500)
            f0 = page.evaluate("G3.frames||0"); page.wait_for_timeout(700); f1 = page.evaluate("G3.frames||0")
            check(f1 - f0 > 3, f"[{dev}] 3D 在畫面內時會繪圖（{f1 - f0} 張）")
            page.evaluate("scrollTo(0,document.documentElement.scrollHeight)")
            page.wait_for_timeout(500)
            off = page.evaluate("document.querySelector('#stage').getBoundingClientRect().bottom")
            check(off < 0, f"[{dev}] 捲到底時 3D 舞台已在畫面外（bottom={off}）")
            f0 = page.evaluate("G3.frames||0"); page.wait_for_timeout(1000); f1 = page.evaluate("G3.frames||0")
            check(f1 - f0 <= 2, f"[{dev}] 3D 捲出畫面後暫停繪圖（1 秒畫了 {f1 - f0} 張）")
            page.evaluate("scrollTo(0,0)")

            if add.count():
                add.click()
            else:
                block.locator("button", has_text="列入館藏").click()
            if True:
                saved = json.loads(page.evaluate("localStorage.getItem('libbuild.v2')"))
                check(len(saved["books"]) == 2, f"[{dev}] 從底部操作列列入館藏 2 本（{len(saved['books'])}）")

            page.click('button[data-step="4"]')
            layout("步驟 5 櫃檯")
            shot("02-step5")
            openb = bar.locator('button[data-nav="open"]')
            check(openb.count() == 1 and openb.is_visible(), f"[{dev}] 最後一步底部操作列有開幕按鈕")
            if openb.count():
                openb.click()
            else:
                page.evaluate("document.querySelector('button[data-nav=open]').click()")
            page.wait_for_timeout(3500)
            page.evaluate("scrollTo(0,0)")
            layout("館長室")
            check(bar.is_visible() and bar.locator('button[data-work]').count() == 1, f"[{dev}] 館長室底部操作列有「上班」")
            shot("04-collection")
            page.locator("#quickBook").scroll_into_view_if_needed()
            shot("04b-collection-add")

            bar.locator('button[data-work]').first.click() if bar.locator('button[data-work]').count() else page.evaluate("document.querySelector('button[data-work]').click()")
            page.wait_for_timeout(1500)
            layout("上班")
            shot("05-shift")
            if not page.locator("button[data-ans]").count():
                check(False, f"[{dev}] 上班畫面有可以回答的書")
                ctx.close(); continue
            page.locator("button[data-ans]").first.click()
            nxt = bar.locator("button[data-nextitem]")
            check(nxt.count() == 1 and nxt.is_visible(), f"[{dev}] 上班回答後底部操作列有「下一本」")
            layout("上班回答後")
            shot("05b-shift-feedback")

            # 底部操作列不能蓋住內容：捲到最底，最後一個元素要在操作列上方
            page.evaluate("scrollTo(0,document.documentElement.scrollHeight)")
            page.wait_for_timeout(300)
            gap = page.evaluate("""()=>{const b=document.querySelector('#actionbar');if(!b||!b.offsetHeight)return null;
              const els=[...document.querySelectorAll('#app *')].filter(e=>e.offsetHeight&&getComputedStyle(e).display!=='none');
              const bottom=Math.max(...els.map(e=>e.getBoundingClientRect().bottom));return b.getBoundingClientRect().top-bottom}""")
            check(gap is not None and gap >= 0, f"[{dev}] 捲到最底時操作列沒有蓋住內容（間距 {gap}）")

            check(not errors, f"[{dev}] 沒有主控台錯誤 {errors[:3]}")
            ctx.close()

        # 桌機：不出現底部操作列、版面不溢出
        page = b.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base, wait_until="networkidle")
        page.click('button[data-go="build"]')
        page.wait_for_timeout(500)
        check(not page.locator("#actionbar").is_visible(), "[desktop] 桌機不顯示底部操作列")
        m = page.evaluate(MEASURE)
        check(m["scrollW"] <= 1280, f"[desktop] 沒有左右溢出（{m['scrollW']}）")
        check(not errors, f"[desktop] 沒有主控台錯誤 {errors[:3]}")
        if SHOT_DIR:
            page.screenshot(path=os.path.join(SHOT_DIR, f"{PREFIX}-desktop-build.png"))
        b.close()
    if httpd:
        httpd.shutdown()
    print("RESULT:", "FAIL" if failures else "OK", f"({len(failures)} failed)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
