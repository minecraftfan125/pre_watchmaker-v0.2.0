"""Script View - Lua 腳本編輯器

使用 QScintilla 提供 Lua 語法高亮和自動完成功能。
支援 WatchMaker Lua API。
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSplitter, QListWidget, QListWidgetItem,
                             QFrame, QTextEdit, QScrollArea, QShortcut)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QKeySequence
from PyQt5.Qsci import QsciScintilla, QsciLexerLua, QsciAPIs

from lua_syntax_checker import LuaSyntaxChecker, LuaSyntaxError, ErrorSeverity


def load_style():
    """載入腳本編輯器樣式"""
    style_path = os.path.join(os.path.dirname(__file__), "style", "script_view.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Style file not found: {style_path}")
        return ""


# WatchMaker Lua API 定義
WATCHMAKER_API = {
    # 核心函數
    'wm_schedule': {
        'signature': "wm_schedule(config)",
        'description': "Manage animations and timed events. config is a table containing action, tween, from, to, duration, easing properties.",
        'example': "wm_schedule { action='tween', tween='rotation', from=0, to=360, duration=1, easing='outQuad' }"
    },
    'wm_unschedule_all': {
        'signature': "wm_unschedule_all()",
        'description': "Cancel all scheduled animations or events.",
        'example': "wm_unschedule_all()"
    },
    'wm_action': {
        'signature': "wm_action(action_name)",
        'description': "Execute various watch control actions like media playback, volume, weather update, etc.",
        'example': "wm_action('media_play_pause')"
    },
    'wm_tag': {
        'signature': "wm_tag(tag_name)",
        'description': "Return the dynamic value of a WatchMaker tag.",
        'example': "local hour = wm_tag('{dh}')"
    },
    'wm_vibrate': {
        'signature': "wm_vibrate(duration, repeat)",
        'description': "Trigger haptic feedback. duration in milliseconds, repeat is the repeat count.",
        'example': "wm_vibrate(100, 2)"
    },
    'wm_sfx': {
        'signature': "wm_sfx(filename)",
        'description': "Play an MP3 file from the sfx folder.",
        'example': "wm_sfx('click.mp3')"
    },
    'wm_transition': {
        'signature': "wm_transition(effect)",
        'description': "Execute screen transition effects.",
        'example': "wm_transition('fade')"
    },
    'wm_anim_set': {
        'signature': "wm_anim_set(layer, property, value)",
        'description': "Configure animation properties for a layer.",
        'example': "wm_anim_set('layer1', 'opacity', 0.5)"
    },
    'wm_anim_start': {
        'signature': "wm_anim_start(layer)",
        'description': "Start animation on the specified layer.",
        'example': "wm_anim_start('layer1')"
    },

    # Callback Functions
    'on_hour': {
        'signature': "function on_hour(h)",
        'description': "Executes every hour. h is the current hour (0-23).",
        'example': "function on_hour(h)\n  print('Hour: ' .. h)\nend"
    },
    'on_minute': {
        'signature': "function on_minute(h, m)",
        'description': "Executes every minute. h is hour, m is minute.",
        'example': "function on_minute(h, m)\n  print(h .. ':' .. m)\nend"
    },
    'on_second': {
        'signature': "function on_second(h, m, s)",
        'description': "Executes every second. h is hour, m is minute, s is second.",
        'example': "function on_second(h, m, s)\n  var_s_time = h * 3600 + m * 60 + s\nend"
    },
    'on_millisecond': {
        'signature': "function on_millisecond(dt)",
        'description': "Executes every millisecond. dt is delta time in ms. Use var_ms_ prefix for variables.",
        'example': "function on_millisecond(dt)\n  var_ms_counter = var_ms_counter + dt\nend"
    },
    'on_display_bright': {
        'signature': "function on_display_bright()",
        'description': "Executes when the watch screen turns on (becomes bright).",
        'example': "function on_display_bright()\n  wm_anim_start('intro')\nend"
    },
    'on_display_not_bright': {
        'signature': "function on_display_not_bright()",
        'description': "Executes when the watch screen turns off (becomes dim).",
        'example': "function on_display_not_bright()\n  wm_unschedule_all()\nend"
    },

    # Variables
    'is_bright': {
        'signature': "is_bright",
        'description': "Boolean value indicating whether the screen is currently bright.",
        'example': "if is_bright then\n  -- screen is on\nend"
    },
}

# WatchMaker 動作列表
WATCHMAKER_ACTIONS = [
    'media_play_pause', 'media_next', 'media_prev', 'media_stop',
    'sw_start_stop', 'sw_reset', 'sw_lap',
    'vol_up', 'vol_down', 'vol_mute',
    'm_update_weather', 'm_task:',
    'flashlight_on', 'flashlight_off',
    'alarm', 'timer', 'stopwatch',
]

# Easing 函數列表
EASING_FUNCTIONS = [
    'linear',
    'inQuad', 'outQuad', 'inOutQuad',
    'inCubic', 'outCubic', 'inOutCubic',
    'inQuart', 'outQuart', 'inOutQuart',
    'inQuint', 'outQuint', 'inOutQuint',
    'inSine', 'outSine', 'inOutSine',
    'inExpo', 'outExpo', 'inOutExpo',
    'inCirc', 'outCirc', 'inOutCirc',
    'inElastic', 'outElastic', 'inOutElastic',
    'inBack', 'outBack', 'inOutBack',
    'inBounce', 'outBounce', 'inOutBounce',
]

# WatchMaker 標籤系統（從 TAG_REFERENCE.md 擷取）
# 格式: "Description:{tag}": "{tag}" (空格以底線替代)
WATCHMAKER_TAGS = {
    # Date / 日期
    "Day_in_month:{dd}": "{dd}",
    "Day_in_month_with_leading_zero:{ddz}": "{ddz}",
    "Day_in_year:{ddy}": "{ddy}",
    "Day_of_week_format_1:{ddw1}": "{ddw1}",
    "Day_of_week_format_2:{ddw2}": "{ddw2}",
    "Day_of_week:{ddw}": "{ddw}",
    "Day_of_week_full:{ddww}": "{ddww}",
    "Day_of_week_next_format_1:{ddw1_1}": "{ddw1_1}",
    "Day_of_week_next_format_2:{ddw2_1}": "{ddw2_1}",
    "Day_of_week_next:{ddw_1}": "{ddw_1}",
    "Day_of_week_next_full:{ddww_1}": "{ddww_1}",
    "Day_of_week_Sun=0_Sat=6:{ddw0}": "{ddw0}",
    "Days_in_current_month:{ddim}": "{ddim}",
    "Month_in_year:{dn}": "{dn}",
    "Month_short:{dnn}": "{dnn}",
    "Month_medium:{dnnn}": "{dnnn}",
    "Month_full:{dnnnn}": "{dnnnn}",
    "Year_2_digits:{dy}": "{dy}",
    "Year_4_digits:{dyy}": "{dyy}",
    "Week_in_month:{dwm}": "{dwm}",
    "Week_in_year:{dw}": "{dw}",

    # Time (12-Hour) / 時間（12小時制）
    "Hour_1-12:{dh}": "{dh}",
    "Hour_0-11:{dh11}": "{dh11}",
    "Hour_1-12_with_leading_zero:{dhz}": "{dhz}",
    "Hour_0-11_with_leading_zero:{dh11z}": "{dh11z}",
    "Hour_text_1-12:{dht}": "{dht}",
    "Hour_tens_1-12:{dhtt}": "{dhtt}",
    "Hour_ones_1-12:{dhto}": "{dhto}",
    "Hour_tens_0-11:{dh11tt}": "{dh11tt}",
    "Hour_ones_0-11:{dh11to}": "{dh11to}",
    "Hour_UTC_12hr:{dhutc12}": "{dhutc12}",
    "Hour_UTC_12hr_with_leading_zero:{dhutc12z}": "{dhutc12z}",
    "AM/PM:{da}": "{da}",

    # Time (24-Hour) / 時間（24小時制）
    "Hour_1-24:{dh24}": "{dh24}",
    "Hour_0-23:{dh23}": "{dh23}",
    "Hour_1-24_with_leading_zero:{dh24z}": "{dh24z}",
    "Hour_0-23_with_leading_zero:{dh23z}": "{dh23z}",
    "Hour_text_1-24:{dh24t}": "{dh24t}",
    "Hour_tens_1-24:{dh24tt}": "{dh24tt}",
    "Hour_ones_1-24:{dh24to}": "{dh24to}",
    "Hour_tens_0-23:{dh23tt}": "{dh23tt}",
    "Hour_ones_0-23:{dh23to}": "{dh23to}",
    "Hour_UTC_24hr:{dhutc24}": "{dhutc24}",
    "Hour_UTC_24hr_with_leading_zero:{dhutc24z}": "{dhutc24z}",
    "UTC_Offset:{dutcoff}": "{dutcoff}",

    # Minutes / 分鐘
    "Minute_in_hour:{dm}": "{dm}",
    "Minute_with_leading_zero:{dmz}": "{dmz}",
    "Minute_tens:{dmt}": "{dmt}",
    "Minute_ones:{dmo}": "{dmo}",
    "Minute_text_all:{dmat}": "{dmat}",
    "Minute_text_tens:{dmtt}": "{dmtt}",
    "Minute_text_ones:{dmot}": "{dmot}",

    # Seconds & Milliseconds / 秒與毫秒
    "Second_in_minute:{ds}": "{ds}",
    "Second_with_leading_zero:{dsz}": "{dsz}",
    "Second_tens:{dst}": "{dst}",
    "Second_ones:{dso}": "{dso}",
    "Second_text_all:{dsat}": "{dsat}",
    "Second_text_tens:{dstt}": "{dstt}",
    "Second_text_ones:{dsot}": "{dsot}",
    "Milliseconds:{dss}": "{dss}",
    "Milliseconds_with_leading_zeros:{dssz}": "{dssz}",
    "Seconds_*_1000_+_milliseconds:{dsps}": "{dsps}",
    "Seconds_since_epoch:{depoch}": "{depoch}",
    "Time_percent_24_hours:{dtp}": "{dtp}",
    "Timezone:{dz}": "{dz}",

    # Rotation Values / 旋轉值
    "Hour_hand_rotation_12h:{drh}": "{drh}",
    "Hour_hand_rotation_24h:{drh24}": "{drh24}",
    "Hour_hand_rotation_12h_no_adjust:{drh0}": "{drh0}",
    "Minute_hand_rotation:{drm}": "{drm}",
    "Second_hand_rotation:{drs}": "{drs}",
    "Second_hand_smooth_rotation:{drss}": "{drss}",
    "Milliseconds_rotation:{drms}": "{drms}",

    # Time Zone 1 / 時區1
    "Time_Zone_1_Location:{tz1l}": "{tz1l}",
    "Time_Zone_1_Location_Long:{tz1ll}": "{tz1ll}",
    "Time_Zone_1_UTC_Offset:{tz1o}": "{tz1o}",
    "Time_Zone_1_UTC_Offset_Mins:{tz1om}": "{tz1om}",
    "Time_Zone_1_Daylight_Savings:{tz1dst}": "{tz1dst}",
    "Time_Zone_1_Time:{tz1t}": "{tz1t}",
    "Time_Zone_1_Rotation_hour:{tz1rh}": "{tz1rh}",
    "Time_Zone_1_Rotation_hour_24h:{tz1rh24}": "{tz1rh24}",
    "Time_Zone_1_Rotation_minute:{tz1rm}": "{tz1rm}",

    # Time Zone 2 / 時區2
    "Time_Zone_2_Location:{tz2l}": "{tz2l}",
    "Time_Zone_2_Location_Long:{tz2ll}": "{tz2ll}",
    "Time_Zone_2_UTC_Offset:{tz2o}": "{tz2o}",
    "Time_Zone_2_UTC_Offset_Mins:{tz2om}": "{tz2om}",
    "Time_Zone_2_Daylight_Savings:{tz2dst}": "{tz2dst}",
    "Time_Zone_2_Time:{tz2t}": "{tz2t}",
    "Time_Zone_2_Rotation_hour:{tz2rh}": "{tz2rh}",
    "Time_Zone_2_Rotation_hour_24h:{tz2rh24}": "{tz2rh24}",
    "Time_Zone_2_Rotation_minute:{tz2rm}": "{tz2rm}",

    # Time Zone 3 / 時區3
    "Time_Zone_3_Location:{tz3l}": "{tz3l}",
    "Time_Zone_3_Location_Long:{tz3ll}": "{tz3ll}",
    "Time_Zone_3_UTC_Offset:{tz3o}": "{tz3o}",
    "Time_Zone_3_UTC_Offset_Mins:{tz3om}": "{tz3om}",
    "Time_Zone_3_Daylight_Savings:{tz3dst}": "{tz3dst}",
    "Time_Zone_3_Time:{tz3t}": "{tz3t}",
    "Time_Zone_3_Rotation_hour:{tz3rh}": "{tz3rh}",
    "Time_Zone_3_Rotation_hour_24h:{tz3rh24}": "{tz3rh24}",
    "Time_Zone_3_Rotation_minute:{tz3rm}": "{tz3rm}",

    # Color Switcher / 顏色切換器
    "Current_Color:{ucolor}": "{ucolor}",
    "Current_Color_Brighter:{ucolor_b}": "{ucolor_b}",

    # Counter / 計數器
    "Seconds_elapsed_since_loaded:{c_elapsed}": "{c_elapsed}",
    "0_to_100_in_2s_stop:{c_0_100_2_st}": "{c_0_100_2_st}",
    "0_to_100_in_2s_repeat:{c_0_100_2_rp}": "{c_0_100_2_rp}",
    "0_to_100_in_2s_reverse:{c_0_100_2_rv}": "{c_0_100_2_rv}",
    "0_to_100_in_2s_reverse_delay:{c_0_100_2_rv_2}": "{c_0_100_2_rv_2}",

    # Watch Battery / 手錶電池
    "Battery_level:{bl}": "{bl}",
    "Battery_level_percent:{blp}": "{blp}",
    "Battery_rotation:{br}": "{br}",
    "Battery_temperature_C:{btc}": "{btc}",
    "Battery_temperature_F:{btf}": "{btf}",
    "Battery_temperature_C_percent:{btcd}": "{btcd}",
    "Battery_temperature_F_percent:{btfd}": "{btfd}",
    "Battery_charging:{bc}": "{bc}",

    # Phone Battery / 手機電池
    "Phone_Battery_level:{pbl}": "{pbl}",
    "Phone_Battery_level_percent:{pblp}": "{pblp}",
    "Phone_Battery_rotation:{pbr}": "{pbr}",
    "Phone_Battery_temperature_C:{pbtc}": "{pbtc}",
    "Phone_Battery_temperature_F:{pbtf}": "{pbtf}",
    "Phone_Battery_temperature_C_percent:{pbtcd}": "{pbtcd}",
    "Phone_Battery_temperature_F_percent:{pbtfd}": "{pbtfd}",
    "Phone_Battery_charging:{pbc}": "{pbc}",

    # System / 系統
    "Operating_System:{aos}": "{aos}",
    "OS_Version:{aosv}": "{aosv}",
    "Language_Code:{alangcode}": "{alangcode}",
    "Language_Region:{alangreg}": "{alangreg}",
    "Language_Full:{alangfull}": "{alangfull}",
    "Device_name:{aname}": "{aname}",
    "Device_model:{amodel}": "{amodel}",
    "Device_manufacturer:{aman}": "{aman}",
    "System_Volume:{avol}": "{avol}",
    "Screen_Brightness:{abrt}": "{abrt}",
    "Low_Power_Mode:{alowpw}": "{alowpw}",
    "Bluetooth_Enabled:{abtc}": "{abtc}",
    "Watch_name:{awname}": "{awname}",
    "Is_round:{around}": "{around}",
    "Has_flat_tyre:{atyre}": "{atyre}",
    "Is_bright:{abright}": "{abright}",
    "Dim_mode_lo-bit_only:{adimlo}": "{adimlo}",
    "Milliseconds_since_bright:{abss}": "{abss}",
    "Seconds_since_bright_capped_30:{abssl}": "{abssl}",
    "Is_dark_mode:{adark}": "{adark}",
    "Last_Reboot_Time:{areboot}": "{areboot}",

    # Memory / 記憶體
    "Used_Memory:{amu}": "{amu}",
    "Used_Memory_Formatted:{amuf}": "{amuf}",
    "Used_Memory_Percentage:{amup}": "{amup}",
    "Free_Memory:{amf}": "{amf}",
    "Free_Memory_Formatted:{amff}": "{amff}",
    "Free_Memory_Percentage:{amfp}": "{amfp}",
    "Total_Memory:{amt}": "{amt}",
    "Total_Memory_Formatted:{amtf}": "{amtf}",

    # Disk Space / 磁碟空間
    "Used_Disk_Space:{adsu}": "{adsu}",
    "Used_Disk_Space_Formatted:{adsuf}": "{adsuf}",
    "Used_Disk_Space_Percentage:{adsup}": "{adsup}",
    "Free_Disk_Space:{adsf}": "{adsf}",
    "Free_Disk_Space_Formatted:{adsff}": "{adsff}",
    "Free_Disk_Space_Percentage:{adsfp}": "{adsfp}",
    "Total_Disk_Space:{adst}": "{adst}",
    "Total_Disk_Space_Formatted:{adstf}": "{adstf}",

    # Location / 位置
    "Current_latitude:{alat}": "{alat}",
    "Current_longitude:{alon}": "{alon}",
    "Current_latitude_degrees:{alatd}": "{alatd}",
    "Current_longitude_degrees:{alond}": "{alond}",
    "Current_latitude_degrees_direction:{alatdd}": "{alatdd}",
    "Current_longitude_degrees_direction:{alondd}": "{alondd}",
    "Current_altitude:{aalt}": "{aalt}",
    "what3words_address:{aw3w}": "{aw3w}",
    "what3words_Word_1:{aw3w1}": "{aw3w1}",
    "what3words_Word_2:{aw3w2}": "{aw3w2}",
    "what3words_Word_3:{aw3w3}": "{aw3w3}",

    # Network / 網路
    "Device_Online:{nc}": "{nc}",
    "Cellular_Connected:{ncc}": "{ncc}",
    "WiFi_Strength_percent:{pws}": "{pws}",
    "WiFi_Connected:{pwc}": "{pwc}",
    "WiFi_IP_Address:{nwip}": "{nwip}",

    # Stopwatch / 碼錶
    "Stopwatch_hours:{swh}": "{swh}",
    "Stopwatch_minutes:{swm}": "{swm}",
    "Stopwatch_seconds:{sws}": "{sws}",
    "Stopwatch_milliseconds_2_digits:{swss}": "{swss}",
    "Stopwatch_milliseconds_3_digits:{swsss}": "{swsss}",
    "Stopwatch_milliseconds_total:{swsst}": "{swsst}",
    "Stopwatch_is_running:{swr}": "{swr}",
    "Stopwatch_minute_rotation:{swrm}": "{swrm}",
    "Stopwatch_second_rotation:{swrs}": "{swrs}",
    "Stopwatch_millisecond_rotation:{swrss}": "{swrss}",

    # Weather - Current / 天氣 - 當前
    "Weather_Location:{wl}": "{wl}",
    "Current_Temperature:{wt}": "{wt}",
    "Today_High:{wth}": "{wth}",
    "Today_Low:{wtl}": "{wtl}",
    "Current_Temperature_degrees:{wtd}": "{wtd}",
    "Today_High_degrees:{wthd}": "{wthd}",
    "Today_Low_degrees:{wtld}": "{wtld}",
    "Weather_Units:{wm}": "{wm}",
    "Current_Condition_Text:{wct}": "{wct}",
    "Current_Condition_Icon:{wci}": "{wci}",
    "Current_Humidity_Number:{wh}": "{wh}",
    "Current_Humidity_Percentage:{whp}": "{whp}",
    "Atmospheric_Pressure:{wp}": "{wp}",
    "Wind_Speed_mph:{wws}": "{wws}",
    "Wind_Direction_degrees:{wwd}": "{wwd}",
    "Wind_Direction_NE:{wwdb}": "{wwdb}",
    "Wind_Direction_NNE:{wwdbb}": "{wwdbb}",
    "Cloudiness_percent:{wcl}": "{wcl}",
    "Rain_volume_3hrs_mm:{wr}": "{wr}",
    "Is_daytime:{wisday}": "{wisday}",
    "Sunrise_time:{wsr}": "{wsr}",
    "Sunset_time:{wss}": "{wss}",
    "Sunrise_percent_24hrs:{wsrp}": "{wsrp}",
    "Sunset_percent_24hrs:{wssp}": "{wssp}",
    "Moon_Phase:{wmp}": "{wmp}",
    "Weather_manual_location:{wml}": "{wml}",
    "Weather_last_update:{wlu}": "{wlu}",

    # Weather - Hourly Forecast / 天氣 - 每小時預報
    "Forecast_Hour_1_Temp:{wf1ht}": "{wf1ht}",
    "Forecast_Hour_1_Hour:{wf1hh}": "{wf1hh}",
    "Forecast_Hour_1_Condition_Text:{wf1hct}": "{wf1hct}",
    "Forecast_Hour_1_Condition_Icon:{wf1hci}": "{wf1hci}",
    "Forecast_Hour_2_Temp:{wf2ht}": "{wf2ht}",
    "Forecast_Hour_2_Hour:{wf2hh}": "{wf2hh}",
    "Forecast_Hour_2_Condition_Text:{wf2hct}": "{wf2hct}",
    "Forecast_Hour_2_Condition_Icon:{wf2hci}": "{wf2hci}",

    # Weather - Daily Forecast / 天氣 - 每日預報
    "Forecast_Day_0_Temp:{wf0dt}": "{wf0dt}",
    "Forecast_Day_0_High:{wf0dth}": "{wf0dth}",
    "Forecast_Day_0_Low:{wf0dtl}": "{wf0dtl}",
    "Forecast_Day_0_Condition_Text:{wf0dct}": "{wf0dct}",
    "Forecast_Day_0_Condition_Icon:{wf0dci}": "{wf0dci}",
    "Forecast_Day_1_Temp:{wf1dt}": "{wf1dt}",
    "Forecast_Day_1_High:{wf1dth}": "{wf1dth}",
    "Forecast_Day_1_Low:{wf1dtl}": "{wf1dtl}",
    "Forecast_Day_1_Condition_Text:{wf1dct}": "{wf1dct}",
    "Forecast_Day_1_Condition_Icon:{wf1dci}": "{wf1dci}",

    # Calendar / 日曆
    "Events_Exist:{cex}": "{cex}",
    "Event_1_Exists:{c1ex}": "{c1ex}",
    "Event_1_Text:{c1t}": "{c1t}",
    "Event_1_Begin_Date:{c1bd}": "{c1bd}",
    "Event_1_Begin_Time:{c1b}": "{c1b}",
    "Event_1_Begin_Rotation:{c1br}": "{c1br}",
    "Event_1_Begin_percent_24hrs:{c1bp}": "{c1bp}",
    "Event_1_End_Date:{c1ed}": "{c1ed}",
    "Event_1_End_Time:{c1e}": "{c1e}",
    "Event_1_End_Rotation:{c1er}": "{c1er}",
    "Event_1_End_percent_24hrs:{c1ep}": "{c1ep}",
    "Event_1_Location:{c1l}": "{c1l}",
    "Event_1_Color:{c1c}": "{c1c}",
    "Event_1_is_All_Day:{c1ad}": "{c1ad}",
    "Event_1_Calendar:{c1cal}": "{c1cal}",
    "Event_1_ID:{c1i}": "{c1i}",

    # Health & Fitness - Steps / 健康與健身 - 步數
    "Steps:{ssc}": "{ssc}",
    "Steps_Goal:{stsc}": "{stsc}",
    "Steps_percent_of_Goal:{sscp}": "{sscp}",
    "Distance_Units:{sdstu}": "{sdstu}",
    "Distance:{sdst}": "{sdst}",
    "Distance_Goal:{stdst}": "{stdst}",
    "Distance_percent_of_Goal:{sdstp}": "{sdstp}",
    "Calories_kCal:{scal}": "{scal}",
    "Calories_Goal_kCal:{stcal}": "{stcal}",
    "Calories_percent_of_Goal:{scalp}": "{scalp}",

    # Health & Fitness - Activity Rings / 健康與健身 - 活動圓環
    "Move_kCal:{ham}": "{ham}",
    "Move_Goal_kCal:{htam}": "{htam}",
    "Exercise_mins:{hae}": "{hae}",
    "Exercise_Goal_mins:{htae}": "{htae}",
    "Stand_hrs:{has}": "{has}",
    "Stand_Goal_hrs:{htas}": "{htas}",
    "Flights_Climbed:{hfc}": "{hfc}",

    # Health & Fitness - Heart Rate / 健康與健身 - 心率
    "Heart_Rate:{shr}": "{shr}",
    "Heart_Rate_Maximum:{sthr}": "{sthr}",
    "Heart_Rate_percent_of_Maximum:{shrp}": "{shrp}",
    "Heart_Rate_Previous:{shr_1}": "{shr_1}",
    "Heart_Rate_Previous_2:{shr_2}": "{shr_2}",

    # Sensors - Accelerometer / 感測器 - 加速度計
    "Accelerometer_X:{sax}": "{sax}",
    "Accelerometer_Y:{say}": "{say}",
    "Accelerometer_Z:{saz}": "{saz}",

    # Sensors - Gyroscope / 感測器 - 陀螺儀
    "Gyroscope_X:{sgx}": "{sgx}",
    "Gyroscope_Y:{sgy}": "{sgy}",
    "Gyroscope_Z:{sgz}": "{sgz}",

    # Sensors - Compass / 感測器 - 指南針
    "Compass_for_Rotation:{scr}": "{scr}",
    "Compass_Display:{sct}": "{sct}",
    "Compass_Display_degrees:{sctd}": "{sctd}",
    "Compass_Bearing_NE:{scb}": "{scb}",
    "Compass_Bearing_NNE:{scbb}": "{scbb}",
    "Compass_Display_degrees_NE:{sctdb}": "{sctdb}",
    "Compass_Display_degrees_NNE:{sctdbb}": "{sctdbb}",

    # Sensors - Other / 感測器 - 其他
    "Barometric_Pressure:{sprs}": "{sprs}",

    # Complications / 複雜功能
    "Complication_1_Text:{m1text}": "{m1text}",
    "Complication_1_Title:{m1title}": "{m1title}",
    "Complication_1_Value:{m1value}": "{m1value}",
    "Complication_1_Min:{m1min}": "{m1min}",
    "Complication_1_Max:{m1max}": "{m1max}",
    "Complication_2_Text:{m2text}": "{m2text}",
    "Complication_2_Title:{m2title}": "{m2title}",
    "Complication_2_Value:{m2value}": "{m2value}",
    "Complication_2_Min:{m2min}": "{m2min}",
    "Complication_2_Max:{m2max}": "{m2max}",
    "Complication_3_Text:{m3text}": "{m3text}",
    "Complication_3_Title:{m3title}": "{m3title}",
    "Complication_3_Value:{m3value}": "{m3value}",
    "Complication_3_Min:{m3min}": "{m3min}",
    "Complication_3_Max:{m3max}": "{m3max}",
    "Complication_4_Text:{m4text}": "{m4text}",
    "Complication_4_Title:{m4title}": "{m4title}",
    "Complication_4_Value:{m4value}": "{m4value}",
    "Complication_4_Min:{m4min}": "{m4min}",
    "Complication_4_Max:{m4max}": "{m4max}",
}


class LuaLexer(QsciLexerLua):
    """自定義 Lua 詞法分析器，支援深色主題"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_colors()
        self.setup_font()

    def setup_colors(self):
        """設置深色主題顏色"""
        # 預設文字
        self.setColor(QColor("#E0E0E0"), QsciLexerLua.Default)
        # 註解
        self.setColor(QColor("#6A9955"), QsciLexerLua.Comment)
        self.setColor(QColor("#6A9955"), QsciLexerLua.LineComment)
        # 數字
        self.setColor(QColor("#B5CEA8"), QsciLexerLua.Number)
        # 字串
        self.setColor(QColor("#CE9178"), QsciLexerLua.String)
        self.setColor(QColor("#CE9178"), QsciLexerLua.Character)
        self.setColor(QColor("#CE9178"), QsciLexerLua.LiteralString)
        # 關鍵字
        self.setColor(QColor("#569CD6"), QsciLexerLua.Keyword)
        # 基本函數
        self.setColor(QColor("#DCDCAA"), QsciLexerLua.BasicFunctions)
        # 字串函數/協程函數/數學函數等
        self.setColor(QColor("#4EC9B0"), QsciLexerLua.StringTableMathsFunctions)
        self.setColor(QColor("#4EC9B0"), QsciLexerLua.CoroutinesIOSystemFacilities)
        # 運算符
        self.setColor(QColor("#D4D4D4"), QsciLexerLua.Operator)
        # 識別符
        self.setColor(QColor("#9CDCFE"), QsciLexerLua.Identifier)
        # 標籤
        self.setColor(QColor("#C586C0"), QsciLexerLua.Label)

        # 設置紙張背景色（編輯器背景）- 為所有樣式設定統一背景色
        bg_color = QColor("#1E1E1E")
        self.setPaper(bg_color)
        self.setDefaultPaper(bg_color)

        # 為所有 token 類型設定相同背景色
        for style in range(128):
            self.setPaper(bg_color, style)

    def setup_font(self):
        """設置等寬字體"""
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setDefaultFont(font)


class LuaEditor(QsciScintilla):
    """Lua 程式碼編輯器"""

    # 用戶列表 ID（用於標籤自動完成）
    TAG_LIST_ID = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        # 標籤自動完成狀態
        self._tag_mode = False
        self._tag_start_pos = -1

        self.setup_editor()
        self.setup_lexer()
        self.setup_autocomplete()
        self.setup_tag_autocomplete()
        self.setup_margins()
        self.setup_folding()
        self.setup_indicators()

        # 連接用戶列表選擇信號（用於標籤自動完成）
        self.userListActivated.connect(self._on_userlist_selected)

    def setup_editor(self):
        """設置編輯器基本屬性"""
        # 設置編碼
        self.setUtf8(True)

        # 設置縮進
        self.setIndentationsUseTabs(False)
        self.setTabWidth(2)
        self.setAutoIndent(True)
        self.setIndentationGuides(True)

        # 設置括號匹配
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        self.setMatchedBraceBackgroundColor(QColor("#3A3D41"))
        self.setMatchedBraceForegroundColor(QColor("#FFCC00"))
        self.setUnmatchedBraceBackgroundColor(QColor("#5A1D1D"))
        self.setUnmatchedBraceForegroundColor(QColor("#FF6B6B"))

        # 設置當前行高亮
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#2D2D30"))
        self.setCaretForegroundColor(QColor("#FFFFFF"))
        self.setCaretWidth(2)

        # 設置選中文字顏色
        self.setSelectionBackgroundColor(QColor("#264F78"))
        self.setSelectionForegroundColor(QColor("#FFFFFF"))

        # 設置邊距顏色
        self.setMarginsBackgroundColor(QColor("#252526"))
        self.setMarginsForegroundColor(QColor("#858585"))

        # 啟用自動換行
        self.setWrapMode(QsciScintilla.WrapWord)

        # 設置滾動條
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 設置編輯器背景色
        self.setStyleSheet("background-color: #1E1E1E;")

    def setup_lexer(self):
        """設置詞法分析器"""
        self.lexer = LuaLexer(self)
        self.setLexer(self.lexer)

    def setup_autocomplete(self):
        """設置自動完成"""
        self.apis = QsciAPIs(self.lexer)

        # 添加 Lua 標準函數
        lua_keywords = [
            'and', 'break', 'do', 'else', 'elseif', 'end', 'false',
            'for', 'function', 'goto', 'if', 'in', 'local', 'nil',
            'not', 'or', 'repeat', 'return', 'then', 'true', 'until', 'while',
            'print', 'type', 'tonumber', 'tostring', 'pairs', 'ipairs',
            'next', 'select', 'unpack', 'pcall', 'xpcall', 'error', 'assert',
            'string.len', 'string.sub', 'string.find', 'string.format',
            'string.lower', 'string.upper', 'string.rep', 'string.reverse',
            'math.abs', 'math.ceil', 'math.floor', 'math.max', 'math.min',
            'math.random', 'math.sin', 'math.cos', 'math.tan', 'math.sqrt',
            'table.insert', 'table.remove', 'table.sort', 'table.concat',
        ]

        for keyword in lua_keywords:
            self.apis.add(keyword)

        # 添加 WatchMaker API
        for func_name in WATCHMAKER_API.keys():
            self.apis.add(func_name)

        # 添加自定義變數前綴
        self.apis.add('var_')
        self.apis.add('var_ms_')
        self.apis.add('var_s_')

        # 添加 easing 函數
        for easing in EASING_FUNCTIONS:
            self.apis.add(easing)

        # 添加動作
        for action in WATCHMAKER_ACTIONS:
            self.apis.add(action)

        # 準備 API
        self.apis.prepare()

        # 設置自動完成
        self.setAutoCompletionSource(QsciScintilla.AcsAll)
        self.setAutoCompletionThreshold(2)
        self.setAutoCompletionCaseSensitivity(False)
        self.setAutoCompletionReplaceWord(True)
        self.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

        # 設置自動完成視窗樣式
        self.setAutoCompletionFillups('(')

        # 設置自動完成選單顏色（深色主題）
        # 使用 SendScintilla 設定自動完成列表的前景色和背景色
        self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciScintilla.STYLE_DEFAULT, 0xE0E0E0)  # 淺灰色文字
        self.SendScintilla(QsciScintilla.SCI_STYLESETBACK, QsciScintilla.STYLE_DEFAULT, 0x252526)  # 深色背景

        # 自動完成列表顏色
        self.SendScintilla(QsciScintilla.SCI_AUTOCSETMAXHEIGHT, 10)  # 最多顯示 10 項

    def setup_tag_autocomplete(self):
        """設置標籤自動完成"""
        # 建立標籤自動完成的 API 列表
        self.tag_apis = QsciAPIs(self.lexer)

        # 添加所有 WatchMaker 標籤
        for display_text in WATCHMAKER_TAGS.keys():
            self.tag_apis.add(display_text)

        # 準備 API
        self.tag_apis.prepare()

    def keyPressEvent(self, event):
        """攔截按鍵事件以處理標籤自動完成"""
        # 檢查是否輸入 {
        if event.text() == '{':
            # 先插入 { 字符
            super().keyPressEvent(event)

            # 進入標籤模式
            self._tag_mode = True
            self._tag_start_pos = self.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)

            # 顯示標籤自動完成選單
            self._show_tag_autocomplete()
            return

        # 在標籤模式下按 Escape 取消
        if self._tag_mode and event.key() == Qt.Key_Escape:
            self._tag_mode = False
            self._tag_start_pos = -1
            self.SendScintilla(QsciScintilla.SCI_AUTOCCANCEL)
            return

        # 在標籤模式下輸入 } 退出標籤模式
        if self._tag_mode and event.text() == '}':
            self._tag_mode = False
            self._tag_start_pos = -1

        super().keyPressEvent(event)

    def _show_tag_autocomplete(self):
        """顯示標籤自動完成選單（使用用戶列表）"""
        # 構建標籤列表字串（以空格分隔，用於 showUserList）
        tag_list = sorted(WATCHMAKER_TAGS.keys())

        # 使用 showUserList 顯示標籤選單
        # 這會觸發 userListActivated 信號
        self.showUserList(self.TAG_LIST_ID, tag_list)

    def _on_userlist_selected(self, list_id, selected_text):
        """當用戶列表項目被選中時的回調"""
        # 確認是標籤列表
        if list_id != self.TAG_LIST_ID:
            return

        # 確認是標籤模式且選擇的是有效標籤
        if not self._tag_mode or selected_text not in WATCHMAKER_TAGS:
            self._tag_mode = False
            self._tag_start_pos = -1
            return

        # 取得實際標籤
        actual_tag = WATCHMAKER_TAGS[selected_text]

        # 刪除 { 並插入實際標籤
        # tag_start_pos 是 { 之後的位置，所以 { 的位置是 tag_start_pos - 1
        delete_start = self._tag_start_pos - 1
        current_pos = self.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)

        # 設置選擇範圍並替換
        self.SendScintilla(QsciScintilla.SCI_SETSEL, delete_start, current_pos)
        self.SendScintilla(QsciScintilla.SCI_REPLACESEL, 0, actual_tag.encode('utf-8'))

        # 重置標籤模式
        self._tag_mode = False
        self._tag_start_pos = -1

    def setup_margins(self):
        """設置邊距（行號）"""
        # 行號邊距
        self.setMarginType(0, QsciScintilla.NumberMargin)
        self.setMarginWidth(0, "0000")
        self.setMarginLineNumbers(0, True)

        # 摺疊邊距
        self.setMarginType(1, QsciScintilla.SymbolMargin)
        self.setMarginWidth(1, 16)
        self.setMarginSensitivity(1, True)

        # 錯誤標記邊距
        self.setMarginType(2, QsciScintilla.SymbolMargin)
        self.setMarginWidth(2, 16)

        # 定義標記樣式
        self.markerDefine(QsciScintilla.Circle, 0)  # 錯誤標記
        self.setMarkerBackgroundColor(QColor("#FF6B6B"), 0)
        self.setMarkerForegroundColor(QColor("#FF6B6B"), 0)

        self.markerDefine(QsciScintilla.RightArrow, 1)  # 警告標記
        self.setMarkerBackgroundColor(QColor("#FFCC00"), 1)
        self.setMarkerForegroundColor(QColor("#FFCC00"), 1)

    def setup_folding(self):
        """設置程式碼摺疊"""
        self.setFolding(QsciScintilla.BoxedTreeFoldStyle)
        self.setFoldMarginColors(QColor("#252526"), QColor("#252526"))

    def setup_indicators(self):
        """設置指示器（用於錯誤高亮）"""
        # 錯誤指示器（紅色波浪線）
        self.indicatorDefine(QsciScintilla.SquiggleIndicator, 0)
        self.setIndicatorForegroundColor(QColor("#FF6B6B"), 0)

        # 警告指示器（黃色波浪線）
        self.indicatorDefine(QsciScintilla.SquiggleIndicator, 1)
        self.setIndicatorForegroundColor(QColor("#FFCC00"), 1)

    def add_error_marker(self, line):
        """在指定行添加錯誤標記"""
        self.markerAdd(line, 0)

    def add_warning_marker(self, line):
        """在指定行添加警告標記"""
        self.markerAdd(line, 1)

    def clear_markers(self):
        """清除所有標記"""
        self.markerDeleteAll(0)
        self.markerDeleteAll(1)

    def highlight_error(self, start_pos, length):
        """高亮錯誤區域"""
        self.SendScintilla(QsciScintilla.SCI_SETINDICATORCURRENT, 0)
        self.SendScintilla(QsciScintilla.SCI_INDICATORFILLRANGE, start_pos, length)

    def clear_error_highlights(self):
        """清除所有錯誤高亮"""
        self.SendScintilla(QsciScintilla.SCI_SETINDICATORCURRENT, 0)
        self.SendScintilla(QsciScintilla.SCI_INDICATORCLEARRANGE, 0, self.length())


class APIReferencePanel(QWidget):
    """API 參考面板"""

    # 當選擇 API 時發出信號
    api_selected = pyqtSignal(str)  # 發送函數名稱

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("apiReferencePanel")
        self.setup_ui()

    def setup_ui(self):
        """設置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 標題
        title = QLabel("WatchMaker API")
        title.setObjectName("apiTitle")
        layout.addWidget(title)

        # API 列表
        self.api_list = QListWidget()
        self.api_list.setObjectName("apiList")
        self.api_list.itemClicked.connect(self.on_item_clicked)
        self.api_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.api_list)

        # 填充 API 列表
        self.populate_api_list()

        # 詳細資訊區域 - 使用 QScrollArea
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setObjectName("apiDetailScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setMinimumHeight(100)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.detail_label = QLabel()
        self.detail_label.setObjectName("apiDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.detail_scroll.setWidget(self.detail_label)

        layout.addWidget(self.detail_scroll)

    def populate_api_list(self):
        """Populate API list"""
        # Group by category
        categories = {
            'Core Functions': ['wm_schedule', 'wm_unschedule_all', 'wm_action', 'wm_tag',
                              'wm_vibrate', 'wm_sfx', 'wm_transition', 'wm_anim_set', 'wm_anim_start'],
            'Callbacks': ['on_hour', 'on_minute', 'on_second', 'on_millisecond',
                         'on_display_bright', 'on_display_not_bright'],
            'Variables': ['is_bright'],
        }

        for category, funcs in categories.items():
            # 添加分類標題
            category_item = QListWidgetItem(f"── {category} ──")
            category_item.setFlags(Qt.NoItemFlags)
            self.api_list.addItem(category_item)

            # 添加函數
            for func_name in funcs:
                item = QListWidgetItem(f"  {func_name}")
                item.setData(Qt.UserRole, func_name)
                self.api_list.addItem(item)

    def on_item_clicked(self, item):
        """Show details when item is clicked"""
        func_name = item.data(Qt.UserRole)
        if func_name and func_name in WATCHMAKER_API:
            api_info = WATCHMAKER_API[func_name]
            detail_text = f"<b>{api_info['signature']}</b><br><br>"
            detail_text += f"{api_info['description']}<br><br>"
            detail_text += f"<b>Example:</b><br><code>{api_info['example']}</code>"
            self.detail_label.setText(detail_text)

    def on_item_double_clicked(self, item):
        """Insert into editor when item is double-clicked"""
        func_name = item.data(Qt.UserRole)
        if func_name:
            self.api_selected.emit(func_name)


class OutputPanel(QWidget):
    """輸出/偵錯面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("outputPanel")
        self.setup_ui()

    def setup_ui(self):
        """設置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 標題列
        title_bar = QWidget()
        title_bar.setObjectName("outputTitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("Output")
        title.setObjectName("outputTitle")
        title_layout.addWidget(title)

        title_layout.addStretch()

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("outputClearButton")
        clear_btn.clicked.connect(self.clear_output)
        title_layout.addWidget(clear_btn)

        layout.addWidget(title_bar)

        # 輸出文字區域
        self.output_text = QTextEdit()
        self.output_text.setObjectName("outputText")
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.output_text)

    def append_output(self, text, level="info"):
        """Append output message"""
        color_map = {
            "info": "#E0E0E0",
            "warning": "#FFCC00",
            "error": "#FF6B6B",
            "success": "#6A9955",
        }
        color = color_map.get(level, "#E0E0E0")
        self.output_text.append(f'<span style="color: {color};">{text}</span>')

    def clear_output(self):
        """Clear output"""
        self.output_text.clear()

    def log_info(self, text):
        """Log info"""
        self.append_output(f"[INFO] {text}", "info")

    def log_warning(self, text):
        """Log warning"""
        self.append_output(f"[WARNING] {text}", "warning")

    def log_error(self, text):
        """Log error"""
        self.append_output(f"[ERROR] {text}", "error")

    def log_success(self, text):
        """Log success"""
        self.append_output(f"[SUCCESS] {text}", "success")


class ScriptView(QWidget):
    """腳本編輯器視圖"""

    # 信號
    return_requested = pyqtSignal()
    script_changed = pyqtSignal(str)  # 當腳本內容改變時

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("scriptView")
        self.setStyleSheet(load_style())

        self.property_name = ""
        self.original_value = ""

        # Initialize syntax checker with WatchMaker API
        self.syntax_checker = LuaSyntaxChecker(
            watchmaker_api=WATCHMAKER_API,
            watchmaker_actions=WATCHMAKER_ACTIONS,
            easing_functions=EASING_FUNCTIONS
        )

        # Debounce timer for real-time checking
        self.check_timer = QTimer()
        self.check_timer.setSingleShot(True)
        self.check_timer.timeout.connect(self._delayed_syntax_check)
        self.check_delay_ms = 500

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """設置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 標題列
        self.create_title_bar()
        layout.addWidget(self.title_bar)

        # 主內容區域
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setObjectName("contentSplitter")

        # 左側：編輯器區域
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # 編輯器和輸出面板的垂直分割
        editor_splitter = QSplitter(Qt.Vertical)
        editor_splitter.setObjectName("editorSplitter")

        # 程式碼編輯器
        self.editor = LuaEditor()
        editor_splitter.addWidget(self.editor)

        # 輸出面板
        self.output_panel = OutputPanel()
        editor_splitter.addWidget(self.output_panel)

        # 設置分割比例
        editor_splitter.setSizes([500, 150])
        editor_layout.addWidget(editor_splitter)

        content_splitter.addWidget(editor_widget)

        # 右側：API 參考面板
        self.api_panel = APIReferencePanel()
        self.api_panel.setFixedWidth(280)
        content_splitter.addWidget(self.api_panel)

        layout.addWidget(content_splitter)

        # 底部按鈕列
        self.create_button_bar()
        layout.addWidget(self.button_bar)

    def create_title_bar(self):
        """創建標題列"""
        self.title_bar = QWidget()
        self.title_bar.setObjectName("scriptTitleBar")
        self.title_bar.setFixedHeight(40)

        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(15, 0, 15, 0)

        # Title
        self.title_label = QLabel("Lua Script Editor")
        self.title_label.setObjectName("scriptTitle")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Undo button - uses QScintilla built-in undo
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setObjectName("checkButton")
        self.undo_btn.clicked.connect(self.undo_action)
        layout.addWidget(self.undo_btn)

        # Redo button - uses QScintilla built-in redo
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setObjectName("checkButton")
        self.redo_btn.clicked.connect(self.redo_action)
        layout.addWidget(self.redo_btn)

        # Syntax check button
        self.check_btn = QPushButton("Check Syntax")
        self.check_btn.setObjectName("checkButton")
        self.check_btn.clicked.connect(self.check_syntax)
        layout.addWidget(self.check_btn)

        # Format button
        self.format_btn = QPushButton("Format")
        self.format_btn.setObjectName("formatButton")
        self.format_btn.clicked.connect(self.format_code)
        layout.addWidget(self.format_btn)

    def create_button_bar(self):
        """創建底部按鈕列"""
        self.button_bar = QWidget()
        self.button_bar.setObjectName("scriptButtonBar")
        self.button_bar.setFixedHeight(50)

        layout = QHBoxLayout(self.button_bar)
        layout.setContentsMargins(15, 0, 15, 0)

        # Return button
        self.return_btn = QPushButton("Return")
        self.return_btn.setObjectName("returnButton")
        self.return_btn.clicked.connect(self.on_return)
        layout.addWidget(self.return_btn)

        layout.addStretch()

        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearButton")
        self.clear_btn.clicked.connect(self.clear_editor)
        layout.addWidget(self.clear_btn)

        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("applyButton")
        self.apply_btn.clicked.connect(self.apply_script)
        layout.addWidget(self.apply_btn)

    def connect_signals(self):
        """連接信號"""
        # API 面板雙擊插入
        self.api_panel.api_selected.connect(self.insert_api_template)

        # 編輯器文字改變
        self.editor.textChanged.connect(self.on_text_changed)

        # Setup keyboard shortcuts using QShortcut
        self.setup_shortcuts()

    def setup_shortcuts(self):
        """Setup keyboard shortcuts using PyQt5 QShortcut"""
        # Undo: Ctrl+Z
        self.shortcut_undo = QShortcut(QKeySequence.Undo, self)
        self.shortcut_undo.activated.connect(self.undo_action)

        # Redo: Ctrl+Y or Ctrl+Shift+Z
        self.shortcut_redo = QShortcut(QKeySequence.Redo, self)
        self.shortcut_redo.activated.connect(self.redo_action)

        # Save/Apply: Ctrl+S
        self.shortcut_save = QShortcut(QKeySequence.Save, self)
        self.shortcut_save.activated.connect(self.apply_script)

        # Check syntax: Ctrl+Shift+C
        self.shortcut_check = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self.shortcut_check.activated.connect(self.check_syntax)

        # Format code: Ctrl+Shift+F
        self.shortcut_format = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        self.shortcut_format.activated.connect(self.format_code)

        # Return: Escape
        self.shortcut_return = QShortcut(QKeySequence("Escape"), self)
        self.shortcut_return.activated.connect(self.on_return)

    def undo_action(self):
        """Undo using QScintilla built-in undo"""
        if self.editor.isUndoAvailable():
            self.editor.undo()

    def redo_action(self):
        """Redo using QScintilla built-in redo"""
        if self.editor.isRedoAvailable():
            self.editor.redo()

    def set_property(self, property_name, current_value):
        """Set the property to edit"""
        self.property_name = property_name
        self.original_value = current_value if current_value else ""

        # Update title
        self.title_label.setText(f"Lua Script Editor - {property_name}")

        # Set editor content
        self.editor.setText(self.original_value)

        # Clear output
        self.output_panel.clear_output()
        self.output_panel.log_info(f"Editing: {property_name}")

    def get_script(self):
        """Get script content"""
        return self.editor.text()

    def insert_api_template(self, func_name):
        """Insert API template"""
        if func_name in WATCHMAKER_API:
            api_info = WATCHMAKER_API[func_name]
            # Insert example code
            template = api_info['example']
            self.editor.insert(template)
            self.editor.setFocus()
            self.output_panel.log_info(f"Inserted {func_name} template")

    def check_syntax(self):
        """Check syntax using luaparser-based checker"""
        self.editor.clear_markers()
        self.editor.clear_error_highlights()

        code = self.editor.text()
        if not code.strip():
            self.output_panel.log_warning("Code is empty")
            return

        # Perform syntax check using LuaSyntaxChecker
        errors = self.syntax_checker.check(code)
        self._display_errors(errors, show_success=True)

    def _display_errors(self, errors: list, show_success: bool = True):
        """Display errors in editor and output panel"""
        if errors:
            for error in errors:
                # Add visual markers based on severity
                if error.severity == ErrorSeverity.ERROR:
                    self.editor.add_error_marker(error.line)
                else:
                    self.editor.add_warning_marker(error.line)

                # Highlight error span if available
                if error.start_pos is not None and error.length:
                    if error.severity == ErrorSeverity.ERROR:
                        self.editor.highlight_error(error.start_pos, error.length)

                # Log to output panel
                line_display = error.line + 1  # 1-indexed for display
                log_msg = f"Line {line_display}: [{error.error_code}] {error.message}"

                if error.severity == ErrorSeverity.ERROR:
                    self.output_panel.log_error(log_msg)
                elif error.severity == ErrorSeverity.WARNING:
                    self.output_panel.log_warning(log_msg)
                else:
                    self.output_panel.log_info(log_msg)
        elif show_success:
            checker_type = "luaparser" if self.syntax_checker.parser_available else "basic"
            self.output_panel.log_success(f"Syntax check passed ({checker_type})")

    def _delayed_syntax_check(self):
        """Perform syntax check after debounce delay"""
        code = self.editor.text()
        if not code.strip() or len(code) > 10000:
            return  # Skip for empty or very long code

        self.editor.clear_markers()
        self.editor.clear_error_highlights()

        errors = self.syntax_checker.check(code)
        self._display_errors(errors, show_success=False)

    def format_code(self):
        """Format code (basic indentation)"""
        code = self.editor.text()
        if not code.strip():
            return

        formatted_lines = []
        indent_level = 0
        indent_str = "  "  # Two spaces

        increase_indent = {'function', 'if', 'for', 'while', 'do', 'repeat', 'else', 'elseif'}
        decrease_indent = {'end', 'until', 'else', 'elseif'}

        for line in code.split('\n'):
            stripped = line.strip()

            # Check if indent should decrease
            first_word = stripped.split()[0] if stripped.split() else ''
            if first_word in decrease_indent:
                indent_level = max(0, indent_level - 1)

            # Add indented line
            if stripped:
                formatted_lines.append(indent_str * indent_level + stripped)
            else:
                formatted_lines.append('')

            # Check if indent should increase
            if first_word in increase_indent and first_word not in {'else', 'elseif'}:
                indent_level += 1
            elif first_word in {'else', 'elseif'}:
                indent_level += 1

        # Update editor
        self.editor.setText('\n'.join(formatted_lines))
        self.output_panel.log_info("Code formatted")

    def clear_editor(self):
        """Clear editor content"""
        self.editor.clear()
        self.editor.clear_markers()
        self.editor.clear_error_highlights()
        self.output_panel.log_info("Editor cleared")

    def apply_script(self):
        """Apply script"""
        script = self.get_script()
        self.script_changed.emit(script)
        self.output_panel.log_success("Script applied")

    def on_return(self):
        """Return to main view"""
        self.return_requested.emit()

    def on_text_changed(self):
        """On text changed"""
        # Clear old error markers
        self.editor.clear_markers()
        self.editor.clear_error_highlights()

        # Clear syntax checker cache when text changes
        self.syntax_checker.clear_cache()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 設置應用程式深色主題
    app.setStyle("Fusion")

    # 創建並顯示 ScriptView
    window = ScriptView()
    window.setWindowTitle("Lua Script Editor - Test")
    window.resize(1200, 800)

    # Set test property and sample code
    sample_code = """-- WatchMaker Lua Script Example
-- A simple watch animation script

-- Custom variable
var_s_rotation = 0

-- Update every second
function on_second(h, m, s)
  -- Calculate second hand rotation angle
  var_s_rotation = s * 6

  -- Play sound on the hour
  if s == 0 and m == 0 then
    wm_sfx('hour_chime.mp3')
    wm_vibrate(200, 1)
  end
end

-- Animation when screen turns on
function on_display_bright()
  wm_schedule {
    action = 'tween',
    tween = 'opacity',
    from = 0,
    to = 1,
    duration = 0.5,
    easing = 'outQuad'
  }
end

-- Clear animations when screen turns off
function on_display_not_bright()
  wm_unschedule_all()
end
"""

    window.set_property("Test Script", sample_code)
    window.show()

    sys.exit(app.exec_())
