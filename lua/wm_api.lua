-- WatchMaker API 存根（lupa 預覽環境）
-- {tag} 語法由 Python _preprocess_tags() 轉換為 _WM_TAGS["tag"] 存取
-- 使用者直接寫 __tagname__ 不具任何特殊意義

_WM_TAGS = {}

-- 支援 wm_tag("{dh}") 及 wm_tag("dh") 兩種呼叫方式
function wm_tag(tag_name)
    local key = tag_name:match("^{(.+)}$") or tag_name
    if _WM_TAGS and _WM_TAGS[key] ~= nil then
        return _WM_TAGS[key]
    end
    return nil
end

-- no-op 存根（預覽環境中無副作用）
function wm_action(...)      end
function wm_schedule(...)    end
function wm_unschedule_all() end
function wm_vibrate(...)     end
function wm_sfx(...)         end
function wm_transition(...)  end
function wm_anim_set(...)    end
function wm_anim_start(...)  end

-- 預覽預設值
is_bright = true
tweens = {}

-- on_hour / on_minute / on_second / on_millisecond 等 callback
-- 由 base script 自行定義，此處不預建存根以免遮蔽使用者定義
