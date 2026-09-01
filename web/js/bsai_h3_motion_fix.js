import { app } from "../../../scripts/app.js";

// BSAI-H3-MotionFix frontend
// 纯前端规则引擎：节点创建 / 参数变化时实时计算并展示"修复方案卡"，
// 与后端 bsai_h3_motion_fix.py 的规则保持一致（6 个 STRING 输出仍可连下游）。

const NEG_FAST = "五官扭曲, 肢体穿模, 画面闪烁, 乱码文字, 画风突变, 肢体畸形, 手部崩坏, 画面撕裂";
const NEG_BASE = "五官扭曲, 肢体穿模, 画面闪烁, 乱码文字, 画风突变";

function buildPlan(motion, turbo, refW, seconds, attention, baseNeg) {
  const L = [];
  const motionKey = (motion || "").toLowerCase();
  const fast = motionKey.indexOf("fast") >= 0;
  const med = motionKey.indexOf("medium") >= 0;
  const stat = motionKey.indexOf("static") >= 0;

  // 1. 步数
  let steps;
  if (fast) steps = turbo ? "Turbo ≥8 步（4 步必出拖影/残影）\n  · 大动态更稳：关 Turbo 回原生 20–24 步" : "关闭 Turbo，原生 20–24 步";
  else if (med) steps = turbo ? "Turbo 6–8 步（勿用 4 步）" : "原生采样 20 步";
  else steps = turbo ? "Turbo 4–8 步（静态拖影风险低）" : "原生 20 步";

  // 2. 注意力
  const att = (attention || "").toLowerCase();
  let attAdvice = "Kitchen Attention 适合动作镜头（无撕裂/虚影）";
  if (fast && att.indexOf("sage") >= 0) attAdvice = "【警告】SageAttention 在打斗/快速动作镜头易出边缘虚影与撕裂 → 请切换 Kitchen Attention（二者不可同开）";
  else if (att.indexOf("sage") >= 0) attAdvice = "SageAttention 用于非动作镜头可接受；动作镜头仍建议 Kitchen Attention";
  else if (att.indexOf("kitchen") >= 0) attAdvice = "Kitchen Attention 正确选择（动作镜头稳定，无撕裂）";

  // 3. 参考权重
  let rwAdvice;
  if (fast) rwAdvice = "0.78–0.82（大姿态/转头/出拳，高权重会拉扯五官）";
  else if (med) rwAdvice = "0.82–0.85（中幅运动，姿态与身份平衡）";
  else rwAdvice = "0.85–0.88（锁人设/静态对话）";
  rwAdvice += `（当前 ${refW}）`;
  if (fast && refW > 0.85) rwAdvice += "  → 请下调，高权重+大动作=双重约束拉扯会五官错位";

  // 4. 负向词
  let neg = fast ? NEG_FAST : NEG_BASE;
  if (baseNeg && baseNeg.trim()) neg = baseNeg.trim() + ", " + neg;
  neg = "clip 负面: " + neg;

  // 5. 检查清单
  let checklist;
  if (fast) {
    const seg = (Number(seconds) || 0) <= 5 ? "（已拆段）" : " → 建议再拆短";
    checklist = [
      `① 拆段：单次生成 ≤5 秒（当前 ${seconds || "?"}s${seg}），帧数再砍半最直接`,
      "② 分辨率降到 0.5MP 档（16:9→960×544 / 竖屏→768×1344）：4-step 蒸馏模型在 1MP 高速动作必然毛刺，降一档最有效",
      "③ 固定 seed + 用上一段结尾画面做参考首帧，分段接力生成",
      "④ 动作镜头单独拆细；后期拼接处留 2–3 帧重叠，不硬切",
      "⑤ 若仍毛刺/闪烁：成片关掉全部加速（VSA/Sage/Turbo）重跑一版对比",
      "⑥ 高权重 + 大动作=双重约束拉扯 → 参考权重下调到 0.78–0.82",
    ];
  } else if (med) {
    checklist = [
      `① 单次生成 ≤15 秒（当前 ${seconds || "?"}s），固定 seed 分段接力`,
      "② 转头/侧身镜头参考权重 0.78–0.82",
      "③ 若拖影：步数提到 8 步或关 Turbo",
      "④ 分辨率保持 1344×768 原生",
    ];
  } else {
    checklist = [
      "① 静态镜头可放长（≤20s），权重 0.85–0.88 锁人设",
      "② 负向词用精简通用版，勿堆砌以免画面变死板",
      "③ 关注时序漂移：每 4–6 个镜头重刷一次人设参考图",
    ];
  }

  // 6. 后处理
  let post = [
    "· FlashVSR_Ultra_Fast 视频超分（逐帧去噪 + 时间一致性）→ 本链路最适配的毛刺/噪点修复（也可用 BSAI-H3-upscale-4K 的 Topaz/FlashVSR 档）",
    "· LTX2.5 二次采样放大（≈0.45 降噪）→ 修复动作镜头脸部模糊/残影",
    "· SeedVR2 / Topaz 超分 → 768P 母片提至 1080P/4K",
    "· ComfyUI-Spectrum-MiniMax-H3：ER-SDE forecast 污染修复 + offline smoothing 去时序闪烁",
    "· 分块超分注意接缝与时间闪烁：正常速度播放两遍再逐帧验眼/嘴/发际线",
  ];

  // 7. FastH3 蒸馏模型驱动配置（自动接入 BSAI-FastH3 极速链路）
  let vsa, keep, ladder = "999,749,500,250", len;
  if (fast) { vsa = "关（Dense 注意力，防边缘虚影/毛刺）"; keep = "35%"; }
  else if (med) { vsa = "开"; keep = "20%"; }
  else { vsa = "开"; keep = "10%"; }
  len = Math.max(5, Math.round((Number(seconds) || 8) * 24));
  let drive = [
    "· vsa_enabled = " + vsa,
    "· video_keep_percent = " + keep + "（VSA 保留 tile 百分比，越高细节损失越小）",
    "· ladder = " + ladder + "（FastH3 v0.2 训练 4 步阶梯，勿改）",
    "· ref_length = " + len + "（" + (Number(seconds) || 8) + "s @ 24fps）→ 连 ReferenceToVideo/ImageToVideo.length",
  ];

  return [
    "═══ 推荐步数 ═══\n" + steps,
    "\n═══ 注意力方案 ═══\n" + attAdvice,
    "\n═══ 参考权重 ═══\n" + rwAdvice,
    "\n═══ 大动态负向词 ═══\n" + neg,
    "\n═══ FastH3 驱动配置 ═══\n" + drive.join("\n"),
    "\n═══ 执行清单 ═══\n" + checklist.join("\n"),
    "\n═══ 后处理 ═══\n" + post.join("\n"),
  ].join("\n");
}

function readParams(node) {
  const g = (name) => {
    const w = node.widgets && node.widgets.find(x => x.name === name);
    return w ? w.value : undefined;
  };
  return {
    motion: g("motion_level"),
    turbo: !!g("use_turbo_lora"),
    refW: g("ref_weight"),
    seconds: g("clip_seconds"),
    attention: g("attention"),
    baseNeg: g("base_negative"),
  };
}

function refresh(node) {
  if (!node || !node._bsaiOut) return;
  const p = readParams(node);
  node._bsaiOut.value = buildPlan(p.motion, p.turbo, p.refW, p.seconds, p.attention, p.baseNeg);
}

app.registerExtension({
  name: "BSAI.H3.MotionFix",
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name !== "BSAI_H3_MotionFix") return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
      if (!this._bsaiOut) {
        this._bsaiOut = this.addWidget(
          "string", "修复方案 (实时)", "",
          () => {}, { multiline: true, serialize: false }
        );
        const onCfgChange = this.onConfigChanged;
        this.onConfigChanged = function (info) {
          if (onCfgChange) onCfgChange.apply(this, arguments);
          if (info && info.widget) refresh(this);
          else setTimeout(() => refresh(this), 50);
        };
        setTimeout(() => refresh(this), 100);
      }
      return r;
    };
  },
});
