# 圖書館人生

蓋一座自己的圖書館：選地點和館藏特色、讀完書上架、上班整理新書，賺金幣加蓋樓層。

線上玩：https://ritakiros.github.io/library-life/

- 這個小遊戲是用 Claude 做的，整個遊戲就是一個 `index.html`，3D 畫面用 three.js。
- 進度存在你的瀏覽器裡（localStorage），換瀏覽器或清除資料就會重來。
- 單機版沒有 AI：每個書區的「推薦書單」是內建的精選繁體中文書單（16 類、每類 8–14 本，書名與作者都對照過書店書目），勾選想要的書按「列入館藏」就行，也可以自己加一本書。
- 每本書都有「北市圖館藏 ↗」和「博客來 ↗」連結，可以直接查臺北市立圖書館哪裡借得到。
- 在 Claude 裡打開時，會改用 AI 推薦書單；「看別人蓋的圖書館」只有在 Claude 裡才看得到。
- 測試：`python3 tests/test_booklist.py`（需要 `pip install playwright && playwright install chromium`）。

也放在 [島嶼上線](https://islelive.com)。
