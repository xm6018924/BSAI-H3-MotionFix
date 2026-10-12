# BSAI-H3-MotionFix - ComfyUI Custom Node
# MiniMax H3 高速运动/快速动作 毛刺与噪点修复向导

# === BSAI H3 VAE 全量加载统一补丁（宿主 BSAI-ComfyUI-Sol-H3）===
try:
    import sys as _sys, os as _os
    _SOL = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                         "..", "BSAI-ComfyUI-Sol-H3")
    if _SOL not in _sys.path:
        _sys.path.insert(0, _SOL)
    import bsai_h3_vae_full as _h3v
    _h3v.apply_global_patch("BSAI-H3-MotionFix")
except Exception:
    pass

from .bsai_h3_motion_fix import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
