import { app } from "../../../scripts/app.js";

// BSAI-H3-MotionFix frontend
// 纯前端规则引擎：节点创建 / 参数变化时实时计算并展示"修复方案卡"，
// 与后端 bsai_h3_motion_fix.py 的规则保持一致（6 个 STRING 输出仍可连下游）。

const NEG_FAST = "distorted facial features, limb clipping, flickering frame, garbled text, style shift, limb deformity, broken hands, screen tearing";
const NEG_BASE = "distorted facial features, limb clipping, flickering frame, garbled text, style shift";

function buildPlan(motion, turbo, refW, seconds, attention, baseNeg) {
  const L = [];
  const motionKey = (motion || "").toLowerCase();
  const fast = motionKey.indexOf("fast") >= 0;
  const med = motionKey.indexOf("medium") >= 0;
  const stat = motionKey.indexOf("static") >= 0;

  // 1. 步数
  let steps;
  if (fast) steps = turbo ? "Turbo >=8 steps (4 steps always smear/ghost)\n  - More stable for large motion: Turbo off, native 20-24 steps" : "Turbo off, native 20-24 steps";
  else if (med) steps = turbo ? "Turbo 6-8 steps (not 4)" : "Native 20 steps";
  else steps = turbo ? "Turbo 4-8 steps (low static smear risk)" : "Native 20 steps";

  // 2. 注意力
  const att = (attention || "").toLowerCase();
  let attAdvice = "Kitchen Attention is suited to action shots (no tearing/ghosting)";
  if (fast && att.indexOf("sage") >= 0) attAdvice = "WARNING: SageAttention tends to produce edge ghosting and tearing on fight/fast-action shots -> switch to Kitchen Attention (the two cannot be enabled together)";
  else if (att.indexOf("sage") >= 0) attAdvice = "SageAttention is acceptable for non-action shots; Kitchen Attention is still recommended for action shots";
  else if (att.indexOf("kitchen") >= 0) attAdvice = "Kitchen Attention is the right pick (stable on action shots, no tearing)";

  // 3. 参考权重
  let rwAdvice;
  if (fast) rwAdvice = "0.78-0.82 (large pose/turn/punch; high weight distorts features)";
  else if (med) rwAdvice = "0.82-0.85 (moderate motion, pose/identity balance)";
  else rwAdvice = "0.85-0.88 (lock character / static dialogue)";
  rwAdvice += ` (current ${refW})`;
  if (fast && refW > 0.85) rwAdvice += "  -> lower it; high weight + large motion double-pulls and misaligns features";

  // 4. 负向词
  let neg = fast ? NEG_FAST : NEG_BASE;
  if (baseNeg && baseNeg.trim()) neg = baseNeg.trim() + ", " + neg;
  neg = "clip negative: " + neg;

  // 5. 检查清单
  let checklist;
  if (fast) {
    const seg = (Number(seconds) || 0) <= 5 ? " (already split)" : " -> split shorter";
    checklist = [
      `1) Split: generate <=5 s per run (currently ${seconds || "?"}s${seg}); halving the frame count is the most direct fix`,
      "2) Lower resolution to the 0.5MP tier (16:9->960x544 / portrait->768x1344): the 4-step distilled model inevitably glitches on 1MP fast action; one tier down is most effective",
      "3) Fix the seed and use the previous segment\'s last frame as the reference first frame for relay generation",
      "4) Split action shots finer; keep 2-3 overlapping frames at joins instead of hard cuts",
      "5) If glitches/flicker persist: rerun a comparison with ALL acceleration off (VSA/Sage/Turbo)",
      "6) High weight + large motion = double constraint pull -> lower the reference weight to 0.78-0.82",
    ];
  } else if (med) {
    checklist = [
      `1) Generate <=15 s per run (currently ${seconds || "?"}s); fix the seed and use segment relay`,
      "2) Turn/profile shots: reference weight 0.78-0.82",
      "3) If smearing: raise steps to 8 or turn Turbo off",
      "4) Keep the native 1344x768 resolution",
    ];
  } else {
    checklist = [
      "1) Static shots can run long (<=20s); weight 0.85-0.88 locks the character",
      "2) Use the concise generic negative prompt; don't pile on terms or the frame becomes stiff",
      "3) Watch for temporal drift: refresh the character reference image every 4-6 shots",
    ];
  }

  // 6. 后处理
  let post = [
    "- FlashVSR_Ultra_Fast video SR (per-frame denoise + temporal consistency) -> the best-fit glitch/noise fix in this pipeline (or the Topaz/FlashVSR tier of BSAI-H3-upscale-4K)",
    "- LTX2.5 second-pass upscale (~0.45 denoise) -> fixes facial blur/ghosting on action shots",
    "- SeedVR2 / Topaz SR -> lifts the 768P master to 1080P/4K",
    "- ComfyUI-Spectrum-MiniMax-H3: ER-SDE forecast contamination fix + offline smoothing removes temporal flicker",
    "- Tiled SR: watch seams and temporal flicker; play through twice at normal speed, then check eyes/mouth/hairline per frame",
  ];

  // 7. FastH3 蒸馏模型驱动配置（自动接入 BSAI-FastH3 极速链路）
  let vsa, keep, ladder = "999,749,500,250", len;
  if (fast) { vsa = "off (Dense attention, prevents edge ghosting/glitches)"; keep = "35%"; }
  else if (med) { vsa = "on"; keep = "20%"; }
  else { vsa = "on"; keep = "10%"; }
  len = Math.max(5, Math.round((Number(seconds) || 8) * 24));
  let drive = [
    "· vsa_enabled = " + vsa,
    "- video_keep_percent = " + keep + " (VSA kept-tile percent; higher = less detail loss)",
    "- ladder = " + ladder + " (FastH3 v0.2 trained 4-step ladder; do not change)",
    "- ref_length = " + len + " (" + (Number(seconds) || 8) + "s @ 24fps) -> connect to ReferenceToVideo/ImageToVideo.length",
  ];

  return [
    "═══ Recommended steps ═══\n" + steps,
    "\n═══ Attention plan ═══\n" + attAdvice,
    "\n═══ Reference weight ═══\n" + rwAdvice,
    "\n═══ Fast-action negative ═══\n" + neg,
    "\n═══ FastH3 drive config ═══\n" + drive.join("\n"),
    "\n═══ Checklist ═══\n" + checklist.join("\n"),
    "\n═══ Post-processing ═══\n" + post.join("\n"),
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
          "string", "Repair Plan (live)", "",
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
