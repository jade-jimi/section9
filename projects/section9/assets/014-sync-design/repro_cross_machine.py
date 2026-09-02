"""REQ-20260902-014 조사 재현 — 다른 머신(alpha)에서 만든 문서가 내 머신(beta)에 pull 돼 왔을 때
각 경로가 그 문서를 집는가. 격리 S9_ROOT. 실제 claude 스폰은 Popen 을 가짜로 바꿔 막는다."""
import os, sys, json, tempfile, subprocess, importlib.util, importlib.machinery, time, shutil

S9 = "/home/sjpark1/section9/bin/s9"
tmp = tempfile.mkdtemp(prefix="s9x014-")
os.environ["S9_ROOT"] = tmp
for k in ("S9_SESSION", "S9_AUTO_RESUME", "S9_AUTO_RESUME_DISABLE", "S9_USER"):
    os.environ.pop(k, None)
os.environ["S9_SYNC"] = "off"

def cli(machine, *argv, sess=None, user=None, check=True):
    env = {**os.environ, "S9_MACHINE": machine}
    if sess: env["S9_SESSION"] = sess
    if user: env["S9_USER"] = user
    r = subprocess.run([S9, *argv], capture_output=True, text=True, env=env, timeout=30)
    if check and r.returncode != 0:
        raise SystemExit(f"FAIL s9 {' '.join(argv)} ({machine}): {r.stdout}{r.stderr}")
    return (r.stdout + r.stderr).strip()

# ---- alpha 머신에서 alice 가 문서를 만든다 -------------------------------
cli("alpha", "init")
cli("alpha", "user", "add", "alice")
cli("alpha", "user", "config", "alice", "auto_resume", "on")
cli("alpha", "user", "config", "alice", "auto_resume_cooldown_sec", "0")
cli("alpha", "user", "config", "alice", "auto_resume_global_per_hour", "50")
cli("alpha", "user", "config", "alice", "auto_resume_global_per_day", "100")
A = "aaaa1111"   # alpha 의 리드 세션
cli("alpha", "user", "switch", "alice", sess=A)
out = cli("alpha", "new", "request", "--title", "알파의 일", "--summary", "s", "--size", "S",
          "--goal", "g", "--body", "orig", sess=A)
X = out.split()[0]
cli("alpha", "status", X, "in-progress", "--note", "착수", sess=A)
cli("alpha", "status", X, "review", "--note", "확인해 주세요", sess=A)
# blocked 의존 문서 Y (alpha) — X 완료를 기다림
out = cli("alpha", "new", "request", "--title", "알파의 후속", "--summary", "s", "--size", "S",
          "--goal", "g", "--body", "orig", sess=A)
Y = out.split()[0]
cli("alpha", "status", Y, "in-progress", "--note", "착수", sess=A)
cli("alpha", "status", Y, "blocked", "--note", f"{X} 완료 대기", sess=A)
# alpha 의 리드 바인딩은 X 를 잡고 있었다(active_reqs) — pull 로 함께 온다
# 여기까지가 "pull 돼 온 상태" 라고 본다: 문서 X(review), Y(blocked), 바인딩 alpha__aaaa1111

# ---- beta 머신: 모듈 로드(워처·판정 함수 직접 호출) -------------------------
os.environ["S9_MACHINE"] = "beta"
spec = importlib.util.spec_from_loader("s9mod", importlib.machinery.SourceFileLoader("s9mod", S9))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
spawned = []
class FakePopen:
    def __init__(self, *a, **k): self.pid = 4242; spawned.append(a[0][:3] if a else k)
    def poll(self): return None
import subprocess as _sp; RealPopen=_sp.Popen; _sp.Popen = FakePopen

meta_X = mod.read_doc(mod.locate(X))[0]
print("X frontmatter machine/user/session:", meta_X.get("machine"), meta_X.get("user"), meta_X.get("session"))
print("current_machine():", mod.current_machine())

# (d) beta 의 대시보드에서 반려 — do_transition + maybe_auto_resume (보통 우선순위 → PENDING)
old = mod.do_transition(X, "in-progress", note="반려: 다시", judge=True, via="dashboard")
print("[d] maybe_auto_resume(normal prio) ->", mod.maybe_auto_resume(X, old, "in-progress", "반려"))

# (a) 워처 1틱: 유예 0 으로 강제 → rework_claimed 거짓이면 _spawn_rework → _spawn_worker
out = {}
ok = mod._spawn_worker(X, mod.read_doc(mod.locate(X))[0], "p", "rework", out=out)
print("[a] _spawn_worker on beta ->", ok, out)
print("[a] rework_watch_tick(grace=0) ->", mod.rework_watch_tick(grace=0), "| Popen calls:", len(spawned))
# 대조군: 같은 문서, S9_MACHINE=alpha 면 뜬다
os.environ["S9_MACHINE"] = "alpha"
out2 = {}
ok2 = mod._spawn_worker(X, mod.read_doc(mod.locate(X))[0], "p", "rework", out=out2)
print("[a-ctl] _spawn_worker on alpha ->", ok2, out2, "| Popen calls:", len(spawned))
_sp.Popen = RealPopen
os.environ["S9_MACHINE"] = "beta"
# 스폰 마커가 남으면 이후 판정(worker_running)이 오염되니 지운다
shutil.rmtree(os.path.join(tmp, "state", "auto_resume"), ignore_errors=True)

# (b) 리드 세션 경로 — beta 에서 alice 로 s9 next / reopened / stalled / blocked / review
B = "bbbb2222"
cli("beta", "user", "add", "bob")
cli("beta", "user", "switch", "alice", sess=B)
print("[b] s9 next (alice@beta):", cli("beta", "next", sess=B))
print("[b] s9 next --json:", cli("beta", "next", "--json", sess=B))
cli("beta", "user", "switch", "bob", sess=B)
print("[b] s9 next (bob@beta):", cli("beta", "next", sess=B))
print("[b] s9 next --all (bob@beta):", cli("beta", "next", "--all", sess=B))
print("[b] s9 reopened:", cli("beta", "reopened", sess=B))
print("[b] s9 stalled:", cli("beta", "stalled", sess=B))
print("[b] s9 blocked:", cli("beta", "blocked", sess=B))
print("[b] s9 review:", cli("beta", "review", sess=B))
dg = cli("beta", "digest", sess=B)
print("[b] digest 'active — bob (이어받을 작업)' 절:", [l for l in dg.splitlines() if "이어받을" in l or "others" in l])
print("[b] digest has X:", X in dg)

# (b2) beta 의 세션이 X 를 클레임하면 문서 session 이 beta 세션으로 갈아타는가, machine 은?
print("[b2] s9 claim X @beta:", cli("beta", "claim", X, sess=B))
m2 = mod.read_doc(mod.locate(X))[0]
print("[b2] X after claim: machine=", m2.get("machine"), "session=", m2.get("session"), "sessions=", m2.get("sessions"))

# (f) 바인딩 섞임: alpha 바인딩이 X 를 잡고 attach_pid 가 (우연히) beta 에 살아 있는 pid 면?
bpath = mod.binding_path("alpha", A)
b = json.load(open(bpath)); print("[f] alpha binding active_reqs:", b.get("active_reqs"))
b["attach_pid"] = os.getpid(); json.dump(b, open(bpath, "w"))
print("[f] rework_claimed(X) with alpha binding pid-collision ->", mod.rework_claimed(X))
print("[f] chat_live(alpha binding) ->", mod.chat_live(b))
t = mod.chat_target(None)
print("[f] chat_target() ->", (t or {}).get("machine"), (t or {}).get("session"))
b["attach_pid"] = 999999; json.dump(b, open(bpath, "w"))
print("[f] rework_claimed(X) with dead pid ->", mod.rework_claimed(X))
# (f2) beta 에서 X 를 review 로 보내면 alpha 바인딩 파일까지 고쳐 쓰는가 (update_active_reqs)
mt0 = os.path.getmtime(bpath); time.sleep(0.05)
os.environ["S9_SESSION"] = B
mod.do_transition(X, "review", note="다시 올림", force=True)
mod.update_active_reqs(X, "review")
b2 = json.load(open(bpath))
print("[f2] alpha binding rewritten by beta? mtime changed:", os.path.getmtime(bpath) != mt0, "active_reqs now:", b2.get("active_reqs"))
os.environ.pop("S9_SESSION")

# (e) trigger_dependents: beta 에서 X done → alpha 의 Y 가 beta 에서 in-progress 로 재개되는가
mod.do_transition(X, "done", note="승인: 끝", judge=True, via="dashboard")
freed = mod.trigger_dependents(X)
print("[e] trigger_dependents(X) freed:", freed, "| Y status:", mod.doc_status_live(Y), "| Y machine:", mod.read_doc(mod.locate(Y))[0].get("machine"))
# 재개된 Y 는 rework 후보인가(마지막 전이 blocked→in-progress 는 후보 아님)
lt = mod._last_transition(mod.read_doc(mod.locate(Y))[1])
print("[e] Y last transition:", lt[1:3], "rework_candidate:", mod.rework_candidate(lt))

# (c) 채팅 수신함 이벤트: chat_notify_transition — 대상은 X 의 session(alpha 세션) 바인딩
b = json.load(open(bpath)); b["attach_pid"] = os.getpid(); json.dump(b, open(bpath, "w"))
sent = mod.chat_notify_transition(Y, "review", "in-progress", "반려", "bob")
print("[c] chat_notify_transition(Y) -> sent to session:", sent)
inbox = os.path.join(tmp, "state", "terminal")
print("[c] inbox files on beta:", os.listdir(inbox) if os.path.isdir(inbox) else None)

print("spawn.log:")
try: print(open(os.path.join(tmp, "state", "auto_resume", "spawn.log")).read())
except OSError as e: print(" (none)", e)
print("TMP", tmp)
