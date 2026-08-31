# BSAI-H3-MotionFix

面向 **ComfyUI MiniMax H3** 在**高速运动 / 人物快速动作（打斗、奔跑、大位移、转身）**下出现的
**毛刺、拖影/残影（motion-smear / trailing ghosting）、帧撕裂、时序闪烁与噪点**问题的修复向导节点。

画面问题类型（参考：夜晚室内格斗、出拳带动态模糊的高动态镜头）：
- 快速动作边缘毛刺 / 鬼影拖尾
- 帧间跳变、上下半帧撕裂
- 加速后画面闪烁、颜色跳动
- 动态场景脸部/肢体模糊、噪点

## 节点

| 节点 | 说明 |
| --- | --- |
| **BSAI H3 MotionFix 高速动作毛刺噪点修复向导** | 输入运动等级 / 是否 Turbo / 参考权重 / 片段时长 / 注意力方案 → 输出 6 组修复配置：推荐步数、注意力建议、参考权重建议、大动态负向词、检查清单、后处理方案 |

纯规则引擎（无模型加载、零显存、零耗时），执行即出方案，可直接照抄进现有 H3 工作流。

## 核心结论（2026-08-31 全网交叉核验）

### 1. 采样/加速层（源头最有效）
| 问题 | 结论 | 来源 |
| --- | --- | --- |
| Turbo LoRA 打斗/奔跑拖影残影 | 4 步必出 motion-smear → **提高到 6–8 步**；大动态镜头**关 Turbo 回原生 20–24 步** | ComfyUI-MiniMax-H3-Turbo；MiniMax H3 30 坑 #23 |
| SageAttention 动作镜头虚影/撕裂 | 动作镜头**切换 Kitchen Attention**，二者不可同开 | MiniMax H3 30 坑 #24 |
| SLA 报红/冲突 | 16G 以下显卡兼容差，改用 Kitchen Attention，同一时间只启用一种 | 30 坑 #25/#26 |
| 加速后闪烁/颜色跳动 | 部分加速牺牲色彩稳定性 → **成片关掉全部加速重跑对比** | 30 坑 #27 |

### 2. 片段/时序稳定性（帧撕裂跳变）
- 单次生成**帧数砍半 / 按 8–15 秒拆段**（时序误差累积是根因）
- **固定 seed + 上一段结尾做参考首帧**分段接力
- **动作镜头单独拆细**，拼接处留 2–3 帧重叠
- 分辨率降一档找稳定区间（原生 1344×768）
- 来源：《MiniMax-H3 漫剧视频帧撕裂跳变 4 招根治》

### 3. 提示词层
- **大动态专用负向词**（精简，勿堆砌以免锁死动态）：
  `五官扭曲, 肢体穿模, 画面闪烁, 乱码文字, 画风突变, 肢体畸形, 手部崩坏, 画面撕裂`
- **分场景参考权重**：转头/大姿态 0.78–0.82；夜景逆光 0.79–0.83；静态慢镜 0.85–0.88
- 来源：《吃透 MiniMax H3 3 个细节错误》

### 4. 后处理层（补救）
- **LTX2.5 二次采样放大**（≈0.45 降噪）修复动作镜头脸部模糊/残影
- **SeedVR2 / FlashVSR / Topaz** 768P→1080P/4K 超分
- **ComfyUI-Spectrum-MiniMax-H3**：修复 ER-SDE forecast "confetti" 污染（solver-space denoised interpolation）+ offline smoothing replay 去时序闪烁；保持原生 11 actual / 9 forecast 调度
- 分块超分注意接缝与时间闪烁，正常速度播放两遍再逐帧验细节

## 安装

**ComfyUI-Manager 一键安装**（已提交官方注册列表，PR: [Comfy-Org/ComfyUI-Manager#3228](https://github.com/Comfy-Org/ComfyUI-Manager/pull/3228)）：
在 ComfyUI-Manager → Custom Nodes Manager → 搜索 `BSAI-H3-MotionFix` → Install。

命令行安装：
```
cd ComfyUI/custom_nodes
git clone https://github.com/xm6018924/BSAI-H3-MotionFix BSAI-H3-MotionFix
```

或直接复制本目录到 `custom_nodes/`，重启 ComfyUI 即可。无第三方依赖。

## 使用

1. 在任意 H3 工作流画布中右键 → Add Node → `BSAI-Nodes/MiniMax-H3` → `BSAI H3 MotionFix 高速动作毛刺噪点修复向导`
2. 选择运动等级（高速动作/中等/静态慢镜）、是否启用 Turbo、当前参考权重、片段时长、注意力方案
3. **节点面板内会实时显示"修复方案"卡**（创建即显示、参数一变即刷新，无需执行）：
   - 推荐步数 / 注意力建议 / 参考权重建议 / 大动态负向词 / 执行清单 / 后处理方案
4. 执行（Queue）一次，节点 6 个 STRING 输出可接下游：
   - `recommended_steps` → 填到采样步数 / BasicScheduler
   - `attention_advice` → 选择注意力节点
   - `ref_weight_advice` → 填到 H3 参考强度
   - `negative_prompt` → 直接可复制进负向提示词框（或接 CONDITIONING）
   - `checklist` / `post_process` → 逐项执行

## 示例工作流

| 文件 | 说明 |
| --- | --- |
| `workflows/BSAI H3 高速运动毛刺噪点修复应用工作流.json` | **应用示例（推荐）**：完整 H3 生成链 + MotionFix 节点；`negative_prompt` 已自动接入 CLIPTextEncode 生成大动态负向 CONDITIONING，附应用映射说明 Note |
| `workflows/BSAI H3 高速运动毛刺噪点修复工作流 v1.0.json` | 简洁版：MotionFix 节点 + 完整 H3 生成链 |

（前端工作流目录 `ComfyUI/user/default/workflows/` 也各存一份，可直接从工作流菜单加载。）

## 文件结构

```
BSAI-H3-MotionFix/
├── __init__.py                  # 注册入口 + WEB_DIRECTORY
├── bsai_h3_motion_fix.py        # 后端规则引擎节点（6 STRING 输出）
├── web/js/bsai_h3_motion_fix.js # 前端实时方案卡（参数变化即时刷新）
├── workflows/                   # 示例工作流（应用版 + 简洁版）
└── README.md
```
