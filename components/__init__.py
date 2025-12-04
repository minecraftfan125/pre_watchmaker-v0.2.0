"""
Components module with lazy loading support.
元件模組，支援延遲載入。
"""

import importlib
from typing import TYPE_CHECKING

# 定義可延遲載入的屬性
_lazy_imports = {
    # common.py
    'COMMON_POSITION': 'common',
    'COMMON_POSITION_3D': 'common',
    'COMMON_TRANSFORM': 'common',
    'COMMON_SIZE': 'common',
    'COMMON_COLOR': 'common',
    'COMMON_DISPLAY': 'common',
    'COMMON_INTERACTION': 'common',
    'COMMON_SHADOW': 'common',
    'COMMON_OUTLINE': 'common',
    'COMMON_SHADER': 'common',
    'COMMON_BLEND': 'common',
    'COMMON_ANIM_SCALE': 'common',
    'COMMON_PROTECTED': 'common',
    # attributes.py - component types
    'group': 'attributes',
    'text': 'attributes',
    'text_animation': 'attributes',
    'text_curved': 'attributes',
    'text_ring': 'attributes',
    'image': 'attributes',
    'image_gif': 'attributes',
    'image_cutout': 'attributes',
    'video': 'attributes',
    'shape': 'attributes',
    'rounded': 'attributes',
    'ring': 'attributes',
    'ring_image': 'attributes',
    'progress': 'attributes',
    'progress_image': 'attributes',
    'chart': 'attributes',
    'markers': 'attributes',
    'markers_hm': 'attributes',
    'tachy': 'attributes',
    'series': 'attributes',
    'map': 'attributes',
    'gallery_2d': 'attributes',
    'model_3d': 'attributes',
    'text_3d': 'attributes',
    'camera': 'attributes',
    'light_dir': 'attributes',
    'complication': 'attributes',
    # attributes.py - other exports
    'SHADER_PARAMS': 'attributes',
    'ANIMATION_TYPES': 'attributes',
    'TAP_ACTIONS': 'attributes',
    'get_shader_params': 'attributes',
    # utils.py
    'summon_components': 'utils',
}

# 快取已載入的模組
_loaded_modules = {}

def __getattr__(name: str):
    """延遲載入屬性"""
    if name in _lazy_imports:
        module_name = _lazy_imports[name]

        # 檢查模組是否已載入
        if module_name not in _loaded_modules:
            _loaded_modules[module_name] = importlib.import_module(
                f'.{module_name}', __name__
            )

        return getattr(_loaded_modules[module_name], name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """列出所有可用屬性"""
    return list(_lazy_imports.keys())


# 為了 IDE 自動完成和類型檢查 (不會實際執行載入)
if TYPE_CHECKING:
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
    from .attributes import (
        group,
        text,
        text_animation,
        text_curved,
        text_ring,
        image,
        image_gif,
        image_cutout,
        video,
        shape,
        rounded,
        ring,
        ring_image,
        progress,
        progress_image,
        chart,
        markers,
        markers_hm,
        tachy,
        series,
        map,
        gallery_2d,
        model_3d,
        text_3d,
        camera,
        light_dir,
        complication,
        SHADER_PARAMS,
        ANIMATION_TYPES,
        TAP_ACTIONS,
        get_shader_params,
    )
    from .utils import summon_components


__all__ = list(_lazy_imports.keys())
