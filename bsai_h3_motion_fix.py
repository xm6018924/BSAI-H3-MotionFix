# -*- coding: utf-8 -*-
"""
BSAI-H3-MotionFix — MiniMax H3 高速运动/快速动作「毛刺 & 噪点」修复向导
=====================================================================
面向 ComfyUI MiniMax H3 在高速运动、人物快速动作（打斗/奔跑/大位移镜头）
下出现的画面毛刺、拖影/残影（motion-smear / trailing ghosting）、帧撕裂、
时序闪烁与噪点问题，输出可直接照抄的修复配置。

方案依据（2026-08-31 全网交叉核验，来源见 README.md）:
  - ComfyUI-MiniMax-H3-Turbo   : Turbo LoRA 在 4 步 + 大/快运动 → 拖影/残影；
                                 改用 6–8 步大幅消除；快速动作更建议关 Turbo 回原生 20–24 步。
  - MiniMax H3 本地实操 30 坑  : 打斗/奔跑大动态镜头关 Turbo 用原生 20–24 步；
                                 SageAttention 在动作镜头出边缘虚影/撕裂 → 换 Kitchen Attention；
                                 加速导致闪烁/颜色跳动 → 成片关掉全部加速重跑对比。
  - 帧撕裂跳变 4 招             : 单次生成帧数砍半 / 8–15s 拆段；分辨率降一档；
                                 固定 seed + 上一段结尾做参考首帧接力；动作镜头单独拆细，
                                 拼接留 2–3 帧重叠。
  - 分场景参考权重              : 转头/大姿态 0.78–0.82；夜景逆光 0.79–0.83；
                                 静态慢镜 0.85–0.88。
  - 大动态负向词                : 仅精简增加「肢体畸形 / 手部崩坏 / 画面撕裂」，
                                 不堆砌以免锁死动态。
  - 后处理                      : LTX2.5 二次采样(≈0.45 降噪)/ SeedVR2 / FlashVSR /
                                 Topaz 超分修复残影与脸部模糊；
                                 ComfyUI-Spectrum-MiniMax-H3 的 ER-SDE forecast confetti
                                 修复 + offline smoothing replay 可去时序闪烁。
"""

NEG_FAST = "五官扭曲, 肢体穿模, 画面闪烁, 乱码文字, 画风突变, 肢体畸形, 手部崩坏, 画面撕裂"
NEG_STATIC = "五官扭曲, 肢体穿模, 画面闪烁, 乱码文字, 画风突变"


class BSAI_H3_MotionFix:
    """高速动作毛刺/噪点修复向导：按运动等级输出步数/注意力/参考权重/负向词/检查清单/后处理。"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "motion_level": (
                    ["fast_action 高速动作/打斗 (出拳/奔跑/转身)",
                     "medium 中等运动 (行走/手势/对话微动)",
                     "static_slow 静态慢镜 (站姿对话/氛围镜头)"],
                    {"default": "fast_action 高速动作/打斗 (出拳/奔跑/转身)"}),
                "use_turbo_lora": ("BOOLEAN", {"default": False,
                                               "label_on": "启用 Turbo/加速 LoRA",
                                               "label_off": "原生采样"}),
                "ref_weight": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0,
                                         "step": 0.01}),
                "clip_seconds": ("FLOAT", {"default": 8.0, "min": 1.0, "max": 30.0,
                                           "step": 1.0}),
                "attention": (
                    ["kitchen_attention", "sage_attention", "sla", "native 原生"],
                    {"default": "kitchen_attention"}),
            },
            "optional": {
                "base_negative": ("STRING", {"default": "", "multiline": True,
                                             "placeholder": "已有负向词（可选，会被合并）"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("recommended_steps", "attention_advice", "ref_weight_advice",
                    "negative_prompt", "checklist", "post_process")
    FUNCTION = "run"
    CATEGORY = "BSAI-Nodes/MiniMax-H3"
    OUTPUT_NODE = True  # allows running this node standalone; results visible in History

    def run(self, motion_level, use_turbo_lora, ref_weight, clip_seconds,
            attention, base_negative=""):
        level = "fast" if motion_level.startswith("fast") else (
            "medium" if motion_level.startswith("medium") else "static")

        # ── 采样步数 ──
        if level == "fast":
            if use_turbo_lora:
                steps = ("【建议】关闭 Turbo LoRA，回原生 20–24 步采样\n"
                         "  · 若必须用 Turbo：提高到 8 步（4 步在打斗/奔跑必然拖影/残影）\n"
                         "  · Turbo LoRA 需配完整基座权重，勿用于剪枝模型")
            else:
                steps = "【建议】原生采样 20–24 步（高速动作最稳档位）"
        elif level == "medium":
            steps = ("【建议】Turbo 用 6–8 步（勿用 4 步）；原生采样 20 步\n"
                     "  · 大姿态/转头镜头 ≤8 步时关闭 Turbo 更稳")
        else:
            steps = "【建议】Turbo 4–8 步即可（静态微动拖影风险低）；原生 20 步"

        # ── 注意力方案 ──
        if attention == "sage_attention":
            if level == "fast":
                att = ("【警告】SageAttention 在打斗/快速动作镜头易出边缘虚影与画面撕裂。\n"
                       "  → 动作镜头请切换为 Kitchen Attention（二者不可同开）")
            else:
                att = "SageAttention 可用于静态对话戏份；动作镜头请切换 Kitchen Attention"
        elif attention == "sla":
            att = ("SLA 稀疏注意力对 16G 以下显卡兼容性一般；若节点报红或加速冲突，"
                   "改用 Kitchen Attention。同一时间只启用一种注意力加速")
        else:
            att = "Kitchen Attention 适合动作镜头（相对 SageAttention 更稳，无撕裂/虚影）"

        # ── 参考权重 ──
        if level == "fast":
            rw = (f"【建议】参考权重降至 0.78–0.82（大姿态/转头/出拳，高权重会拉扯五官）；\n"
                  f"  当前 {ref_weight:.2f} → 请下调到 0.80 附近"
                  if ref_weight >= 0.85 else
                  f"【建议】参考权重保持在 0.78–0.82（当前 {ref_weight:.2f} 合适）")
        elif level == "medium":
            rw = f"【建议】参考权重 0.82–0.85（当前 {ref_weight:.2f}）"
        else:
            rw = f"【建议】参考权重 0.85–0.88 锁人设（当前 {ref_weight:.2f}）"

        # ── 负向词 ──
        neg = NEG_FAST if level == "fast" else NEG_STATIC
        if base_negative and base_negative.strip():
            merged = ", ".join([x for x in (base_negative.strip().rstrip(","), neg) if x])
            neg = merged

        # ── 检查清单 ──
        if level == "fast":
            checklist = (
                "① 拆段：单次生成 ≤8–15 秒（当前 %.0f 秒%s），帧数砍半最直接\n"
                "② 固定 seed + 用上一段结尾画面做参考首帧，分段接力生成\n"
                "③ 动作镜头单独拆细；后期拼接处留 2–3 帧重叠，不硬切\n"
                "④ 分辨率降一档（优先原生 1344×768），找稳定区间\n"
                "⑤ 若加速后仍闪烁/颜色跳动：成片关掉全部加速重跑一版对比\n"
                "⑥ 高权重 + 大动作=双重约束拉扯 → 按上方权重下调") % (clip_seconds,
                "（已拆段）" if clip_seconds <= 15 else " → 建议再拆短")
        elif level == "medium":
            checklist = (
                "① 单次生成 ≤15 秒；固定 seed 分段接力\n"
                "② 转头/侧身镜头参考权重 0.78–0.82\n"
                "③ 若拖影：步数提到 8 步或关 Turbo\n"
                "④ 分辨率保持 1344×768 原生")
        else:
            checklist = (
                "① 静态镜头可放长（≤20s），权重 0.85–0.88 锁人设\n"
                "② 负向词用精简通用版，勿堆砌以免画面变死板\n"
                "③ 关注时序漂移：每 4–6 个镜头重刷一次人设参考图")

        # ── 后处理 ──
        post = (
            "成片后处理（修残影/模糊/噪点）：\n"
            "  · LTX2.5 二次采样放大（≈0.45 降噪）→ 修复动作镜头脸部模糊/残影\n"
            "  · SeedVR2 / FlashVSR / Topaz 超分 → 768P 母片提至 1080P/4K\n"
            "  · ComfyUI-Spectrum-MiniMax-H3 → ER-SDE forecast confetti 修复 + offline\n"
            "    smoothing replay 去时序闪烁（保持 11 actual / 9 forecast 原生调度）\n"
            "  · 分块超分注意接缝与时间闪烁：正常速度播放两遍再逐帧验眼/嘴/发际线")

        ui = {"bsai_motionfix": {
            "recommended_steps": steps,
            "attention_advice": att,
            "ref_weight_advice": rw,
            "negative_prompt": neg,
            "checklist": checklist,
            "post_process": post,
        }}
        return (steps, att, rw, neg, checklist, post), {"ui": ui}


NODE_CLASS_MAPPINGS = {
    "BSAI_H3_MotionFix": BSAI_H3_MotionFix,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_H3_MotionFix": "BSAI H3 MotionFix 高速动作毛刺噪点修复向导",
}
