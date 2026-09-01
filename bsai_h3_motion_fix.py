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
            att = ("SLA 稀疏注意力（社区 2026-08 最新）：训练时专门补齐动态运动样本，"
                   "对中远景人脸糊 + 拖影收敛好；配 6–8 步 + CFG 6–7 最稳，"
                   "适合打斗/奔跑大动态。注意：16G 以下显卡兼容性一般，节点报红或加速冲突时"
                   "改回 Kitchen Attention；同一时间只启用一种注意力加速，勿与 Turbo/Sage 混搭")
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
                "① 拆段：单次生成 ≤5 秒（当前 %.0f 秒%s），帧数再砍半最直接\n"
                "② 分辨率降到 0.5MP 档（16:9→960×544 / 竖屏→768×1344）："
                "4-step 蒸馏模型在 1MP 高速动作必然毛刺，降一档最有效\n"
                "③ 固定 seed + 用上一段结尾画面做参考首帧，分段接力生成\n"
                "④ 动作镜头单独拆细；后期拼接处留 2–3 帧重叠，不硬切\n"
                "⑤ 若仍毛刺/闪烁：成片关掉全部加速（VSA/Sage/Turbo）重跑一版对比\n"
                "⑥ 高权重 + 大动作=双重约束拉扯 → 参考权重下调到 0.78–0.82\n"
                "⑦ v2.0 工作流已内置 FlashVSR 时序修复分支：VAEDecode→FlashVSR(去毛刺+超分)→合成。"
                "逐帧去噪 + 时间一致性，对打斗毛刺/模糊最直接有效；scale 保持 2（勿开 4 倍放大）\n"
                "⑧ 终稿轨：打斗镜头改用原生 20–24 步模型"
                "（minimax_h3_fl2va_pruned_int8_convrot / ref2va_pruned_int8_convrot 已就绪）。"
                "4 步蒸馏对高速打斗的模糊/毛刺属模型固有，原生步数可根治；v2.1 起已内置"
                "该终稿轨（默认静音，Ctrl+M 启用一键对比）\n"
                "⑨ 若打斗仍拖影：用 SLA 稀疏注意力 + 6–8 步 + CFG 6–7（专补动态样本，"
                "中远景人脸与拖影收敛好）；同一时间只启用一种加速，勿与 Turbo/Sage 混搭\n"
                "⑩ 慢动作重拍方案（ComfyUI-MAINodes）: Jerk Oracle 动作热力→Time Smear 慢放"
                "→重绘→恢复帧率，专修快速动作残影；等效抖音 edgid nose 插件") % (clip_seconds,
                "（已拆段）" if clip_seconds <= 5 else " → 建议再拆短")
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
            "  · v2.0+ 工作流已内置 FlashVSR 时序修复分支（VAEDecode→FlashVSR→合成），"
            "逐帧去噪 + 时间一致性，是本链路最适配的毛刺/噪点修复；scale 保持 2，"
            "4 倍放大对高动态打斗会放大噪点/伪影（首跑自动下载模型）\n"
            "  · 慢动作重拍（ComfyUI-MAINodes Jerk Oracle+Time Smear）：动作热力→慢放→重绘→恢复帧率，"
            "H3 快速动作残影专修（等效抖音 edgid nose）\n"
            "  · latent upscaler + 精修（ComfyUI_Minimax_h3_latent_Upscaler）：学习式 3D 放大 + "
            "低 sigma 二采，修放大超 2 倍线条/碎玻璃瑕疵；与 Spectrum/DiffAid 联动 h3_refinement\n"
            "  · FlashVSR_Ultra_Fast 视频超分（也可用 BSAI-H3-upscale-4K 的 Topaz/FlashVSR 档）\n"
            "  · LTX2.5 二次采样放大（≈0.45 降噪）→ 修复动作镜头脸部模糊/残影\n"
            "  · SeedVR2 / Topaz 超分 → 768P 母片提至 1080P/4K\n"
            "  · ComfyUI-Spectrum-MiniMax-H3 → ER-SDE forecast confetti 修复 + offline\n"
            "    smoothing replay 去时序闪烁（保持 11 actual / 9 forecast 原生调度）\n"
            "  · 分块超分注意接缝与时间闪烁：正常速度播放两遍再逐帧验眼/嘴/发际线")

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
    "BSAI_H3_MotionFix": "BSAI H3 MotionFix 高速动作毛刺噪点修复向导",
}
