# ============================================================================
# Common Attributes (通用屬性定義)
# ============================================================================

# Basic Position (基礎定位屬性)
COMMON_POSITION = [
    {"name": "x", "type": "number", "default": 0, "description": "X coordinate"},  # X 座標位置
    {"name": "y", "type": "number", "default": 0, "description": "Y coordinate"},  # Y 座標位置
    {"name": "rotation", "type": "number", "default": 0, "description": "Rotation angle (0-360)"},  # 旋轉角度
    {"name": "opacity", "type": "number", "default": 100, "description": "Opacity (0-100)"},  # 透明度
    {"name": "alignment", "type": "option", "options": ["cc", "cl", "cr", "tc", "tl", "tr", "bc", "bl", "br"],
     "default": "cc", "description": "Alignment"},  # 對齊方式
]

# 3D Position (3D 定位屬性)
COMMON_POSITION_3D = [
    {"name": "x", "type": "number", "default": 0, "description": "X coordinate"},  # X 座標位置
    {"name": "y", "type": "number", "default": 0, "description": "Y coordinate"},  # Y 座標位置
    {"name": "z", "type": "number", "default": 0, "description": "Z coordinate (3D)"},  # Z 座標位置
    {"name": "rotation", "type": "number", "default": 0, "description": "Z-axis rotation"},  # Z 軸旋轉角度
    {"name": "rotation_x", "type": "number", "default": 0, "description": "X-axis rotation"},  # X 軸旋轉角度
    {"name": "rotation_y", "type": "number", "default": 0, "description": "Y-axis rotation"},  # Y 軸旋轉角度
    {"name": "opacity", "type": "number", "default": 100, "description": "Opacity (0-100)"},  # 透明度
]

# Transform (變換屬性)
COMMON_TRANSFORM = [
    {"name": "gyro", "type": "number", "default": 0, "description": "Gyroscope effect (0-360)"},  # 陀螺儀效果
    {"name": "skew_x", "type": "number", "default": 0, "description": "X-axis skew"},  # X 軸傾斜
    {"name": "skew_y", "type": "number", "default": 0, "description": "Y-axis skew"},  # Y 軸傾斜
    {"name": "scale_x", "type": "number", "default": 100, "description": "X-axis scale (%)"},  # X 軸縮放
    {"name": "scale_y", "type": "number", "default": 100, "description": "Y-axis scale (%)"},  # Y 軸縮放
]

# Size (尺寸屬性)
COMMON_SIZE = [
    {"name": "width", "type": "number", "default": 100, "description": "Width"},  # 寬度
    {"name": "height", "type": "number", "default": 100, "description": "Height"},  # 高度
]

# Color (顏色屬性)
COMMON_COLOR = [
    {"name": "color", "type": "color", "default": "ffffff", "description": "Primary color"},  # 主顏色
    {"name": "color_dim", "type": "color", "default": "", "description": "Dim mode color"},  # 暗屏模式顏色
]

# Display (顯示屬性)
COMMON_DISPLAY = [
    {"name": "display", "type": "option", "options": ["bd", "b", "d"],
     "default": "bd", "description": "Display mode (bd=both, b=bright only, d=dim only)"},  # 顯示模式
]

# Interaction (互動屬性)
COMMON_INTERACTION = [
    {"name": "tap_action", "type": "text", "default": "",
     "description": "Tap action (script:func, app:package, sw_start_stop, sw_reset)"},  # 點擊動作
]

# Shadow (陰影效果)
COMMON_SHADOW = [
    {"name": "shadow", "type": "option", "options": ["", "Drop"], "default": "", "description": "Shadow type"},  # 陰影類型
    {"name": "w_color", "type": "color", "default": "000000", "description": "Shadow color"},  # 陰影顏色
    {"name": "w_distance", "type": "number", "default": 4, "description": "Shadow distance"},  # 陰影距離
    {"name": "w_opacity", "type": "number", "default": 100, "description": "Shadow opacity"},  # 陰影透明度
]

# Outline (描邊效果)
COMMON_OUTLINE = [
    {"name": "outline", "type": "option", "options": ["", "Outline"], "default": "", "description": "Outline type"},  # 描邊類型
    {"name": "o_color", "type": "color", "default": "000000", "description": "Outline color"},  # 描邊顏色
    {"name": "o_size", "type": "number", "default": 2, "description": "Outline size"},  # 描邊大小
    {"name": "o_opacity", "type": "number", "default": 100, "description": "Outline opacity"},  # 描邊透明度
]

# Shader (著色器效果)
COMMON_SHADER = [
    {"name": "shader", "type": "option",
     "options": ["", "Segment", "Radial", "GradientLinear", "GradientRadial", "Progress", "ProgressBetween", "HSV"],
     "default": "", "description": "Shader type"},  # 著色器類型
    {"name": "u_1", "type": "text", "default": "", "description": "Shader parameter 1"},  # 著色器參數1
    {"name": "u_2", "type": "text", "default": "", "description": "Shader parameter 2"},  # 著色器參數2
    {"name": "u_3", "type": "text", "default": "", "description": "Shader parameter 3"},  # 著色器參數3
    {"name": "u_4", "type": "text", "default": "", "description": "Shader parameter 4"},  # 著色器參數4
    {"name": "u_5", "type": "text", "default": "", "description": "Shader parameter 5"},  # 著色器參數5
]

# Blend Mode (混合模式)
COMMON_BLEND = [
    {"name": "blend_mode", "type": "option",
     "options": ["", "Multiply", "Screen", "Add", "Blend", "mode2", "mode3"],
     "default": "", "description": "Blend mode"},  # 混合模式
]

# Animation Scale (動畫縮放)
COMMON_ANIM_SCALE = [
    {"name": "anim_scale_x", "type": "text", "default": "", "description": "Animation scale X (bind to tweens.*)"},  # 動畫縮放X
    {"name": "anim_scale_y", "type": "text", "default": "", "description": "Animation scale Y (bind to tweens.*)"},  # 動畫縮放Y
]

# Protected (保護屬性)
COMMON_PROTECTED = [
    {"name": "protected", "type": "option", "options": ["", "y"], "default": "", "description": "Protected (prevent editing)"},  # 是否保護
]

# 導出所有 COMMON 屬性
__all__ = [
    'COMMON_POSITION',
    'COMMON_POSITION_3D',
    'COMMON_TRANSFORM',
    'COMMON_SIZE',
    'COMMON_COLOR',
    'COMMON_DISPLAY',
    'COMMON_INTERACTION',
    'COMMON_SHADOW',
    'COMMON_OUTLINE',
    'COMMON_SHADER',
    'COMMON_BLEND',
    'COMMON_ANIM_SCALE',
    'COMMON_PROTECTED',
]
