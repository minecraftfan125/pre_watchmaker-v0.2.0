-- 全域環境白名單沙盒：移除危險 API，防止沙盒逃逸
-- 載入順序：wm_api.lua → wm_sandbox.lua → 使用者程式碼

-- 1. lupa Python 橋（可直接呼叫任意 Python，最高優先）
python = nil

-- 2. 在移除 package 前先清空 loaded 快取，防止 package.loaded.os 繞過
if package then
    local _dangerous = { "io", "os", "debug" }
    for _, name in ipairs(_dangerous) do
        package.loaded[name] = nil
        if package.preload then
            package.preload[name] = nil
        end
    end
end

-- 3. 危險標準庫模組
io      = nil   -- 檔案讀寫
os      = nil   -- 行程執行、shell、環境變數
debug   = nil   -- 可繞過 Lua 限制（getupvalue、sethook、getregistry 等）
package = nil   -- 含 loaded / path / C loader，移除後無法再 require 新模組

-- 4. 動態程式碼載入
require    = nil   -- 載入模組
dofile     = nil   -- 從檔案執行 Lua
loadfile   = nil   -- 從檔案載入 Lua chunk
load       = nil   -- 從字串/函式載入 Lua chunk
loadstring = nil   -- Lua 5.1 / LuaJIT 別名（load 的舊版）
