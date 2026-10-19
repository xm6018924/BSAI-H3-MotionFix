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
  - 最新补充（2026-08-31 全网核验）:
    · FastVideo 官方声明：4 步 FastH3 面向最低延迟，8 步是更高质量档；
      "difficult motion / fine detail 可能低于 base"——打斗成片用原生 20–24 步终稿轨根治。
    · SLA 稀疏注意力（社区 2026-08 最新加速）: 训练时专门补齐动态运动样本，
      对中远景人脸糊 + 拖影收敛好；6–8 步 + CFG 6–7 最稳；勿与 Turbo/Sage 混搭。
    · ComfyUI-MAINodes（H3 Jerk Oracle + Time Smear）: "慢动作重拍"方案——
      动作热力图检测→快动作区慢放(hold)→视频重绘(partial denoise)→按 hold map 恢复帧率，
      专修快速动作残影/拖影（与抖音 edgid nose 插件同原理）。
    · ComfyUI_Minimax_h3_latent_Upscaler（xmarre）: 学习式 3D latent 放大 + 低 sigma
      二次精修，修放大超 2 倍后的线条/碎玻璃瑕疵；h3_refinement 标记让 Spectrum/DiffAid
      识别为短低 sigma 二采。
    · MiniMax-H3 Turbo LoRA v4(step600): 4 步+大动作会有 motion-smear → 用 6–8 步消除；
      v4 静态/小动作/微细节最佳；重动作 4 步场景可回退 v1(850)。
    · 双采方案（社区实测）: 一采 8 步 LoRA(保基础内容) + 二采 4 步 LoRA(收敛更快边缘更清)，
      高动态飘动衣物边缘更清晰；LoRA 强度一采 0.75 / 二采 0.7 减少油腻。
    · FlashVSR 注意: scale 用官方默认 2，勿开 4 倍——高动态打斗 4 倍放大会放大噪点/伪影。
"""

NEG_FAST = "distorted facial features, limb clipping, flickering frame, garbled text, style shift, limb deformity, broken hands, screen tearing"
NEG_STATIC = "distorted facial features, limb clipping, flickering frame, garbled text, style shift"


class BSAI_H3_MotionFix:
    """高速动作毛刺/噪点修复向导：按运动等级输出步数/注意力/参考权重/负向词/检查清单/后处理。"""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "motion_level": (
                    ["fast_action (punch/run/turn)",
                     "medium (walk/gesture/dialogue micro-motion)",
                     "static_slow (static dialogue/atmosphere)"],
                    {"default": "fast_action (punch/run/turn)"}),
                "use_turbo_lora": ("BOOLEAN", {"default": False,
                                               "label_on": "Enable Turbo/accelerated LoRA",
                                               "label_off": "Native sampling"}),
                "ref_weight": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0,
                                         "step": 0.01}),
                "clip_seconds": ("FLOAT", {"default": 8.0, "min": 1.0, "max": 30.0,
                                           "step": 1.0}),
                "attention": (
                    ["kitchen_attention", "sage_attention", "sla", "native"],
                    {"default": "kitchen_attention"}),
            },
            "optional": {
                "base_negative": ("STRING", {"default": "", "multiline": True,
                                             "placeholder": "Existing negative prompt (optional, will be merged)"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING",
                    "BOOLEAN", "FLOAT", "STRING", "INT")
    RETURN_NAMES = ("recommended_steps", "attention_advice", "ref_weight_advice",
                    "negative_prompt", "checklist", "post_process",
                    "vsa_enabled", "video_keep_percent", "ladder", "ref_length")
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
                steps = ("Recommendation: turn off the Turbo LoRA and use native 20-24 step sampling\n"
                         "  - If you must use Turbo: raise to 8 steps (4 steps will smear/ghost on fights and running)\n"
                         "  - Turbo LoRA needs the full base weights; do not use it on pruned models")
            else:
                steps = "Recommendation: native 20-24 step sampling (most stable for fast action)"
        elif level == "medium":
            steps = ("Recommendation: Turbo 6-8 steps (not 4); native 20 steps\n"
                     "  - For large-pose/turn shots, turning Turbo off below 8 steps is more stable")
        else:
            steps = "Recommendation: Turbo 4-8 steps is fine (low smear risk for static micro-motion); native 20 steps"

        # ── 注意力方案 ──
        if attention == "sage_attention":
            if level == "fast":
                att = ("WARNING: SageAttention tends to produce edge ghosting and frame tearing on fight/fast-action shots.\n"
                       "  -> Switch action shots to Kitchen Attention (the two cannot be enabled together)")
            else:
                att = "SageAttention is acceptable for static dialogue scenes; switch action shots to Kitchen Attention"
        elif attention == "sla":
            att = ("SLA sparse attention (community latest, 2026-08): trained specifically with dynamic-motion samples, "
                   "converges well on mid/wide face blur and smearing; most stable with 6-8 steps + CFG 6-7, "
                   "suited to fights/running large motion. Note: compatibility is mediocre below 16GB VRAM; "
                   "if the node errors or accelerators conflict, switch back to Kitchen Attention; "
                   "enable only one attention accelerator at a time, never mix with Turbo/Sage")
        else:
            att = "Kitchen Attention is suited to action shots (more stable than SageAttention, no tearing/ghosting)"

        # ── 参考权重 ──
        if level == "fast":
            rw = (f"Recommendation: lower the reference weight to 0.78-0.82 (large pose/turn/punch; high weight distorts features);\n"
                  f"  current {ref_weight:.2f} -> please lower it toward 0.80"
                  if ref_weight >= 0.85 else
                  f"Recommendation: keep the reference weight at 0.78-0.82 (current {ref_weight:.2f} is fine)")
        elif level == "medium":
            rw = f"Recommendation: reference weight 0.82-0.85 (current {ref_weight:.2f})"
        else:
            rw = f"Recommendation: reference weight 0.85-0.88 to lock the character (current {ref_weight:.2f})"

        # ── 负向词 ──
        neg = NEG_FAST if level == "fast" else NEG_STATIC
        if base_negative and base_negative.strip():
            merged = ", ".join([x for x in (base_negative.strip().rstrip(","), neg) if x])
            neg = merged

        # ── 检查清单 ──
        if level == "fast":
            checklist = (
                "1) Split segments: generate <=5 s at a time (currently %.0f s%s), halving the frame count is the most direct fix\n"
                "2) Lower resolution to the 0.5MP tier (16:9 -> 960x544 / portrait -> 768x1344): "
                "the 4-step distilled model inevitably glitches on 1MP fast action; one tier down is most effective\n"
                "3) Fix the seed and use the previous segment's last frame as the reference first frame for relay generation\n"
                "4) Split action shots finer; keep 2-3 overlapping frames at joins instead of hard cuts\n"
                "5) If glitches/flicker persist: rerun a comparison with ALL acceleration off (VSA/Sage/Turbo)\n"
                "6) High weight + large motion = double constraint pull -> lower the reference weight to 0.78-0.82\n"
                "7) The v2.0 workflow already has a FlashVSR temporal-fix branch: VAEDecode->FlashVSR(deglitch+SR)->compose. "
                "Per-frame denoise + temporal consistency directly fixes fight glitches/blur; keep scale at 2 (do not open 4x)\n"
                "8) Final master track: switch fight shots to the native 20-24 step model "
                "(minimax_h3_fl2va_pruned_int8_convrot / ref2va_pruned_int8_convrot are ready). "
                "Blur/glitch on fast fights is inherent to the 4-step distill; native steps fix it; "
                "built into the workflow since v2.1 (muted by default, Ctrl+M enables one-click A/B)\n"
                "9) If fights still smear: use SLA sparse attention + 6-8 steps + CFG 6-7 (adds dynamic samples, "
                "converges well on mid/wide faces and smears); enable only one accelerator, never mix with Turbo/Sage\n"
                "10) Slow-motion re-shoot (ComfyUI-MAINodes): Jerk Oracle motion heat -> Time Smear slow-down "
                "-> re-render -> restore frame rate, purpose-built for fast-action ghosting; equivalent to the edgid-nose plugin") % (clip_seconds,
                " (already split)" if clip_seconds <= 5 else " -> split shorter")
        elif level == "medium":
            checklist = (
                "1) Generate <=15 s per run; fix the seed and use segment relay\n"
                "2) Turn/profile shots: reference weight 0.78-0.82\n"
                "3) If smearing: raise steps to 8 or turn Turbo off\n"
                "4) Keep the native 1344x768 resolution")
        else:
            checklist = (
                "1) Static shots can run long (<=20s); weight 0.85-0.88 locks the character\n"
                "2) Use the concise generic negative prompt; don't pile on terms or the frame becomes stiff\n"
                "3) Watch for temporal drift: refresh the character reference image every 4-6 shots")

        # ── 后处理 ──
        post = (
            "Post-processing for the final cut (fixes ghosting/blur/noise):\n"
            "  - The v2.0+ workflow has a FlashVSR temporal-fix branch (VAEDecode->FlashVSR->compose), "
            "per-frame denoise + temporal consistency, the best-fit glitch/noise fix in this pipeline; keep scale at 2, "
            "4x upscale amplifies noise/artifacts on high-dynamic fights (model auto-downloads on first run)\n"
            "  - Slow-motion re-shoot (ComfyUI-MAINodes Jerk Oracle + Time Smear): motion heat -> slow-down -> re-render -> restore frame rate, "
            "purpose-built for H3 fast-action ghosting (equivalent to the edgid-nose plugin)\n"
            "  - latent upscaler + refine (ComfyUI_Minimax_h3_latent_Upscaler): learned 3D upscale + "
            "low-sigma second pass, fixes line/crushed-glass artifacts above 2x; h3_refinement hooks into Spectrum/DiffAid\n"
            "  - FlashVSR_Ultra_Fast video SR (or use the Topaz/FlashVSR tier of BSAI-H3-upscale-4K)\n"
            "  - LTX2.5 second-pass upscale (~0.45 denoise) -> fixes facial blur/ghosting on action shots\n"
            "  - SeedVR2 / Topaz SR -> lifts the 768P master to 1080P/4K\n"
            "  - ComfyUI-Spectrum-MiniMax-H3 -> ER-SDE forecast confetti fix + offline\n"
            "    smoothing replay removes temporal flicker (keep the native 11 actual / 9 forecast schedule)\n"
            "  - Tiled SR: watch seams and temporal flicker; play through twice at normal speed, then check eyes/mouth/hairline per frame")

        # ── FastH3 蒸馏模型驱动输出（自动接入 BSAI-FastH3 极速链路）──
        # 注：FastH3 是 4-step 蒸馏模型（ladder 用训练跳点，勿改阶梯），
        #     高速动作画面噪点/毛刺/拖影的主因是 VSA 稀疏注意力丢细节 → 关 VSA / 提高 keep_percent。
        if level == "fast":
            vsa_enabled = False          # 高速动作关 VSA → Dense 注意力防边缘虚影/毛刺
            video_keep_percent = 35.0    # 若保留 VSA，把保留百分比提到 ~35% 保细节
        elif level == "medium":
            vsa_enabled = True
            video_keep_percent = 20.0
        else:
            vsa_enabled = True
            video_keep_percent = 10.0    # 静态默认官方值
        ladder = "999,749,500,250"       # FastH3 v0.2 训练 4 步阶梯（勿用均匀网格）
        ref_length = max(5, int(round(clip_seconds * 24)))  # 24fps 帧数

        ui = {"bsai_motionfix": {
            "recommended_steps": steps,
            "attention_advice": att,
            "ref_weight_advice": rw,
            "negative_prompt": neg,
            "checklist": checklist,
            "post_process": post,
            "vsa_enabled": vsa_enabled,
            "video_keep_percent": video_keep_percent,
            "ladder": ladder,
            "ref_length": ref_length,
        }}
        # 注意：ComfyUI 要求 ui dict 放在返回元组【内部】（平铺），
        # 写成 `(a,...,j), {"ui": ui}` 会变成嵌套元组，导致 output_data 长度错乱，
        # 一旦该节点有下游连接，cache_update 的 outputs[from_socket] 必然越界(IndexError)。
        return (steps, att, rw, neg, checklist, post,
                vsa_enabled, video_keep_percent, ladder, ref_length,
                {"ui": ui})


NODE_CLASS_MAPPINGS = {
    "BSAI_H3_MotionFix": BSAI_H3_MotionFix,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_H3_MotionFix": "BSAI H3 MotionFix (fast-action glitch & noise repair guide)",
}
