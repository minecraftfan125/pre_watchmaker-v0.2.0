from .common import (
    COMMON_POSITION,
    COMMON_POSITION_3D,
    COMMON_TRANSFORM,
    COMMON_SIZE,
    COMMON_COLOR,
    COMMON_DISPLAY,
    COMMON_INTERACTION,
    COMMON_SHADOW,
    COMMON_OUTLINE,
    COMMON_SHADER,
    COMMON_BLEND,
    COMMON_ANIM_SCALE,
    COMMON_PROTECTED,
)

# ============================================================================
# Component Attributes (元件屬性定義)
# ============================================================================

# ========================================================================
# Group (群組)
# ========================================================================
group = [
    {"name": "name", "type": "text", "default": "Group", "description": "Layer name"},  # 群組名稱
    *COMMON_POSITION,
    *COMMON_TRANSFORM,
    *COMMON_DISPLAY,
]

# ========================================================================
# Text (文字)
# ========================================================================
text = [
    {"name": "name", "type": "text", "default": "Text Layer", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_TRANSFORM,
    {"name": "text", "type": "text", "default": "{dh}:{dmz}", "description": "Text content (supports tags and expressions)"},  # 文字內容
    {"name": "text_size", "type": "number", "default": 40, "description": "Font size (pixels)"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Regular", "description": "Font name"},  # 字體名稱
    {"name": "transform", "type": "option", "options": ["n", "u", "l", "c"],
     "default": "n", "description": "Text transform (n=none, u=uppercase, l=lowercase, c=capitalize)"},  # 文字變換
    *COMMON_COLOR,
    *COMMON_DISPLAY,
    *COMMON_INTERACTION,
    *COMMON_ANIM_SCALE,
    *COMMON_SHADOW,
    *COMMON_OUTLINE,
    *COMMON_SHADER,
    *COMMON_BLEND,
]

# ========================================================================
# Text Animation (文字動畫)
# ========================================================================
text_animation = [
    {"name": "name", "type": "text", "default": "Text Animation", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_TRANSFORM,
    {"name": "text", "type": "text", "default": "Hello", "description": "Text content"},  # 文字內容
    {"name": "text_size", "type": "number", "default": 40, "description": "Font size"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Regular", "description": "Font name"},  # 字體名稱
    {"name": "transform", "type": "option", "options": ["n", "u", "l", "c"], "default": "n", "description": "Text transform"},  # 文字變換
    *COMMON_COLOR,
    # Animation properties (動畫屬性)
    {"name": "anim_in", "type": "option",
     "options": ["None", "Pulse", "FadeIn", "SlideLeft", "SlideRight", "SlideUp", "SlideDown", "ZoomIn", "Flip"],
     "default": "None", "description": "Enter animation"},  # 進入動畫
    {"name": "anim_out", "type": "option",
     "options": ["None", "Pulse", "FadeOut", "SlideLeft", "SlideRight", "SlideUp", "SlideDown", "ZoomOut", "Flip"],
     "default": "None", "description": "Exit animation"},  # 離開動畫
    {"name": "delay_start", "type": "number", "default": 0.0, "description": "Start delay (seconds)"},  # 延遲開始
    {"name": "dur_in", "type": "number", "default": 1.0, "description": "Enter animation duration (seconds)"},  # 進入動畫持續時間
    {"name": "dur_on", "type": "number", "default": 0.5, "description": "Display duration (seconds)"},  # 顯示持續時間
    {"name": "dur_out", "type": "number", "default": 1.0, "description": "Exit animation duration (seconds)"},  # 離開動畫持續時間
    {"name": "dur_off", "type": "number", "default": 0.0, "description": "Hidden duration (seconds)"},  # 隱藏持續時間
    {"name": "repeat_count", "type": "number", "default": 1, "description": "Repeat count (-1=infinite)"},  # 重複次數
    {"name": "restart_on_load", "type": "option", "options": ["Y", "N"], "default": "N", "description": "Restart on load"},  # 載入時重新開始
    {"name": "restart_on_bright", "type": "option", "options": ["Y", "N"], "default": "N", "description": "Restart on bright"},  # 亮屏時重新開始
    {"name": "restart_text_change", "type": "option", "options": ["Y", "N"], "default": "N", "description": "Restart on text change"},  # 文字變更時重新開始
    *COMMON_DISPLAY,
    *COMMON_SHADOW,
    *COMMON_OUTLINE,
]

# ========================================================================
# Text Curved (曲線文字)
# ========================================================================
text_curved = [
    {"name": "name", "type": "text", "default": "Curved Text", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "text", "type": "text", "default": "Curved Text", "description": "Text content"},  # 文字內容
    {"name": "text_size", "type": "number", "default": 30, "description": "Font size"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Regular", "description": "Font name"},  # 字體名稱
    {"name": "transform", "type": "option", "options": ["n", "u", "l", "c"], "default": "n", "description": "Text transform"},  # 文字變換
    {"name": "radius", "type": "number", "default": 150, "description": "Curve radius"},  # 曲線半徑
    {"name": "curve_dir", "type": "option", "options": ["Up", "Down"], "default": "Up", "description": "Curve direction"},  # 曲線方向
    *COMMON_COLOR,
    *COMMON_DISPLAY,
    *COMMON_SHADOW,
    *COMMON_OUTLINE,
]

# ========================================================================
# Text Ring (環形文字)
# ========================================================================
text_ring = [
    {"name": "name", "type": "text", "default": "Text Ring", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "text_size", "type": "number", "default": 30, "description": "Font size"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Regular", "description": "Font name"},  # 字體名稱
    {"name": "transform", "type": "option", "options": ["n", "u", "l", "c"], "default": "n", "description": "Text transform"},  # 文字變換
    {"name": "radius", "type": "number", "default": 200, "description": "Ring radius"},  # 環形半徑
    {"name": "ring_type", "type": "option",
     "options": ["1-12", "1-24", "1-60", "0-11", "0-23", "0-59", "Custom"],
     "default": "1-12", "description": "Ring type"},  # 環形類型
    {"name": "show_every", "type": "number", "default": 1, "description": "Show interval"},  # 顯示間隔
    {"name": "hide_text", "type": "text", "default": "", "description": "Hidden text"},  # 隱藏的文字
    {"name": "rotated_text", "type": "option", "options": ["ru", "rd", "n"],
     "default": "ru", "description": "Text rotation (ru=rotate up, rd=rotate down, n=none)"},  # 文字旋轉
    {"name": "squarify", "type": "option", "options": ["0", "1"], "default": "0", "description": "Squarify"},  # 方形化
    {"name": "color", "type": "color", "default": "ffffff", "description": "Color"},  # 顏色
    *COMMON_DISPLAY,
    *COMMON_SHADOW,
    *COMMON_OUTLINE,
]

# ========================================================================
# Image (圖片)
# ========================================================================
image = [
    {"name": "name", "type": "text", "default": "Image Layer", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_TRANSFORM,
    *COMMON_SIZE,
    {"name": "path", "type": "text", "default": "", "description": "Image path"},  # 圖片路徑
    {"name": "color", "type": "color", "default": "ffffff", "description": "Tint color"},  # 著色顏色
    *COMMON_DISPLAY,
    *COMMON_INTERACTION,
    *COMMON_ANIM_SCALE,
    *COMMON_SHADOW,
    *COMMON_SHADER,
    *COMMON_BLEND,
    *COMMON_PROTECTED,
]

# ========================================================================
# Image GIF (動態圖片)
# ========================================================================
image_gif = [
    {"name": "name", "type": "text", "default": "Animated GIF", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "path", "type": "text", "default": "", "description": "Image path (use ` to separate multiple images)"},  # 圖片路徑
    {"name": "gif_delay", "type": "number", "default": 100, "description": "Frame delay (milliseconds)"},  # 幀延遲
    *COMMON_DISPLAY,
]

# ========================================================================
# Image Cutout (圖片遮罩)
# ========================================================================
image_cutout = [
    {"name": "name", "type": "text", "default": "Image Cutout", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "path", "type": "text", "default": "", "description": "Image path"},  # 圖片路徑
    {"name": "text", "type": "text", "default": "Text", "description": "Mask text"},  # 遮罩文字
    {"name": "text_size", "type": "number", "default": 50, "description": "Font size"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Bold", "description": "Font name"},  # 字體名稱
    {"name": "transform", "type": "option", "options": ["n", "u", "l", "c"], "default": "n", "description": "Text transform"},  # 文字變換
    *COMMON_DISPLAY,
]

# ========================================================================
# Video (影片)
# ========================================================================
video = [
    {"name": "name", "type": "text", "default": "Video Layer", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "path", "type": "text", "default": "", "description": "Video path (.mp4)"},  # 影片路徑
    *COMMON_DISPLAY,
]

# ========================================================================
# Shape (形狀)
# ========================================================================
shape = [
    {"name": "name", "type": "text", "default": "Shape Layer", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_TRANSFORM,
    *COMMON_SIZE,
    {"name": "shape", "type": "option",
     "options": ["Square", "Circle", "Triangle", "Pentagon", "Hexagon", "Star", "Heart"],
     "default": "Square", "description": "Shape type"},  # 形狀類型
    {"name": "color", "type": "color", "default": "ffffff", "description": "Fill color"},  # 填充顏色
    *COMMON_DISPLAY,
    *COMMON_INTERACTION,
    *COMMON_SHADOW,
    *COMMON_OUTLINE,
    *COMMON_SHADER,
    *COMMON_BLEND,
]

# ========================================================================
# Rounded (圓角矩形)
# ========================================================================
rounded = [
    {"name": "name", "type": "text", "default": "Rounded Shape", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "radius", "type": "number", "default": 20, "description": "Corner radius"},  # 圓角半徑
    {"name": "corner_type", "type": "option", "options": ["0", "1", "2", "3"], "default": "1", "description": "Corner type"},  # 圓角類型
    {"name": "color", "type": "color", "default": "ffffff", "description": "Fill color"},  # 填充顏色
    *COMMON_DISPLAY,
    *COMMON_SHADER,
]

# ========================================================================
# Ring (圓環)
# ========================================================================
ring = [
    {"name": "name", "type": "text", "default": "Ring", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "radius_outer", "type": "number", "default": 180, "description": "Outer radius"},  # 外圓半徑
    {"name": "radius_inner", "type": "number", "default": 140, "description": "Inner radius"},  # 內圓半徑
    {"name": "radius", "type": "number", "default": 10, "description": "Corner radius"},  # 圓角半徑
    {"name": "angle", "type": "text", "default": "{drss}", "description": "Current angle (0-360, supports tags)"},  # 當前角度
    {"name": "angle_total", "type": "number", "default": 360, "description": "Total angle"},  # 總角度
    {"name": "is_clockwise", "type": "option", "options": ["Y", "N"], "default": "Y", "description": "Clockwise"},  # 是否順時針
    {"name": "color", "type": "color", "default": "00ff00", "description": "Primary color"},  # 主顏色
    {"name": "color2", "type": "color", "default": "0000ff", "description": "Secondary color"},  # 第二顏色
    {"name": "color3", "type": "color", "default": "333333", "description": "Background color"},  # 背景顏色
    {"name": "outside_opacity", "type": "number", "default": 50, "description": "Outside opacity"},  # 外圈透明度
    *COMMON_DISPLAY,
]

# ========================================================================
# Ring Image (圖片圓環)
# ========================================================================
ring_image = [
    {"name": "name", "type": "text", "default": "Ring Image", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "radius", "type": "number", "default": 150, "description": "Radius"},  # 半徑
    {"name": "pct_complete", "type": "text", "default": "50", "description": "Percent complete (0-100, supports expressions)"},  # 完成百分比
    {"name": "shape", "type": "text", "default": "octagon1", "description": "Shape style"},  # 形狀樣式
    {"name": "color", "type": "color", "default": "e00c25", "description": "Primary color"},  # 主顏色
    {"name": "color2", "type": "color", "default": "383838", "description": "Background color"},  # 背景顏色
    {"name": "outside_opacity", "type": "number", "default": 50, "description": "Outside opacity"},  # 外圈透明度
    *COMMON_DISPLAY,
]

# ========================================================================
# Progress (進度條)
# ========================================================================
progress = [
    {"name": "name", "type": "text", "default": "Progress Bar", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "pct_complete", "type": "text", "default": "50", "description": "Percent complete (0-100, supports expressions)"},  # 完成百分比
    {"name": "margin", "type": "number", "default": 8, "description": "Margin"},  # 邊距
    {"name": "radius", "type": "number", "default": 20, "description": "Corner radius"},  # 圓角半徑
    {"name": "end_style", "type": "option", "options": ["round", "square"], "default": "round", "description": "End style"},  # 端點樣式
    {"name": "corner_type", "type": "option", "options": ["0", "1", "2", "3"], "default": "1", "description": "Corner type"},  # 圓角類型
    {"name": "color", "type": "color", "default": "00ff00", "description": "Progress color"},  # 進度顏色
    {"name": "color2", "type": "color", "default": "00aa00", "description": "Progress secondary color"},  # 進度第二顏色
    {"name": "color3", "type": "color", "default": "444444", "description": "Background color"},  # 背景顏色
    {"name": "color4", "type": "color", "default": "666666", "description": "Background secondary color"},  # 背景第二顏色
    *COMMON_DISPLAY,
]

# ========================================================================
# Progress Image (圖片進度條)
# ========================================================================
progress_image = [
    {"name": "name", "type": "text", "default": "Progress Image", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "pct_complete", "type": "text", "default": "50", "description": "Percent complete"},  # 完成百分比
    {"name": "shape", "type": "text", "default": "bar_rounded1", "description": "Shape style"},  # 形狀樣式
    {"name": "repeat_count", "type": "number", "default": 5, "description": "Repeat count"},  # 重複次數
    {"name": "color", "type": "color", "default": "e00c25", "description": "Primary color"},  # 主顏色
    {"name": "color2", "type": "color", "default": "383838", "description": "Background color"},  # 背景顏色
    {"name": "outside_opacity", "type": "number", "default": 50, "description": "Outside opacity"},  # 外圈透明度
    *COMMON_DISPLAY,
]

# ========================================================================
# Chart (圖表)
# ========================================================================
chart = [
    {"name": "name", "type": "text", "default": "Chart", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "chart_type", "type": "option", "options": ["line", "bar"], "default": "line", "description": "Chart type"},  # 圖表類型
    {"name": "data_points", "type": "text", "default": "{shr_8};{shr_7};{shr_6};{shr_5};{shr_4};{shr_3};{shr_2};{shr_1};{shr}",
     "description": "Data points (semicolon separated, supports tags)"},  # 數據點
    {"name": "line_width", "type": "number", "default": 5, "description": "Line width"},  # 線條寬度
    {"name": "marker_size", "type": "number", "default": 10, "description": "Marker size"},  # 標記大小
    {"name": "bar_thickness", "type": "number", "default": 80, "description": "Bar thickness (%)"},  # 長條寬度
    {"name": "radius", "type": "number", "default": 10, "description": "Corner radius"},  # 圓角半徑
    {"name": "corner_type", "type": "option", "options": ["0", "1"], "default": "1", "description": "Corner type"},  # 圓角類型
    {"name": "chart_group", "type": "number", "default": 1, "description": "Chart group"},  # 圖表群組
    {"name": "color", "type": "color", "default": "38747f", "description": "Line/bar color"},  # 線條/長條顏色
    {"name": "color2", "type": "color", "default": "38747f", "description": "Fill color"},  # 填充顏色
    {"name": "color3", "type": "color", "default": "2ae4fe", "description": "Marker color"},  # 標記顏色
    {"name": "color4", "type": "color", "default": "ffffff", "description": "Label color"},  # 標籤顏色
    {"name": "top_opacity", "type": "number", "default": 100, "description": "Top opacity"},  # 頂部透明度
    {"name": "bottom_opacity", "type": "number", "default": 0, "description": "Bottom opacity"},  # 底部透明度
    {"name": "labels", "type": "text", "default": "", "description": "Labels config"},  # 標籤配置
    {"name": "lines", "type": "text", "default": "", "description": "Lines config"},  # 線條配置
    *COMMON_DISPLAY,
]

# ========================================================================
# Markers (自由標記)
# ========================================================================
markers = [
    {"name": "name", "type": "text", "default": "Markers", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "radius", "type": "number", "default": 200, "description": "Radius"},  # 半徑
    {"name": "m_width", "type": "number", "default": 10, "description": "Marker width"},  # 標記寬度
    {"name": "m_height", "type": "number", "default": 35, "description": "Marker height"},  # 標記高度
    {"name": "m_count", "type": "number", "default": 60, "description": "Marker count"},  # 標記數量
    {"name": "shape", "type": "option", "options": ["Square", "Circle", "Triangle"],
     "default": "Square", "description": "Marker shape"},  # 標記形狀
    {"name": "squarify", "type": "option", "options": ["0", "1"], "default": "0", "description": "Squarify"},  # 方形化
    {"name": "color", "type": "color", "default": "ffffff", "description": "Marker color"},  # 標記顏色
    *COMMON_DISPLAY,
    *COMMON_SHADOW,
]

# ========================================================================
# Markers HM (時分標記)
# ========================================================================
markers_hm = [
    {"name": "name", "type": "text", "default": "Hour Minute Markers", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "radius", "type": "number", "default": 256, "description": "Radius"},  # 半徑
    {"name": "m_hour", "type": "option",
     "options": ["None", "Small", "Medium", "Large", "Triangle", "Circle", "Diamond"],
     "default": "Medium", "description": "Hour marker style"},  # 小時標記樣式
    {"name": "m_minute", "type": "option",
     "options": ["None", "Small", "Medium", "Large", "Triangle", "Circle", "Diamond"],
     "default": "Small", "description": "Minute marker style"},  # 分鐘標記樣式
    {"name": "squarify", "type": "option", "options": ["0", "1"], "default": "0", "description": "Squarify"},  # 方形化
    {"name": "color", "type": "color", "default": "ffffff", "description": "Marker color"},  # 標記顏色
    *COMMON_DISPLAY,
    *COMMON_ANIM_SCALE,
]

# ========================================================================
# Tachymeter (測速計)
# ========================================================================
tachy = [
    {"name": "name", "type": "text", "default": "Tachymeter", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "radius", "type": "number", "default": 230, "description": "Radius"},  # 半徑
    {"name": "text", "type": "text", "default": "TACHYMETER", "description": "Title text"},  # 標題文字
    {"name": "speeds", "type": "text", "default": "400,300,240,200,180,160,140,120,110,100,95,90,85,80,75,70,65,60",
     "description": "Speed values (comma separated)"},  # 速度值
    {"name": "text_size", "type": "number", "default": 25, "description": "Font size"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Regular", "description": "Font name"},  # 字體名稱
    {"name": "transform", "type": "option", "options": ["n", "u", "l"], "default": "n", "description": "Text transform"},  # 文字變換
    {"name": "rotated_text", "type": "option", "options": ["ru", "rd", "n"], "default": "ru", "description": "Text rotation"},  # 文字旋轉
    {"name": "squarify", "type": "option", "options": ["0", "1"], "default": "0", "description": "Squarify"},  # 方形化
    {"name": "m_width", "type": "number", "default": 10, "description": "Marker width"},  # 標記寬度
    {"name": "m_height", "type": "number", "default": 10, "description": "Marker height"},  # 標記高度
    {"name": "m_hour", "type": "option", "options": ["None", "Triangle", "Circle", "Diamond"], "default": "None", "description": "Hour marker"},  # 小時標記
    {"name": "m_minute", "type": "option", "options": ["None", "Triangle", "Circle", "Diamond"], "default": "Triangle", "description": "Minute marker"},  # 分鐘標記
    {"name": "color", "type": "color", "default": "ffffff", "description": "Color"},  # 顏色
    *COMMON_DISPLAY,
]

# ========================================================================
# Series (數據系列)
# ========================================================================
series = [
    {"name": "name", "type": "text", "default": "Series", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    {"name": "series", "type": "option",
     "options": ["dm", "ds", "dh", "dd", "dn", "dy", "ddw"],
     "default": "dm", "description": "Series type"},  # 系列類型
    {"name": "orientation", "type": "option", "options": ["v", "h"], "default": "v", "description": "Orientation (v=vertical, h=horizontal)"},  # 方向
    {"name": "current_pos", "type": "option", "options": ["t", "m", "b"], "default": "m", "description": "Current position (t=top, m=middle, b=bottom)"},  # 當前值位置
    {"name": "spacing", "type": "number", "default": 10, "description": "Spacing"},  # 間距
    {"name": "text_size", "type": "number", "default": 40, "description": "Current value font size"},  # 當前值字體大小
    {"name": "font", "type": "text", "default": "Roboto-Bold", "description": "Current value font"},  # 當前值字體
    {"name": "color", "type": "color", "default": "ffffff", "description": "Current value color"},  # 當前值顏色
    {"name": "text_size2", "type": "number", "default": 30, "description": "Other values font size"},  # 其他值字體大小
    {"name": "font2", "type": "text", "default": "Roboto-Regular", "description": "Other values font"},  # 其他值字體
    {"name": "color2", "type": "color", "default": "888888", "description": "Other values color"},  # 其他值顏色
    {"name": "transform", "type": "option", "options": ["n", "u", "l"], "default": "n", "description": "Text transform"},  # 文字變換
    *COMMON_DISPLAY,
    *COMMON_SHADOW,
    *COMMON_OUTLINE,
]

# ========================================================================
# Map (地圖)
# ========================================================================
map = [
    {"name": "name", "type": "text", "default": "Map", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "lat", "type": "text", "default": "{alat}", "description": "Latitude (supports tags or variables)"},  # 緯度
    {"name": "lon", "type": "text", "default": "{alon}", "description": "Longitude (supports tags or variables)"},  # 經度
    {"name": "map_zoom", "type": "number", "default": 16, "description": "Zoom level (1-20)"},  # 縮放等級
    {"name": "map_scale", "type": "number", "default": 100, "description": "Scale (%)"},  # 縮放比例
    *COMMON_DISPLAY,
]

# ========================================================================
# Gallery 2D (相簿/幻燈片)
# ========================================================================
gallery_2d = [
    {"name": "name", "type": "text", "default": "Gallery", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    {"name": "dur_on", "type": "number", "default": 1.0, "description": "Image display duration (seconds)"},  # 每張圖片顯示時間
    *COMMON_DISPLAY,
    *COMMON_PROTECTED,
]

# ========================================================================
# 3D Model (3D 模型)
# ========================================================================
model_3d = [
    {"name": "name", "type": "text", "default": "3D Model", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION_3D,
    {"name": "model", "type": "option",
     "options": ["cube", "sphere", "cylinder", "cone", "capsule", "torus"],
     "default": "cube", "description": "Model type"},  # 模型類型
    {"name": "scale_x", "type": "number", "default": 100, "description": "X-axis scale"},  # X 軸縮放
    {"name": "scale_y", "type": "number", "default": 100, "description": "Y-axis scale"},  # Y 軸縮放
    {"name": "scale_z", "type": "number", "default": 100, "description": "Z-axis scale"},  # Z 軸縮放
    {"name": "gyro", "type": "number", "default": 30, "description": "Gyroscope effect"},  # 陀螺儀效果
    {"name": "color", "type": "color", "default": "ffffff", "description": "Model color"},  # 模型顏色
    *COMMON_DISPLAY,
]

# ========================================================================
# 3D Text (3D 文字)
# ========================================================================
text_3d = [
    {"name": "name", "type": "text", "default": "3D Text", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION_3D,
    {"name": "text", "type": "text", "default": "3D", "description": "Text content"},  # 文字內容
    {"name": "text_size", "type": "number", "default": 100, "description": "Font size"},  # 字體大小
    {"name": "font", "type": "text", "default": "Roboto-Bold", "description": "Font name"},  # 字體名稱
    {"name": "scale_x", "type": "number", "default": 100, "description": "X-axis scale"},  # X 軸縮放
    {"name": "scale_y", "type": "number", "default": 100, "description": "Y-axis scale"},  # Y 軸縮放
    {"name": "scale_z", "type": "number", "default": 100, "description": "Z-axis scale"},  # Z 軸縮放
    {"name": "spacing_letter", "type": "number", "default": 5, "description": "Letter spacing"},  # 字母間距
    {"name": "spacing_word", "type": "number", "default": 25, "description": "Word spacing"},  # 單詞間距
    {"name": "explode", "type": "number", "default": 100, "description": "Explode effect"},  # 爆炸效果
    {"name": "color", "type": "color", "default": "ffffff", "description": "Text color"},  # 文字顏色
    *COMMON_DISPLAY,
]

# ========================================================================
# Camera (3D 攝影機)
# ========================================================================
camera = [
    {"name": "name", "type": "text", "default": "Camera", "description": "Layer name"},  # 圖層名稱
    {"name": "x", "type": "number", "default": 0, "description": "X coordinate"},  # X 座標
    {"name": "y", "type": "number", "default": 0, "description": "Y coordinate"},  # Y 座標
    {"name": "z", "type": "number", "default": -320, "description": "Z coordinate"},  # Z 座標
    {"name": "look_x", "type": "number", "default": 0, "description": "Look at X"},  # 注視點 X
    {"name": "look_y", "type": "number", "default": 0, "description": "Look at Y"},  # 注視點 Y
    {"name": "look_z", "type": "number", "default": 0, "description": "Look at Z"},  # 注視點 Z
    {"name": "field_of_view", "type": "number", "default": 60, "description": "Field of view"},  # 視野角度
    {"name": "near_plane", "type": "number", "default": 1, "description": "Near clipping plane"},  # 近裁剪面
    {"name": "far_plane", "type": "number", "default": 1000, "description": "Far clipping plane"},  # 遠裁剪面
    *COMMON_DISPLAY,
]

# ========================================================================
# Light Direction (方向光源)
# ========================================================================
light_dir = [
    {"name": "name", "type": "text", "default": "Light", "description": "Layer name"},  # 圖層名稱
    {"name": "x", "type": "number", "default": 0, "description": "X direction"},  # X 方向
    {"name": "y", "type": "number", "default": -1, "description": "Y direction"},  # Y 方向
    {"name": "z", "type": "number", "default": -1, "description": "Z direction"},  # Z 方向
    {"name": "color", "type": "color", "default": "ffffff", "description": "Light color"},  # 光源顏色
    {"name": "intensity", "type": "number", "default": 100, "description": "Light intensity"},  # 光源強度
]

# ========================================================================
# Complication (Wear OS 複雜功能)
# ========================================================================
complication = [
    {"name": "name", "type": "text", "default": "Complication", "description": "Layer name"},  # 圖層名稱
    *COMMON_POSITION,
    *COMMON_SIZE,
    *COMMON_DISPLAY,
]


# ============================================================================
# Shader Parameters (著色器參數說明)
# ============================================================================
SHADER_PARAMS = {
    "Segment": {
        "u_1": "Progress value (0-360, supports tags like {drm})",  # 進度值
        "u_2": "Opacity (0-100)",  # 透明度
        "u_3": "Gradient width",  # 漸變寬度
    },
    "Radial": {
        "u_1": "Progress value (0-360)",  # 進度值
    },
    "GradientLinear": {
        "u_1": "Start color (6-digit hex)",  # 起始顏色
        "u_2": "End color (6-digit hex)",  # 結束顏色
        "u_3": "Start position (0-100)",  # 起始位置
        "u_4": "End position (0-100)",  # 結束位置
    },
    "GradientRadial": {
        "u_1": "Center color (6-digit hex)",  # 中心顏色
        "u_2": "Edge color (6-digit hex)",  # 邊緣顏色
        "u_3": "Radius (0-100)",  # 半徑
    },
    "Progress": {
        "u_1": "Progress value",  # 進度值
        "u_2": "Minimum value",  # 最小值
        "u_3": "Maximum value",  # 最大值
        "u_4": "Gradient width",  # 漸變寬度
    },
    "ProgressBetween": {
        "u_1": "Start progress",  # 起始進度
        "u_2": "End progress",  # 結束進度
        "u_3": "Minimum value",  # 最小值
        "u_4": "Maximum value",  # 最大值
        "u_5": "Gradient width",  # 漸變寬度
    },
    "HSV": {
        "u_1": "Hue offset (0-360)",  # 色相偏移
        "u_2": "Saturation offset (-100 to 100)",  # 飽和度偏移
        "u_3": "Value offset (-100 to 100)",  # 明度偏移
    },
}


# ============================================================================
# Animation Types (動畫類型說明)
# ============================================================================
ANIMATION_TYPES = {
    "in": ["None", "Pulse", "FadeIn", "SlideLeft", "SlideRight", "SlideUp", "SlideDown", "ZoomIn", "Flip",
           "Bounce", "Rotate", "Swing", "Wobble", "Flash", "RubberBand", "ShakeX", "ShakeY"],
    "out": ["None", "Pulse", "FadeOut", "SlideLeft", "SlideRight", "SlideUp", "SlideDown", "ZoomOut", "Flip",
            "Bounce", "Rotate", "Swing", "Wobble", "Flash", "RubberBand", "ShakeX", "ShakeY"],
}


# ============================================================================
# Tap Actions (點擊動作說明)
# ============================================================================
TAP_ACTIONS = {
    "script": "Execute Lua script, format: script:function_name() or script:var=value",  # 執行 Lua 腳本
    "app": "Open application, format: app:com.package.name",  # 開啟應用程式
    "sw_start_stop": "Stopwatch start/stop",  # 碼錶 開始/停止
    "sw_reset": "Stopwatch reset",  # 碼錶 重設
    "color_next": "Switch to next color",  # 切換到下一個顏色
    "color_prev": "Switch to previous color",  # 切換到上一個顏色
}


# ============================================================================
# Helper Functions (輔助函數)
# ============================================================================
def get_shader_params(shader_type):
    """Get parameter descriptions for a shader type"""  # 獲取指定著色器的參數說明
    return SHADER_PARAMS.get(shader_type, {})


__all__ = [
    # Component types
    'group',
    'text',
    'text_animation',
    'text_curved',
    'text_ring',
    'image',
    'image_gif',
    'image_cutout',
    'video',
    'shape',
    'rounded',
    'ring',
    'ring_image',
    'progress',
    'progress_image',
    'chart',
    'markers',
    'markers_hm',
    'tachy',
    'series',
    'map',
    'gallery_2d',
    'model_3d',
    'text_3d',
    'camera',
    'light_dir',
    'complication',
    # Other exports
    'SHADER_PARAMS',
    'ANIMATION_TYPES',
    'TAP_ACTIONS',
    'get_shader_params',
]
