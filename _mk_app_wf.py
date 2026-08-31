# -*- coding: utf-8 -*-
import json, os

SRC = r"C:\BSAI\ComfyUI-BSAI_pro_v38_Film Factory\ComfyUI\user\default\workflows\BSAI H3 Prompt Template (提示词模板)支持语音交互+ACC-8步lora+BSAI-H3-upscale-4K超分放大高清修复+文生+图生+首尾帧+多参生视频参考工作流 v2.0.json"

wf = json.load(open(SRC, encoding="utf-8"))
nodes = wf["nodes"]
links = wf.get("links", [])
max_id = max(n["id"] for n in nodes)
max_link = max((l[0] for l in links), default=0)
max_order = max(n.get("order", 0) for n in nodes)

# 定位
cliploader = next(n for n in nodes if n["type"] == "CLIPLoader")
anchor = next(n for n in nodes if n["type"] == "BSAI_H3_PromptTemplate")
bx, by = anchor["pos"][0], anchor["pos"][1] + anchor["size"][1] + 260

# 1) MotionFix 节点
motionfix = {
    "id": max_id + 1,
    "type": "BSAI_H3_MotionFix",
    "pos": [bx, by],
    "size": [430, 240],
    "flags": {},
    "order": max_order + 1,
    "mode": 0,
    "inputs": [],
    "outputs": [
        {"localized_name": "recommended_steps (推荐步数)", "name": "recommended_steps", "type": "STRING", "links": None},
        {"localized_name": "attention_advice (注意力建议)", "name": "attention_advice", "type": "STRING", "links": None},
        {"localized_name": "ref_weight_advice (参考权重建议)", "name": "ref_weight_advice", "type": "STRING", "links": None},
        {"localized_name": "negative_prompt (大动态负向词)", "name": "negative_prompt", "type": "STRING", "links": None},
        {"localized_name": "checklist (检查清单)", "name": "checklist", "type": "STRING", "links": None},
        {"localized_name": "post_process (后处理方案)", "name": "post_process", "type": "STRING", "links": None},
    ],
    "properties": {"Node name for S&R": "BSAI_H3_MotionFix"},
    "widgets_values": [
        "fast_action 高速动作/打斗 (出拳/奔跑/转身)",
        False,
        0.85,
        8.0,
        "kitchen_attention",
        "",
    ],
    "color": "#662233",
    "bgcolor": "#442222",
}

# 2) 负向 CLIPTextEncode（text <- MotionFix.negative_prompt）
nce = {
    "id": max_id + 2,
    "type": "CLIPTextEncode",
    "pos": [bx + 480, by + 60],
    "size": [320, 180],
    "flags": {},
    "order": max_order + 2,
    "mode": 0,
    "inputs": [
        {"localized_name": "clip", "name": "clip", "type": "CLIP", "link": None},
        {"localized_name": "text", "name": "text", "type": "STRING", "link": None},
    ],
    "outputs": [
        {"localized_name": "CONDITIONING", "name": "CONDITIONING", "type": "CONDITIONING", "links": None},
    ],
    "properties": {"Node name for S&R": "CLIPTextEncode"},
    "widgets_values": [],
}

# 3) Note 映射说明
note_text = (
    "BSAI H3 MotionFix 应用映射说明\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "1. 本节点为「高速动作毛刺/噪点修复向导」，纯规则引擎，零显存。\n"
    "   节点面板内实时显示完整修复方案卡（步数/注意力/权重/负向词/清单/后处理）。\n"
    "2. negative_prompt 已自动接入右侧 CLIPTextEncode，生成大动态负向 CONDITIONING\n"
    "   （若 H3 采样需负向 CFG，可把该 CONDITIONING 经 ConditioningConcat 并入；\n"
    "    或直接复制节点方案卡中的负向词文本）。\n"
    "3. recommended_steps（推荐步数）：\n"
    "   · 关闭 Turbo 回原生 20–24 步 → 参考 MiniMaxH3PDDAccApply.nfe\n"
    "   · 若用 ACC-8步 LoRA，至少提高到 8 步（勿用 4 步，必出拖影/残影）\n"
    "4. ref_weight_advice（参考权重）：填到 ReferenceToVideo 参考强度（大姿态 0.78–0.82）\n"
    "5. clip_seconds（片段时长）：填到 length / 单次生成 ≤8–15 秒拆段\n"
    "6. checklist / post_process：逐项执行；后处理可用 LTX2.5 二次采样 + SeedVR2/FlashVSR/Topaz 超分"
)
note = {
    "id": max_id + 3,
    "type": "Note",
    "pos": [bx + 480, by + 360],
    "size": [480, 320],
    "flags": {},
    "order": max_order + 3,
    "mode": 0,
    "inputs": [],
    "outputs": [],
    "properties": {"Node name for S&R": "Note"},
    "widgets_values": [note_text],
}

nodes.append(motionfix)
nodes.append(nce)
nodes.append(note)

# 新 links
nid = max_id + 1
nlink = max_link + 1
link_neg = [nlink, nid, 3, max_id + 2, 1, "STRING"]  # MotionFix.negative_prompt -> CLIPTextEncode.text
nlink += 1
link_clip = [nlink, cliploader["id"], 0, max_id + 2, 0, "CLIP"]  # CLIPLoader.CLIP -> CLIPTextEncode.clip
links.append(link_neg)
links.append(link_clip)

wf["nodes"] = nodes
wf["links"] = links
if wf.get("last_node_id", 0) <= max_id + 3:
    wf["last_node_id"] = max_id + 3

# 保存两份：插件仓库 + 前端工作流目录
out1 = r"C:\BSAI\ComfyUI-BSAI_pro_v38_Film Factory\ComfyUI\custom_nodes\BSAI-H3-MotionFix\workflows\BSAI H3 高速运动毛刺噪点修复应用工作流.json"
os.makedirs(os.path.dirname(out1), exist_ok=True)
json.dump(wf, open(out1, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

out2 = r"C:\BSAI\ComfyUI-BSAI_pro_v38_Film Factory\ComfyUI\user\default\workflows\BSAI H3 高速运动毛刺噪点修复应用工作流.json"
json.dump(wf, open(out2, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# verify
v = json.load(open(out1, encoding="utf-8"))
types = [n["type"] for n in v["nodes"]]
print("nodes:", len(v["nodes"]), "links:", len(v["links"]))
print("has MotionFix:", "BSAI_H3_MotionFix" in types)
print("has CLIPTextEncode:", types.count("CLIPTextEncode"))
print("has Note:", types.count("Note"))
print("link_neg in:", link_neg in [list(l) for l in v["links"]])
print("link_clip in:", link_clip in [list(l) for l in v["links"]])
print("written:", out1)
print("written:", out2)
