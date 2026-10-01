#!/usr/bin/env python3
"""
review_labels.py - a small local screen for reviewing the M42 label queue (collared-neck, regular-sleeve).

It shows one garment photo at a time with a question and the possible answers. Press the number of the answer
(or click it); the answer is saved at once and the next photo appears. You can stop at any time and continue
later: the tool starts at the first photo that has no answer yet.

    backend\\venv\\Scripts\\python ai_training\\tools\\review_labels.py --reviewer "your name"
    then open  http://127.0.0.1:5090  in the browser

It runs on this computer only (127.0.0.1), reads the queue made by scripts/v2/build_review_queue_m42.py and
writes ai_training/data/label_queue_m42/decisions.jsonl. Nothing is sent anywhere.
"""
import argparse
import datetime
import io
import json
import os
import tempfile

from flask import Flask, abort, jsonify, request, send_file
from PIL import Image, ImageOps

app = Flask(__name__)
STATE = {"queue": [], "by_id": {}, "decisions": {}, "decisions_path": "", "reviewer": ""}

DEFINITIONS = {
    "neckline_type": [
        ("collared-neck", "A shirt collar: a separate folded band around the neck (shirts, polo collars). A blazer / jacket lapel is NOT this - answer 'other'.",
         "කමිස collar එකක්: බෙල්ල වටා නවා ඇති වෙනම පටියක්. Blazer / jacket lapel නම් 'other'."),
        ("round-neck", "A round opening, no collar.", "වටකුරු බෙල්ල, collar නැත."),
        ("v-neck", "The front comes to a V point, no collar.", "ඉදිරියෙන් V හැඩය, collar නැත."),
        ("square-neck", "A straight edge across the chest with corners.", "පපුව හරහා කෙළින් දාරයක්, කොන් සහිතව."),
        ("off-shoulder", "The neckline sits below both shoulders.", "උරහිස් දෙකටම පහළින්."),
        ("other", "Any other neckline (boat, halter, high neck, hood, jacket lapel ...) or not a top.", "වෙනත් බෙල්ලක් හෝ top එකක් නොවේ."),
        ("unclear", "The neckline cannot be seen well enough to decide.", "පැහැදිලිව නොපෙනේ."),
    ],
    "sleeve_style": [
        ("regular-sleeve", "A plain set-in sleeve: smooth at the shoulder, no gathers, not flared. Short or long.",
         "සාමාන්‍ය අත: උරහිසේ රැලි නැත, පුළුල් වී නැත. කෙටි හෝ දිග."),
        ("puff-sleeve", "Gathered at the shoulder and / or the hem so it puffs out.", "උරහිසේ හෝ කෙළවරේ රැලි සහිතව පිම්බුණු අත."),
        ("bell-sleeve", "Fitted at the top and flaring wide towards the hem.", "ඉහළින් සිහින්, පහළට පුළුල් වන අත."),
        ("none", "Sleeveless: no sleeve at all.", "අත් නැත (sleeveless)."),
        ("other", "Any other sleeve (raglan, dolman / batwing, kimono, flutter, cap ...) or not a top.", "වෙනත් අත් වර්ගයක් හෝ top එකක් නොවේ."),
        ("unclear", "The sleeve cannot be seen well enough to decide.", "පැහැදිලිව නොපෙනේ."),
    ],
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Label review</title><style>
body{font-family:system-ui,Segoe UI,sans-serif;margin:0;background:#f4f4f0;color:#1d2a24}
header{background:#1f3d31;color:#fff;padding:10px 18px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header b{font-size:17px} #bar{flex:1;min-width:160px;height:10px;background:#3d5a4d;border-radius:6px;overflow:hidden}
#bar i{display:block;height:100%;background:#9fd8b4}
main{display:grid;grid-template-columns:minmax(280px,1fr) minmax(300px,460px);gap:18px;padding:18px;max-width:1200px;margin:auto}
@media(max-width:800px){main{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid #dcdcd4;border-radius:12px;padding:14px}
#photo{width:100%;max-height:72vh;object-fit:contain;background:#eee;border-radius:8px}
h2{margin:0 0 4px;font-size:19px} .hint{color:#5d6b63;font-size:13px;margin:0 0 12px}
.opt{display:flex;gap:10px;align-items:flex-start;width:100%;text-align:left;font:inherit;padding:9px 11px;margin:0 0 7px;border:1px solid #cfd4cc;border-radius:9px;background:#fafaf7;cursor:pointer}
.opt:hover{border-color:#1f5c4a} .opt.sel{background:#e3f3ea;border-color:#1f6b3a}
.opt kbd{background:#1f3d31;color:#fff;border-radius:5px;padding:1px 7px;font-size:13px}
.opt small{display:block;color:#5d6b63;font-size:12px;margin-top:2px}
.row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap} .row button{font:inherit;padding:8px 12px;border-radius:8px;border:1px solid #cfd4cc;background:#fff;cursor:pointer}
#msg{font-size:13px;color:#8d2a2a;min-height:18px;margin-top:8px}
</style></head><body>
<header><b>Label review</b><span id="count"></span><div id="bar"><i id="fill"></i></div><span id="who"></span></header>
<main><div class="card"><img id="photo" alt="garment"><div class="row">
<button id="crop">Garment crop</button><button id="full">Whole photo</button></div></div>
<div class="card"><h2 id="q"></h2><p class="hint" id="hint"></p><div id="opts"></div>
<div class="row"><button id="prev">&larr; Back</button><button id="next">Next &rarr;</button><button id="todo">Go to first unanswered</button></div>
<div id="msg"></div><p class="hint">Keys: 1-7 answer &middot; &larr; &rarr; move. Answer what you SEE; the hint is only why this photo was picked.</p></div></main>
<script>
let S=null,i=0,mode='crop',item=null;
const $=id=>document.getElementById(id);
async function state(){S=await (await fetch('/api/state')).json();$('who').textContent='Reviewer: '+S.reviewer;progress();}
function progress(){const d=S.items.filter(x=>x.decision).length;$('count').textContent=d+' of '+S.total+' answered';$('fill').style.width=(100*d/S.total)+'%';}
function firstTodo(){const k=S.items.findIndex(x=>!x.decision);return k<0?S.total-1:k;}
async function show(k){i=Math.max(0,Math.min(S.total-1,k));mode='crop';item=await (await fetch('/api/item/'+i)).json();
 $('q').textContent=(i+1)+'. '+item.question;$('hint').textContent='Why this photo: '+item.hint+' ('+item.source+')';
 $('full').style.display=item.has_full?'':'none';img();
 $('opts').innerHTML='';item.options.forEach((o,n)=>{const b=document.createElement('button');b.className='opt'+(item.decision===o.value?' sel':'');
  b.innerHTML='<kbd>'+(n+1)+'</kbd><span><b>'+o.value+'</b><small>'+o.en+'</small><small>'+o.si+'</small></span>';b.onclick=()=>decide(o.value);$('opts').appendChild(b);});
 $('msg').textContent='';}
function img(){$('photo').src='/img/'+i+'/'+mode+'?t='+Date.now();}
async function decide(v){const r=await fetch('/api/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({queue_id:item.queue_id,decision:v})});
 if(!r.ok){$('msg').textContent='Not saved: '+((await r.json()).error||r.status);return;}
 S.items[i].decision=v;progress();if(i<S.total-1)show(i+1);else{show(i);$('msg').textContent='Last photo answered. Thank you!';}}
$('prev').onclick=()=>show(i-1);$('next').onclick=()=>show(i+1);$('todo').onclick=()=>show(firstTodo());
$('crop').onclick=()=>{mode='crop';img();};$('full').onclick=()=>{mode='full';img();};
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')show(i-1);else if(e.key==='ArrowRight')show(i+1);
 else if(item&&/^[1-9]$/.test(e.key)){const o=item.options[Number(e.key)-1];if(o)decide(o.value);}});
state().then(()=>show(firstTodo()));
</script></body></html>"""


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_decisions():
    """Atomic rewrite: the file is complete or untouched, never half written."""
    path = STATE["decisions_path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for q in STATE["queue"]:
            d = STATE["decisions"].get(q["queue_id"])
            if d:
                f.write(json.dumps(d) + "\n")
    os.replace(tmp, path)


def configure(queue_path, decisions_path, reviewer):
    STATE["queue"] = load_jsonl(queue_path)
    STATE["by_id"] = {q["queue_id"]: q for q in STATE["queue"]}
    STATE["decisions_path"] = decisions_path
    STATE["reviewer"] = reviewer
    STATE["decisions"] = {d["queue_id"]: d for d in load_jsonl(decisions_path) if d.get("queue_id") in STATE["by_id"]}


def _item(index):
    if not 0 <= index < len(STATE["queue"]):
        abort(404)
    return STATE["queue"][index]


@app.route("/")
def page():
    return PAGE


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/api/state")
def state():
    return jsonify({"total": len(STATE["queue"]), "reviewer": STATE["reviewer"],
                    "items": [{"queue_id": q["queue_id"], "decision": (STATE["decisions"].get(q["queue_id"]) or {}).get("decision")}
                              for q in STATE["queue"]]})


@app.route("/api/item/<int:index>")
def item(index):
    q = _item(index)
    text = {v: (en, si) for v, en, si in DEFINITIONS[q["head"]]}
    return jsonify({"queue_id": q["queue_id"], "question": q["question"], "hint": q["hint"], "source": q["source"],
                    "has_full": bool(q.get("bbox_xywh") or q.get("full_image_path")),
                    "decision": (STATE["decisions"].get(q["queue_id"]) or {}).get("decision"),
                    "options": [{"value": o, "en": text[o][0], "si": text[o][1]} for o in q["options"]]})


@app.route("/img/<int:index>/<mode>")
def image(index, mode):
    """Only images named by the queue are served (looked up by position, never by a path from the browser)."""
    q = _item(index)
    path = q["image_path"]
    if mode == "full" and q.get("full_image_path"):
        path = q["full_image_path"]
    if not os.path.exists(path):
        abort(404)
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if mode != "full" and q.get("bbox_xywh"):
            x, y, w, h = [float(v) for v in q["bbox_xywh"]]
            mx, my = 0.10 * w, 0.10 * h
            im = im.crop((max(0, int(x - mx)), max(0, int(y - my)), min(im.width, int(x + w + mx)), min(im.height, int(y + h + my))))
        im.thumbnail((1100, 1100))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg")


@app.route("/api/decide", methods=["POST"])
def decide():
    data = request.get_json(silent=True) or {}
    q = STATE["by_id"].get(data.get("queue_id"))
    if not q:
        return jsonify({"error": "unknown queue_id"}), 404
    if data.get("decision") not in q["options"]:
        return jsonify({"error": f"decision must be one of {q['options']}"}), 400
    STATE["decisions"][q["queue_id"]] = {
        "queue_id": q["queue_id"], "head": q["head"], "decision": data["decision"], "human_verified": True,
        "reviewer_id": STATE["reviewer"], "reviewed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_decisions()
    return jsonify({"saved": True, "answered": len(STATE["decisions"]), "total": len(STATE["queue"])})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue", default="ai_training/data/label_queue_m42/queue.jsonl")
    ap.add_argument("--decisions", default="ai_training/data/label_queue_m42/decisions.jsonl")
    ap.add_argument("--reviewer", required=True, help="your name (stored with every answer)")
    ap.add_argument("--port", type=int, default=5090)
    a = ap.parse_args()
    if not os.path.exists(a.queue):
        raise SystemExit(f"Queue not found: {a.queue}\nBuild it first:  backend\\venv\\Scripts\\python ai_training\\scripts\\v2\\build_review_queue_m42.py")
    configure(a.queue, a.decisions, a.reviewer.strip())
    done = len(STATE["decisions"])
    print(f"{len(STATE['queue'])} photos in the queue, {done} already answered.")
    print(f"Open  http://127.0.0.1:{a.port}  in your browser. Press Ctrl+C here to stop; answers are saved as you go.")
    app.run(host="127.0.0.1", port=a.port, debug=False)


if __name__ == "__main__":
    main()
