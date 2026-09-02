"""2차 재현: (1) beta 세션이 alpha 문서를 이어받은 뒤 alpha 워처가 중복 스폰하는가
(2) 긴급 우선순위의 반려가 beta 에서 전이 자리(rework_kick)에서 막히는가
(3) 남의 바인딩이 내 문서를 잡고 pid 가 겹치면 내 워처가 침묵하는가 / 내 전이가 남의 바인딩 파일을 고쳐 쓰는가
(4) 시간이 지난 alpha 문서가 beta 의 `s9 stalled` 에 오르는가(사용자 무관)"""
import os, sys, json, tempfile, subprocess, importlib.util, importlib.machinery, time, shutil, datetime
S9 = "/home/sjpark1/section9/bin/s9"
tmp = tempfile.mkdtemp(prefix="s9x014b-")
os.environ["S9_ROOT"] = tmp
for k in ("S9_SESSION", "S9_AUTO_RESUME", "S9_AUTO_RESUME_DISABLE", "S9_USER"):
    os.environ.pop(k, None)
os.environ["S9_SYNC"] = "off"
def cli(machine, *argv, sess=None, check=True):
    env = {**os.environ, "S9_MACHINE": machine}
    if sess: env["S9_SESSION"] = sess
    r = subprocess.run([S9, *argv], capture_output=True, text=True, env=env, timeout=30)
    if check and r.returncode != 0:
        raise SystemExit(f"FAIL s9 {' '.join(argv)} ({machine}): {r.stdout}{r.stderr}")
    return (r.stdout + r.stderr).strip()
cli("alpha", "init"); cli("alpha", "user", "add", "alice")
for kv in (("auto_resume","on"),("auto_resume_cooldown_sec","0"),("auto_resume_global_per_hour","50"),("auto_resume_global_per_day","100")):
    cli("alpha", "user", "config", "alice", *kv)
A, B = "aaaa1111", "bbbb2222"
cli("alpha", "user", "switch", "alice", sess=A)
def mkdoc(title, prio=None):
    args = ["new", "request", "--title", title, "--summary", "s", "--size", "S", "--goal", "g", "--body", "o"]
    if prio: args += ["--priority", prio]
    d = cli("alpha", *args, sess=A).split()[0]
    cli("alpha", "status", d, "in-progress", "--note", "착수", sess=A)
    cli("alpha", "status", d, "review", "--note", "확인", sess=A)
    return d
X = mkdoc("알파의 일"); R = mkdoc("알파의 급한 일", "urgent")
spec = importlib.util.spec_from_loader("s9mod", importlib.machinery.SourceFileLoader("s9mod", S9))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
spawned = []
class FakePopen:
    def __init__(self, *a, **k): self.pid = 4242; spawned.append(a[0][:2] if a else k)
    def poll(self): return None
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def communicate(self, *a, **k): return ("", "")
    def wait(self, *a, **k): return 0
    returncode = 0
import subprocess as _sp; RealPopen = _sp.Popen

# (2) 긴급 반려를 beta 대시보드에서 — 전이 자리 즉시 스폰(rework_kick) 이 elsewhere 로 막히는가
os.environ["S9_MACHINE"] = "beta"; _sp.Popen = FakePopen
old = mod.do_transition(R, "in-progress", note="반려: 급함", judge=True, via="dashboard")
print("[2] rush rework on beta: rework_grace=", mod.rework_grace(mod.read_doc(mod.locate(R))[0]),
      "maybe_auto_resume ->", mod.maybe_auto_resume(R, old, "in-progress", "반려"), "| Popen:", len(spawned))
_sp.Popen = RealPopen
print("[2] spawn.log tail:", open(os.path.join(tmp,"state","auto_resume","spawn.log")).read().strip().splitlines()[-2:])

# (1) beta 대시보드에서 X 반려 → beta 세션 B 가 이어받아(claim) 일하는 중. alpha 워처는?
old = mod.do_transition(X, "in-progress", note="반려: 다시", judge=True, via="dashboard")
cli("beta", "user", "switch", "alice", sess=B)
print("[1] beta claim:", cli("beta", "claim", X, sess=B))
bb = mod.read_binding("beta", B); print("[1] beta binding active_reqs:", bb.get("active_reqs"), "attach_pid:", bb.get("attach_pid"))
mx = mod.read_doc(mod.locate(X))[0]; print("[1] X machine/session after beta claim:", mx.get("machine"), mx.get("session"))
os.environ["S9_MACHINE"] = "alpha"       # ← alpha 머신의 serve 워처 시점 (beta 바인딩은 pull 로 와 있음)
print("[1] alpha: rework_claimed(X) ->", mod.rework_claimed(X), "(beta 세션의 transcript/pid 는 alpha 에 없다)")
_sp.Popen = FakePopen; n0 = len(spawned)
print("[1] alpha: rework_watch_tick(grace=0) ->", mod.rework_watch_tick(grace=0), "| new Popen:", len(spawned)-n0)
_sp.Popen = RealPopen
shutil.rmtree(os.path.join(tmp, "state", "auto_resume"), ignore_errors=True)

# (3) beta 시점: alpha 바인딩이 X 를 잡고 있고 attach_pid 가 beta 의 산 pid 와 겹친다
os.environ["S9_MACHINE"] = "beta"
ap = mod.binding_path("alpha", A); b = json.load(open(ap))
b["active_reqs"] = [X]; b["claim_at"] = {X: mod.now_iso()}; b["attach_pid"] = os.getpid(); json.dump(b, open(ap, "w"))
print("[3] beta: rework_claimed(X) with alpha binding(pid collides) ->", mod.rework_claimed(X))
b["attach_pid"] = 999999; json.dump(b, open(ap, "w"))
print("[3] beta: rework_claimed(X) with alpha binding(pid dead) ->", mod.rework_claimed(X))
# beta 세션이 X 를 review 로 보내면 alpha 바인딩에서 X 를 걷어 파일을 고쳐 쓰는가
mt0 = os.path.getmtime(ap); time.sleep(0.05)
os.environ["S9_SESSION"] = B
mod.do_transition(X, "review", note="다시 올림", force=True); mod.update_active_reqs(X, "review")
os.environ.pop("S9_SESSION")
print("[3] alpha binding file rewritten on beta:", os.path.getmtime(ap) != mt0, "active_reqs:", json.load(open(ap)).get("active_reqs"))
# claim --release 도 남의 바인딩을 만지는가
b = json.load(open(ap)); b["active_reqs"] = [X]; b["claim_at"] = {X: mod.now_iso()}; json.dump(b, open(ap, "w"))
mod.do_transition(X, "in-progress", note="반려: 또", judge=True, via="dashboard")
mt0 = os.path.getmtime(ap); time.sleep(0.05)
print("[3] s9 claim --release by A-session on beta:", cli("beta", "claim", X, "--release", "--session", A, check=False))
print("[3] alpha binding rewritten by release:", os.path.getmtime(ap) != mt0, json.load(open(ap)).get("active_reqs"))

# (4) 시간이 지난 alpha 문서 — beta 의 `s9 stalled`(훅이 매 턴 주입) 에 오르는가
p = mod.locate(X); m, body = mod.read_doc(p)
m["updated"] = (datetime.datetime.now().astimezone() - datetime.timedelta(minutes=40)).isoformat(timespec="seconds")
mod.write_doc(p, m, body); mod.rebuild_index(quiet=True)
cli("beta", "user", "add", "bob"); cli("beta", "user", "switch", "bob", sess=B)
print("[4] s9 stalled (bob@beta):", cli("beta", "stalled", sess=B))
print("[4] s9 loose (bob@beta):", cli("beta", "loose", sess=B))
print("TMP", tmp)
