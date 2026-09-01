import json, os, tempfile
from importlib.machinery import SourceFileLoader
os.environ["S9_ROOT"] = tempfile.mkdtemp(prefix="s9busy-")
s9 = SourceFileLoader("s9", "/home/sjpark1/section9/bin/s9").load_module()

def w(rows):
    p = tempfile.mktemp(suffix=".jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p

LIMIT = {"type":"assistant","message":{"model":"<synthetic>","stop_reason":"stop_sequence",
        "content":[{"type":"text","text":"You've reached your Fable 5 limit. Run /usage-credits to continue or switch models with /model."}]}}
END   = {"type":"assistant","message":{"model":"claude-opus-5","stop_reason":"end_turn",
        "content":[{"type":"text","text":"done"}]}}
USER  = {"type":"user","message":{"content":[{"type":"text","text":"hi"}]}}

cases = [
 ("정상 유휴 (end_turn)",                [USER, END],                 False),
 ("한도 소진 합성 응답 (실측 원문 그대로)", [USER, LIMIT],              False),
 ("한도 + 중단요청 4회 반복 (12:37~12:39 실측)", [USER,LIMIT,USER,LIMIT,USER,LIMIT,USER,LIMIT], False),
 ("진짜 진행 중 (tool_use)",             [USER, {"type":"assistant","message":{"stop_reason":"tool_use","content":[]}}], True),
 ("사용자 턴이 마지막",                   [END, USER],                 True),
]
print("case | busy 실측 | busy 기대 | 판정")
for name, rows, want in cases:
    got = s9._transcript_busy(w(rows))
    print(f"{name} | {got} | {want} | {'OK' if got==want else '✗ MISMATCH'}")
