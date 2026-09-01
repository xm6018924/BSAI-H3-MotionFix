# BSAI H3 MotionFix v2.x · 打斗动作毛刺/模糊修复说明
# BSAI H3 MotionFix v2.x · Fight-Scene Glitch & Blur Fix Notes

> 中英双语 / Bilingual
> 适用工作流：
> - v2.0：`BSAI H3 MotionFix 打斗毛刺模糊修复 v2.0 (内置FlashVSR时序修复).json`
> - v2.1：`BSAI H3 MotionFix 打斗毛刺模糊修复 v2.1 (含原生20步终稿轨).json`（在 v2.0 基础上新增「原生 20–24 步终稿轨」）
> - v2.2：`BSAI H3 MotionFix 打斗毛刺模糊修复 v2.2 (参数优化 3轨对比).json`（3 轨对比 + 参数最优档，见第五章）
> - **v2.3（最新/推荐）**：`BSAI H3 MotionFix 打斗毛刺模糊修复 v2.3 (慢动作重拍 4轨对比).json`（v2.2 + 内置 MAINodes 慢动作重拍链，见第五章 5.6）
> - **v2.5（修复版，若 v2.3/v2.4 第 4 轨停跑用这个）**：`BSAI H3 MotionFix 打斗毛刺模糊修复 v2.5 (慢动作重拍 4轨对比·修复).json`（修复第 4 轨 model=None 停跑，见 5.7）

---

## 一、问题诊断（为什么还有毛刺和模糊）
## 1. Diagnosis (why glitches & blur persist)

**结论：原 v1 工作流已把生成侧参数压到 FastH3 4 步模型的极限，剩余毛刺/模糊是 4 步蒸馏模型对高速动作的固有缺陷 + 缺少后处理修复链。**
**Conclusion: v1 already pushed the generation-side settings to the limit of the FastH3 4-step distilled model. The remaining glitches/blur come from (a) the inherent limitation of 4-step distillation on fast motion, and (b) the missing post-process repair chain.**

| # | 根因 Root Cause | 证据 Evidence |
|---|---|---|
| 1 | **4 步蒸馏模型固有模糊/伪影**（打斗高速运动时时序闪烁、拖影）<br>4-step distillation is inherently soft/artifact-prone on fast motion | 快动作档 MotionFix 已输出 `vsa_enabled=False`（关 VSA）、0.5MP、5s 拆段、阶梯 999,749,500,250，均已正确接入——生成侧已到极限 |
| 2 | **输出直出、无时序修复链**<br>No temporal post-process fix chain | 原流程 VAEDecode → SaveVideo 直出；4K 分支仅 RTX 锐化超分，不修时序毛刺 |
| 3 | **负向词未接入采样**（H3 原生无 CFG，属提示性建议）<br>Negative prompt is advisory-only (H3 is CFG-free) | BasicGuider 仅接正向条件，负向词只接到 ShowText 显示 |
| 4 | **参考权重不可调**（ReferenceToVideo 无强度参数）<br>Ref strength not exposed on the ref node | MotionFix 的 ref_weight 仅输出建议文本 |

---

## 二、v2.0 改了什么
## 2. What changed in v2.0

### 新增：FlashVSR 时序修复输出分支（核心）
### New: FlashVSR temporal-repair output branch (core)

```
VAEDecode(视频帧) ──► FlashVSRNode(逐帧去噪+时间一致性+超分) ──► VHS_VideoCombine(合音轨) ──► mp4
                                                                    ▲
VAEDecodeAudio(音频) ──────────────────────────────────────────────┘
```

- **节点**：新增 `FlashVSRNode`（mode=tiny, scale=2, tiled）→ 新 `VHS_VideoCombine`，输出「BSAI MotionFix FlashVSR 时序修复」mp4（24fps + 音轨）。
- **作用**：逐帧去噪 + **时间一致性** 处理，是当前链路里对「打斗毛刺 + 模糊」最适配的修复（MotionFix 指引点名方案）。
- **注意**：FlashVSR 模型首次运行会从 HuggingFace 自动下载（`JunhaoZhuang/FlashVSR-v1.1`，较大，需联网耐心等待）。
- **Nodes**: new `FlashVSRNode` (mode=tiny, scale=2, tiled) → new `VHS_VideoCombine`, outputs "BSAI MotionFix FlashVSR 时序修复" mp4 (24fps + audio).
- **Effect**: per-frame denoise + **temporal consistency** — the most suitable fix for fight glitches + blur in this chain.
- **Note**: FlashVSR model auto-downloads from HuggingFace on first run (`JunhaoZhuang/FlashVSR-v1.1`, large; needs network & patience).

### 保留了原有分支 / Original branches kept
- 直出分支（SaveVideo）— 快速预览 FastH3 原片
- 4K 超分分支（BSAI_H3_Upscale4K → VHS）— 纯锐化放大
- 三条输出可同时对比，挑满意的一条

### MotionFix 节点指引同步升级
### MotionFix node guidance upgraded
- 快动作档检查清单新增 ⑦（内置 FlashVSR 分支）、⑧（原生 20–24 步终稿轨）
- 后处理建议新增内置 FlashVSR 分支说明
- Checklist adds ⑦ (built-in FlashVSR branch) & ⑧ (native 20–24-step final track); post-process advice updated.

---

## 三、使用方法 / How to use
1. 重启 ComfyUI（使 MotionFix 新指引生效，可选）。
2. 加载 `BSAI H3 MotionFix 打斗毛刺模糊修复 v2.0 (内置FlashVSR时序修复).json`。
3. 填入参考图（LoadImage）、提示词模板（散打对咏春），点 Run。
4. 输出三份：直出 / 4K超分 / **FlashVSR 时序修复**——重点看修复版。

---

## 四、终稿轨（根治 4 步模糊）— 终极方案
## 4. Final-quality track (root fix for 4-step blur) — the ultimate option

4 步蒸馏对高速打斗的模糊/毛刺属**模型固有**，若 FlashVSR 仍不满足：
The blur/artifacts of 4-step distillation on fast motion are **inherent to the model**. If FlashVSR is still not enough:

**切换原生模型 20–24 步重跑打斗镜头（模型已就绪）：**
**Switch to the native model at 20–24 steps for fight shots (models are ready):**

| 步骤 | 操作 |
|---|---|
| 1 | 把模型换成原生全量模型：`minimax_h3_fl2va_pruned_int8_convrot.safetensors`（FL2VA）或 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`（Ref2VA，多参考打斗更适配） |
| 2 | 采样改 **20–24 步**（KSampler steps=20~24），cfg 用 H3 惯例值 |
| 3 | VSA/加速全部关闭（MotionFix 指引 ⑤） |
| 4 | 分辨率保持 0.5MP，打斗镜头 ≤5s 拆段，固定 seed 接力 |
| 5 | 再用 v2.0 的 FlashVSR 分支过一遍，得到最终成片 |

> 权衡：原生 20–24 步速度远慢于 4 步，适合「打斗/动作终稿」；其余文戏/过渡镜头继续用 FastH3 4 步提速。
> Trade-off: native 20–24 steps is much slower than 4-step — use it for hero fight shots; keep FastH3 4-step for dialogue/transition shots.

---

## 五、v2.1 新增：原生 20 步终稿轨（根治 4 步模糊）
## 5. New in v2.1: Native 20-step final track (root fix for 4-step blur)

**v2.1 在 v2.0 基础上加入一条「原生 20–24 步终稿轨」，与 FastH3 4 步极速轨并存、一键切换。**
**v2.1 adds a "Native 20–24-step final track" alongside the FastH3 4-step fast track — switch with one click.**

```
（共享参考条件/音视频 VAE，自动跟随 文生/图生/多参 切换）
                 ┌──────────────────────────────────────────────┐
FastH3 4步极速轨  │  UNETLoader(ref2va_pruned_int8) → BasicGuider  │
(默认启用)        │  → res_multistep + BasicScheduler(20步)        │
                 │  → SamplerCustomAdvanced → VAEDecode(+fp16 VAE) │
                 │  → VHS 输出「BSAI MotionFix 原生20步 终稿」      │
                 └──────────────────────────────────────────────┘
```

**默认状态**：终稿轨 10 个节点（⑩ 个 BSAI MotionFix 终稿轨 ①–⑩）**全部静音（灰色）**，不影响 FastH3 快轨运行。
**Default state**: all 10 native-track nodes are **muted (grey)**; the FastH3 fast track runs as usual.

### 启用方法 / How to enable
1. 画布上**框选**所有标题含「BSAI MotionFix 终稿轨」的节点（①–⑩）。
2. 按 **Ctrl+M**（或右键 → Mute）取消静音 → 节点变亮。
3. 点 Run：终稿轨会用原生模型跑 **20 步**（步数可在「终稿轨 ④ 调度」改为 24），输出 `BSAI MotionFix 原生20步 终稿` mp4。
4. 对比 FastH3 4 步快轨 / FlashVSR 修复版 / 原生终稿版，选满意的一条。

### 终稿轨配置说明 / Track config
| 节点 | 配置 | 说明 |
|---|---|---|
| 终稿轨 ① UNETLoader | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 原生 Ref2VA 模型（多参考打斗最适配，已就绪 19.5GB） |
| 终稿轨 ② BasicGuider | cfg=1 | H3 原生引导（无 CFG） |
| 终稿轨 ③ KSamplerSelect | `res_multistep` | H3 原生推荐采样器 |
| 终稿轨 ④ BasicScheduler | simple / **20** 步（可改 24）/ denoise 1 | 步数即质量杠杆：20→24 更稳更慢 |
| 终稿轨 ⑦ VAELoader | `minimax_h3_video_vae_fp16.safetensors` | 原生 fp16 视频 VAE（与原生参考工作流一致） |
| 音频 | 复用 FastH3 轨 fp32 音频 VAE | 同一 H3 音频 VAE |

> 提示：如需改回 FL2VA（文生）模型，把 ① 的模型换成 `minimax_h3_fl2va_pruned_int8_convrot.safetensors`；参考条件接线不受影响。
> Tip: to switch to the FL2VA (text-driven) model, change ① to `minimax_h3_fl2va_pruned_int8_convrot.safetensors`; reference wiring is unaffected.

---

## 五.5、v2.2 新增：参数最优档（最新推荐）
## 5.5. New in v2.2: Optimized parameters (latest & recommended)

**v2.2 = v2.1（3 轨对比：FastH3 4步快轨 + FlashVSR 修复轨 + 原生终稿轨）基础上，按 2026-08-31 全网最新证据优化关键参数。**
**v2.2 = v2.1 (3-track: FastH3 4-step fast + FlashVSR repair + native final) with key params tuned per the latest community evidence (2026-08-31).**

### 参数变更 / Parameter changes
| 位置 | v2.1 | v2.2（优化后） | 依据 Evidence |
|---|---|---|---|
| FlashVSR scale | **4** | **2（官方默认）** | 4 倍放大对高动态打斗会**放大噪点/伪影**；官方默认 2，逐帧去噪+时间一致性最稳 |
| 原生终稿轨步数 | 20 | **24** | 社区共识打斗/大动态 20–24 步，取上限更稳（FlashVSR 修复轨不受影响） |

### 为什么 scale 从 4 降回 2
FlashVSR 的 `scale` 表示放大倍数（合法 2–4）。打斗帧本身高速运动+已有毛刺，4 倍放大会把噪点、振铃一起放大，反而更糊。**修复打斗毛刺的正确姿势是"时序去噪为主、放大为辅"**，scale=2 保留官方训练分布，稳定度最高。需要大分辨率时，走独立的 BSAI-H3-upscale-4K 分支，不要靠 FlashVSR 硬拉到 4 倍。

### 三轨如何选 / Which track to use
| 轨道 | 用途 | 速度 |
|---|---|---|
| FastH3 4步快轨 | 草稿/预览/文戏 | 极快 |
| FlashVSR 修复轨（默认看这个） | 快轨输出的毛刺/模糊修复 | 中 |
| 原生 24 步终稿轨（Ctrl+M 启用） | 打斗/动作终稿，根治 4 步模糊 | 慢 |

---

## 五.6、进阶可选：慢动作重拍链（MAINodes · 本机已装 · v2.3 已内置）
## 5.6. Advanced: Slow-motion re-shoot chain (MAINodes · installed · built into v2.3)

**原理**：打斗残影的本质是"一个 latent token 管 4 帧，高速时 4 帧要 4 个姿势，单 token 装不下、缺的姿势从未生成"。MAINodes 用「动作热力图检测→快动作区慢放(hold)→视频重绘(partial denoise)→按 hold map 恢复帧率」，相当于一次**慢动作重拍**，给模型更多时间轴空间补齐缺失姿势。与抖音 edgid noise 插件同原理。

**Principle**: fight smearing happens because one latent token covers 4 frames; at high speed the 4 frames need 4 poses a single token can't hold — the missing poses were never generated. MAINodes re-shoots the clip in slow-motion (Jerk heat → Time Smear hold → V2V redraw → Exact Recover) to give the model temporal room.

### v2.3 已内置该链路（默认静音，一键启用）
### v2.3 has this chain built-in (muted by default, enable in one click)

**v2.3 在 v2.2 基础上新增 16 个节点（id 48–63，标题前缀「BSAI MotionFix 重拍 ①–⑯」），全部默认静音。**
**v2.3 adds 16 nodes (id 48–63, titled "BSAI MotionFix 重拍 ①–⑯"), all muted by default.**

```
FastH3 主轨 Sampler 的 LATENT ──► H3JerkOracle(动作热力检测) ──► hold_map
FastH3 主轨 VAEDecode 的 IMAGE ─► H3TimeSmear(慢放) ──► VAEEncode ──► H3V2VInit
H3V2VInit.LATENT + 原生 ref2va 模型 + H3InjectSchedule(simple 25步 inject 0.7) + res_multistep
    ──► SamplerCustomAdvanced(二次采样) ──► VAEDecode/VAEDecodeAudio
    ──► H3ExactRecover(恢复帧率) + H3AudioRecover(音频恢复, pass1原声作参考)
    ──► CreateVideo ──► SaveVideo「BSAI MotionFix 慢动作重拍」
```

**启用方法 / How to enable**：
1. 框选标题含「BSAI MotionFix 重拍」的节点（①–⑯）→ **Ctrl+M** 取消静音。
2. 点 Run：主轨先出 FastH3 4 步片，随后重拍链用**原生 ref2va 模型（终稿轨同款）**做二次采样，输出「BSAI MotionFix 慢动作重拍」mp4。
3. 与 3 条旧轨对比，挑最干净的一版。

**接线说明 / Wiring**：
- 动作热力：`H3JerkOracle.samples` ← 主轨 Sampler 的 LATENT；`length` ← MotionFix.ref_length
- 慢放：`H3TimeSmear.images` ← 主轨 VAEDecode；`hold_map` ← JerkOracle
- 二次采样 conditioning：复制 ReferenceToVideo（接同样的 3 张参考图 + 提示词模板 + 分辨率），`length` ← TimeSmear 的新长度（慢放后变长）
- 二次采样模型：复用**原生 ref2va**（UNETLoader 38，终稿轨同款）→ 与 MAINodes 官方 pipeline 一致（用原生模型跑 pass2，不用 FastH3 4 步蒸馏做 partial denoise）
- 音频：重拍轨新音频经 `H3AudioRecover` 按 hold_map 恢复，`reference_mix=1` 保留 pass1 原声

**推荐参数（已在工作流预设）**：JerkOracle q=0.75, d_max=4, ramp=ON, bridge=8；InjectSchedule total_steps=25, inject=0.70（0.5 保原画细节 / 0.8 更发散）；H3V2VInit length=0(auto)；ExactRecover 仅删帧不重采样；H3AudioRecover reference_mix=1.0。

**注意 / Caveats**：
- 重拍链用原生 ref2va 模型做 pass2，会**显著增加时长**（25 步 partial denoise）——只在打斗关键镜头用。
- 重拍链与「原生终稿轨」共用 UNETLoader(38) 模型：若重拍链启用，终稿轨不必同时开（避免重复加载）。
- 二次采样是 partial denoise（inject 0.7），**不要**在 pass2 挂 Turbo LoRA 按蒸馏步数跑（会崩成马赛克）。
- 24GB 显存建议：一次只启用「重拍链」或「终稿轨」之一，不要同时跑满 4 轨。

---

## 五.7、v2.5 修复说明：第 4 轨停跑（model=None）
## 5.7. v2.5 fix: Track-4 stalls (model=None)

**现象 / Symptom**：主程序（FastH3 4 步轨）与第 2 轨（FlashVSR 修复）正常出片，轮到第 4 轨（慢动作重拍）直接停、无输出。

**根因 / Root cause**：v2.3/v2.4 中重拍链的二次采样 `BasicGuider` 与 `H3InjectSchedule` 的 model 取自「终稿轨」的 `UNETLoader(38)`；一旦把终稿轨整组 **BYPA（mode=4 绕过）**，38 不执行、其 MODEL 输出为 None，二次采样拿到 None 模型 → 链中断停跑。

**修复（v2.5）**：
1. **新增独立 `UNETLoader(65)`** 专供重拍链，加载原生 `minimax_h3_ref2va_pruned_int8_convrot`，重拍链的 `BasicGuider(53)` / `H3InjectSchedule(56)` 改接 65——不再依赖终稿轨的 38，终稿轨可自由 BYPA。
2. **H3AudioRecover(61)** fps 错位 1→24（之前音频按 1fps 恢复，时长错乱）。
3. **H3TimeSmear(49)** hold_map widget 清空（由 JerkOracle 输入接管，避免 widget 值干扰）。
4. **H3V2VInit(51)** freeze_grow 还原默认（避免误冻结背景）。

**用法 / How to use**：加载 v2.5 → 框选「BSAI MotionFix 重拍 ①–⑰」→ Ctrl+M 启用 → Run。重拍链自带独立模型加载，不再受终稿轨 BYPA 影响。

**提醒 / Caveat**：24GB 显存下，重拍链（独立 ref2va 19.5GB）与主轨 FastH3（21GB）会先后驻留显存，建议一次只启用「重拍链」或「终稿轨」之一，FlashVSR 修复轨可保留。

---
- 工作流 JSON 合法（v2.2：47 节点 / 68 连线），全部节点类已在运行中的 ComfyUI 注册（object_info 核对通过）。
- FlashVSRNode scale=2（合法区间 2–4）/ VHS_VideoCombine / 终稿轨各节点输入接线与节点 schema 一致。
- MotionFix 节点源码 `py_compile` 通过。
- v2.2: 47 nodes / 68 links; all node classes registered (verified via object_info); FlashVSR scale=2 within legal range; native-track wiring matches schemas.
- MotionFix node source passes `py_compile`.

**未尽事项 / Remaining**: FlashVSR 首次运行需联网下载模型；原生终稿轨首次启用会加载 19.5GB ref2va 模型（与 FastH3 轨同时启用时显存占用较高，建议终稿轨单独启用）；端到端出片未在本机 GPU 跑通验证（受限于生成时长），建议先跑一个 5s 打斗测试段对比快轨/修复/终稿三版。
