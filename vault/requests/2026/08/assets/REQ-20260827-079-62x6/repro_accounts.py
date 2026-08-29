"""REQ-20260827-079 재현: account_rows 의 중복 제거가 '고를 수 있는 줄'을 0으로 만든다.

격리: HOME 을 임시 디렉토리로 바꿔 실제 ~/.claude 를 건드리지 않는다.
"""
import json, os, shutil, sys, tempfile, importlib.util

ROOT = "/home/sjpark1/section9"
tmp = tempfile.mkdtemp(prefix="s9acct-")
os.environ["HOME"] = tmp
os.environ.pop("CLAUDE_CONFIG_DIR", None)

def mkcfg(path, email=None):
    os.makedirs(path, exist_ok=True)
    if email is not None:
        with open(os.path.join(path, ".claude.json"), "w") as f:
            json.dump({"oauthAccount": {"emailAddress": email}}, f)

# ~/.claude 는 .claude.json 이 바깥에 있다 (account_of 의 특례)
mkcfg(os.path.join(tmp, ".claude"))
with open(os.path.join(tmp, ".claude.json"), "w") as f:
    json.dump({"oauthAccount": {"emailAddress": "me@example.invalid"}}, f)
base = os.path.join(tmp, ".claude-profiles")
mkcfg(os.path.join(base, "me@example.invalid"), "me@example.invalid")  # 같은 계정 중복
mkcfg(os.path.join(base, "새-계정"))                                    # 로그인 전
mkcfg(os.path.join(base, "새-계정-2"))                                  # 로그인 전

spec = importlib.util.spec_from_loader(
    "s9mod", importlib.machinery.SourceFileLoader("s9mod", os.path.join(ROOT, "bin", "s9")))
s9 = importlib.util.module_from_spec(spec)
sys.argv = ["s9"]                      # main() 은 __main__ 가드 안이라 안 돈다
spec.loader.exec_module(s9)

rows = s9.account_rows()
print("== /api/accounts 와 같은 값 ==")
print(json.dumps(rows, ensure_ascii=False, indent=2))
pick = [r for r in rows if r["ready"] and not r["current"]]
print("고를 수 있는 줄(ready & not current):", len(pick))
assert len(pick) == 0, "재현 실패 — 고를 줄이 생겼다"

# 반대 방향: 세션이 프로필 쪽으로 떠 있을 때도 같은 막다른 창인가
rows2 = s9.account_rows(os.path.join(base, "me@example.invalid"))
pick2 = [r for r in rows2 if r["ready"] and not r["current"]]
print("\n== 세션이 프로필로 떠 있을 때 ==")
print(json.dumps(rows2, ensure_ascii=False, indent=2))
print("고를 수 있는 줄:", len(pick2))

shutil.rmtree(tmp, ignore_errors=True)
print("\n정리 완료:", tmp)
