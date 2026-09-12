# BSAI-H3-MotionFix ｜ BSAI-H3-MotionFix

**MiniMax H3 高速运动/快速动作「毛刺 & 噪点」修复向导 / Glitch & Noise Fix Guide for MiniMax H3 fast-motion clips**

> 中英双语文档 / Bilingual documentation.

## 插件介绍 / Introduction

面向 ComfyUI MiniMax H3 在**高速运动、人物快速动作**（打斗 / 奔跑 / 大位移镜头）下出现的画面毛刺、拖影/残影（motion-smear / trailing ghosting）、帧撕裂、时序闪烁与噪点问题，**一键输出可直接照抄的修复配置**（步数 / 注意力 / 参考权重 / 负向词 / 检查清单 / 后处理方案）。

For MiniMax H3 clips with **high-speed motion and fast action** (fights / running / large camera moves) that show glitches, motion-smear, frame tearing, temporal flicker or noise, this node **outputs ready-to-copy fix configs** (steps / attention / ref weight / negative prompt / checklist / post-processing).

方案依据：2026-08-31 全网交叉核验（ComfyUI-MiniMax-H3-Turbo 官方、MiniMax H3 本地实操 30 坑、FastVideo 官方声明、SLA 稀疏注意力社区方案、MAINodes 慢动作重拍等），详细依据见 `workflows/README-MotionFix-v2.0-打斗毛刺模糊修复说明.md`。/ Based on cross-verified community & official sources (2026-08-31); see the bilingual fix notes under `workflows/`.

---

## 节点 / Node

### BSAI_H3_MotionFix · 修复向导

**分类 / Category:** `BSAI-Nodes/MiniMax-H3` · 输出节点（可单独运行，结果在 History 可见）

#### 参数 / Parameters

| 参数 / Parameter | 类型 | 默认值 / Default | 说明 / Description |
|---|---|---|---|
| `motion_level` | 下拉 | fast_action | `fast_action 高速动作/打斗` / `medium 中等运动` / `static_slow 静态慢镜` |
| `use_turbo_lora` | BOOLEAN | False | 启用 Turbo/加速 LoRA（打斗镜头建议关闭，回原生 20–24 步）/ Use Turbo LoRA |
| `ref_weight` | FLOAT | 0.85 | 参考权重（0.0-1.0）/ Reference image weight |
| `clip_seconds` | FLOAT | 8.0 | 片段时长（1-30 秒）/ Clip length |
| `attention` | 下拉 | kitchen_attention | `kitchen_attention` / `sage_attention` / `sla` / `native 原生` |
| `base_negative` | STRING(可选) | "" | 已有负向词（可选，自动合并）/ Existing negative prompt (merged) |

#### 输出 / Outputs

| 端口 / Port | 说明 / Description |
|---|---|
| `recommended_steps` | 建议采样步数（按运动等级 + Turbo 状态）/ Recommended steps |
| `attention_advice` | 注意力方案建议（Kitchen / Sage / SLA 取舍）/ Attention advice |
| `ref_weight_advice` | 参考权重建议（大动态 0.78-0.82 / 夜景逆光 0.79-0.83 / 静态慢镜 0.85-0.88）/ Ref weight advice |
| `negative_prompt` | 大动态负向词（精简，防锁死动态）/ Negative prompt |
| `checklist` | 帧撕裂跳变 4 招检查清单 / Checklist |
| `post_process` | 后处理方案（LTX2.5 二采 / SeedVR2 / FlashVSR / Topaz 等）/ Post-processing |
| `vsa_enabled` | VSA 建议开关 / VSA recommendation |
| `video_keep_percent` | VSA 保留百分比建议 / VSA keep % |
| `ladder` | 时间步阶梯建议 / Timestep ladder |
| `ref_length` | 参考长度建议 / Reference length |

---

## 示例工作流 / Example Workflows

本仓库 `workflows/` 目录包含完整可用的极速生成套件与修复说明：

### 1. `workflows/BSAI-ComfyUI-FastH3-(VSA稀疏注意力)极速生成套件 v2.10 PDD加速.json`

**FastH3 VSA 极速生成套件 v2.10 PDD 加速版**（71 节点完整工作流）：
- 4 步蒸馏 FastH3 + VSA 视频稀疏注意力 + PDD 加速
- 内置 **MotionFix 慢动作重拍修复链**：动作热力图检测 → 快动作区慢放（hold）→ 视频重绘（partial denoise）→ 按 hold map 恢复帧率，专修快速动作残影/拖影
- 加载后按你的模型路径设置 `unet_name` / 参考图即可运行

### 2. `workflows/README-MotionFix-v2.0-打斗毛刺模糊修复说明.md`

**打斗毛刺模糊修复完整说明（中英双语，18KB）**，含：
- 问题诊断：4 步蒸馏模型对高速动作的固有缺陷 + 修复链必要性
- v2.0 → v2.9 全版本演进记录（3 轨对比 / 慢动作重拍 / 帧数修复 / turbo 加速 / w4a8 优化）
- 5 章详解：参数最优档、MAINodes 慢动作重拍链、FlashVSR 时序修复、FastH3 套件 v1.2 ghost-link 修复等

---

## 安装 / Installation

1. 将 `BSAI-H3-MotionFix` 放入 `ComfyUI/custom_nodes/` / Copy into `custom_nodes`
2. 重启 ComfyUI / Restart ComfyUI
3. 搜索 `BSAI_H3_MotionFix` 或 `MotionFix` 添加节点 / Search in node list
4. 配合 FastH3 / MiniMax H3 工作流使用 / Use inside your FastH3 / H3 workflow

**无额外依赖**，仅需 ComfyUI + MiniMax H3 模型环境。/ No extra dependencies beyond your H3 environment.

---

## License / 许可证

Apache-2.0。
