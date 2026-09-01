"""세션 1회 모델 선택이 사용자 영속 정책이 되는가 — 임시 S9_ROOT 실증."""
import os, tempfile, subprocess, json
ROOT = tempfile.mkdtemp(prefix="s9persist-")
S9 = "/home/sjpark1/section9/bin/s9"
env = {**os.environ, "S9_ROOT": ROOT}
env.pop("S9_SESSION", None)
def run(*a):
    return subprocess.run([S9, *a], env=env, capture_output=True, text=True, timeout=60)
print(run("init").stdout.strip()[:120])
run("user", "add", "tester")
run("user", "config", "tester", "s9code_args", "--permission-mode auto --model opus")
run("user", "config", "tester", "auto_resume_model", "opus")

from importlib.machinery import SourceFileLoader
os.environ["S9_ROOT"] = ROOT
s9 = SourceFileLoader("s9", S9).load_module()
print("이전:", {k: v for k, v in (s9.user_config("tester") or {}).items()
                if k in ("s9code_args", "auto_resume_model")})
saved = s9._persist_model_choice("tester", "fable")   # 대시보드에서 fable 한 번 고름
print("_persist_model_choice 반환:", saved)
print("이후:", {k: v for k, v in (s9.user_config("tester") or {}).items()
                if k in ("s9code_args", "auto_resume_model")})
prof = os.path.join(ROOT, "users", "tester", "profile.md")
print("프로필 기록:", [l for l in open(prof, encoding="utf-8")
                    if "dashboard model change" in l])
print("무인 워커 모델 인자:", s9._spawn_model_args("tester"))
import shutil; shutil.rmtree(ROOT)
print("cleanup ok")
