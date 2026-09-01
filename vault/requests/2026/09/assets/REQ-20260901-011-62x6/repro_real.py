"""실측 트랜스크립트(a8186437)를 각 시점에서 잘라 _transcript_busy 를 물어본다."""
import json, os, tempfile
from importlib.machinery import SourceFileLoader
os.environ["S9_ROOT"] = tempfile.mkdtemp(prefix="s9busy-")
s9 = SourceFileLoader("s9", "/home/sjpark1/section9/bin/s9").load_module()
SRC = "/home/sjpark1/.claude/projects/-home-sjpark1-section9/a8186437-7f5e-4278-86cb-29951ca7e349.jsonl"
lines = [l for l in open(SRC, encoding="utf-8")]
rows  = [json.loads(l) for l in lines if l.strip().startswith("{")]
marks = [286, 292, 298, 304, 309, 313, 324]   # 한도응답 4회 · /model stdout · 인터럽트 · 마지막 end_turn
for i in marks:
    p = tempfile.mktemp(suffix=".jsonl")
    open(p, "w", encoding="utf-8").writelines(lines[:i+1])
    d = rows[i]; m = d.get("message") or {}
    c = m.get("content")
    if isinstance(c, list):
        c = " ".join(str(b.get("text", b.get("type"))) for b in c if isinstance(b, dict))
    print(f"[{i}] {d.get('timestamp','')[:19]} type={d.get('type'):9s} stop={str(m.get('stop_reason')):12s} "
          f"busy={s9._transcript_busy(p)}  :: {str(c)[:70]!r}")
