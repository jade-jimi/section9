/* restart.js — 세션 재시작의 알림과 보내기(sendChat) */
"use strict";
function goTab(name){
  const b = document.querySelector(`header [data-tab="${name}"]`);
  if (b) b.click(); else location.hash = "#" + name;
}
/* 다시 시작을 **어느 탭에서 눌렀든 마감한다** (REQ-20260827-079 재작업).

   사용자가 겪은 화면: Board 에서 계정을 바꾸면 헤더 칩이 "세션 다시 시작 중"
   으로 95초 돌다가 **아무 말 없이 사라진다.** 됐는지 안 됐는지 알 길이 없다.

   원인은 자리다 — 완료를 지켜보는 눈이 터미널 판을 그리는 함수(restartLog)
   안에 있었고, 그 함수는 판이 없으면 첫 줄에서 되돌아간다. 눈이 안 서니
   마감하는 손(termRestartDone)도 불릴 일이 없었다.

   그래서 눈을 밖으로 낸다. 판이 있으면 터미널 폴이 맡고(그쪽이 빠르고 줄까지
   고친다), **없을 때만** 여기서 같은 답을 직접 받아 본다 — 같은 신호,
   같은 문턱(8초 뒤 수신 대기가 살아 있으면 완료 · 90초면 못 돌아옴)이라
   두 길이 다른 말을 하지 않는다. 새 컴포넌트는 만들지 않는다: 결과가 서는
   자리는 이미 있는 그 칩이다. */
let svWatch = null;            // {t0, sid, timer} · 터미널 판이 없을 때만
function svWatchStop(){
  if (!svWatch) return;
  clearInterval(svWatch.timer);
  svWatch = null;
}
function restartWatch(T, sid, d){
  if (!(d && d.ok && d.mode === "wrapper")) return;   // 감시할 것이 없다
  if (T && TERM === T && T.restart) return;           // 터미널 폴이 맡았다
  svWatchStop();
  const w = svWatch = {t0: Date.now(), sid: sid, timer: 0};
  w.timer = setInterval(async () => {
    if (svWatch !== w) return;
    const secs = (Date.now() - w.t0) / 1000;
    if (secs > 90){ svWatchStop(); restartChip("lost"); return; }
    // 터미널 판이 그 사이 열려 감시를 넘겨받았으면 물러난다 — 두 눈이 같은
    // 것을 보며 각자 칩을 고치면 순서에 따라 답이 달라진다.
    if (TERM && TERM.restart){ svWatchStop(); return; }
    const nt = await ccFetch("/api/chat/target", 4000);
    if (svWatch !== w) return;
    if (!nt || !nt.sid) return;                       // 아직 안 돌아왔다
    if (w.sid && nt.sid !== w.sid) return;            // 다른 세션 이야기다
    if (nt.listening && (Date.now() - w.t0) / 1000 > 8){
      svWatchStop(); restartChip("done");
    }
  }, 2000);
}
/* 거부·수락을 사람에게 말하고, 필요하면 **멈출지 묻는다.** */
async function restartTell(T, sid, req, d, what, cap){
  restartLog(T, d, what, req.model);
  if (d.ok){
    restartChip(d.mode === "wrapper" ? "going" : "hand", what, d);
    restartWatch(T, sid, d);   // 터미널 판이 없으면 여기서 마감한다
    if (d.mode !== "wrapper")
      // 손으로 한 번 해 줘야 하는 세션 — 그 명령을 창으로 준다(터미널 판이
      // 없으면 아무 데서도 못 보던 것이다)
      await s9dlg({kind: "alert", cap, stop: false,
        title: "이 세션은 처음 한 번만 손으로 다시 시작해야 합니다",
        descHtml: "세션 터미널에서 Ctrl+C 를 두 번 눌러 끝낸 뒤 아래를 실행하면,"
          + " 이후로는 대시보드에서 바로 됩니다."
          + `<code class="dlgcmd">${esc(d.cmd || "")}</code>`,
        ok: "닫기"});
    return;
  }
  if (!restartBusy(d)){
    svWatchStop();
    restartChip("fail", what, d);
    await s9dlg({kind: "alert", cap, title: restartSay(d.reason, what), ok: "닫기"});
    return;
  }
  /* 일하는 중이다 — **여기서 묻는다.** 확인 단계에서 미리 겁주지 않는 이유는
     화면이 그때는 모르기 때문이다: 세션이 일하는 중인지는 서버만 안다
     (`_transcript_busy`). 모르는 것을 아는 척 미리 말하면 대부분의 경우 쓸데없는
     경고가 되고, 정작 진짜인 순간에는 이미 배경이 되어 안 읽힌다. 되돌릴 수
     없는 일은 **그 순간에** 확인받는 것이 맞다. */
  restartChip("fail", what, d);
  // 맨 Enter 는 「그대로 두기」에 닿는다 (REQ-20260830-008) — 도는 일을 끊는
  // 창은 전부 물러나는 쪽에서 시작한다.
  const go = await s9dlg({kind: "confirm", cap, stop: false, safe: true,
    title: "지금 이 세션이 일하는 중입니다",
    desc: "하던 일을 중단하고 바꿀까요? 대화는 그대로 이어지므로, 다시 시작한 뒤"
      + " 하던 말을 이어서 하면 됩니다. 중단하지 않으면 지금 설정 그대로 둡니다.",
    ok: "중단하고 바꾸기", cancel: "그대로 두기"});
  if (!go) return;
  await restartAfterStop(T, sid, req, what, cap);
}
/* 멈추고 다시 청한다. 중단 신호는 이미 있는 그 길이다 — 수신함 `kind=interrupt`
   (Esc 가 쓰는 그것). 멈춘 뒤 유휴가 되기까지는 시간이 걸리므로 **그 사이도
   말한다**: 칩이 "하던 일을 멈추는 중"으로 서 있는다. */
async function restartAfterStop(T, sid, req, what, cap){
  restartChip("stopping", what, null);
  try{
    const r = await fetch("/api/chat", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({kind: "interrupt", sid})});
    const di = await r.json();
    if (!di.ok) throw new Error(di.error || "중단 요청 실패");
  }catch(ex){
    restartChip("fail", what, {reason: "중단 요청 실패"});
    await s9dlg({kind: "alert", cap, title: "하던 일을 중단하지 못했습니다",
      desc: "설정은 그대로 두었습니다 — 세션 터미널을 확인한 뒤 다시 눌러 주세요.",
      ok: "닫기"});
    return;
  }
  for (let i = 0; i < RESTART_STOP_TRIES; i++){
    await new Promise(res => setTimeout(res, 600));
    const d = await restartPost(sid, req);
    if (restartBusy(d)) continue;          // 아직 안 멈췄다 — 더 기다린다
    await restartTell(T, sid, req, d, what, cap);
    return;
  }
  // 15초를 기다려도 안 멈췄다 — 지어내지 않고 있는 그대로 말한다
  // `멈춤` 은 이제 **상태**의 낱말이다 (REQ-20260829-024 라운드4) — 저절로
  // 조용해진 것을 가리킨다. 사람이 끝내는 행동은 `중단` 이라, 여기 사유는
  // 상태 낱말을 피해 무엇이 안 됐는지만 말한다.
  restartChip("fail", what, {reason: "안 끝남"});
  await s9dlg({kind: "alert", cap, title: "하던 일이 아직 안 끝났습니다",
    desc: "멈춰 달라고는 했지만 15초 안에 끝나지 않았습니다 — 설정은 그대로"
      + " 둡니다. 잠시 뒤 다시 눌러 주세요.", ok: "닫기"});
}
/* 부르는 자리는 둘(계정 창·모델 창)이고 들어오는 것은 세션 id 하나다.
   터미널 판(T)은 있으면 기록을 남기고 없으면 없는 대로 간다 — 예전에는 그것이
   없으면 아무 일도 일어나지 않았다. */
/* 지금 도는 무인 작업자들 — 서버가 카탈로그 행에 실어 준 `worker` 하나가
   조건이다 (REQ-20260829-024). 화면이 따로 세지 않는다. */
function liveWorkerRows(){
  return (catalog || []).filter(r => r.type === "request" && r.worker);
}
async function sessionRestart(sid, req, T, cap){
  const what = restartWhat(req.model, req.effort, req.account);
  if (!sid){
    // 세션이 없으면 요청 자체가 성립하지 않는다 — 조용히 넘어가지 않는다
    await s9dlg({kind: "alert", cap: cap || "다시 시작",
      title: restartSay("세션 없음", what), ok: "닫기"});
    return;
  }
  /* 바꾸는 것은 **이 창 하나**다 (REQ-20260829-024).

     사용자: "계정을 변경하면 기존에 진행 중이던 작업들을 중단하는게 맞지 싶다."
     백그라운드에서 도는 무인 작업자는 이 재기동을 모른다 — 옛 계정·옛 모델로
     계속 돈다. 요금이 어느 계정에 붙는지도, 어느 모델이 쓰는지도 그때부터
     갈린다.

     그래서 도는 것이 있을 때만 한 번 묻고, 사람이 누르면 그 걸음을 같은
     요청에 실어 보낸다(서버가 거부 갈래를 다 지난 뒤에 세운다 — 못 바꾸면서
     돌던 일만 죽으면 잃기만 한다). 물러날 자리는 그만두기 하나다: 되돌릴 수
     없는 일이 두 개(세우기·재기동) 붙어 있는 창에서 Esc 가 그중 하나만 취소해
     주는 것은 사람이 예상할 수 없는 답이다. */
  const wk = liveWorkerRows();
  if (wk.length){
    // 한 번에 여러 건을 세우는 창이라 더더욱 물러나는 쪽에서 시작한다
    // (REQ-20260830-008).
    const go = await s9dlg({kind: "confirm", cap: cap || "다시 시작",
      stop: false, safe: true,
      title: `진행 중인 자동 작업 ${wk.length}건을 중단하고 ${what} 바꿉니다`,
      desc: "이 재시작은 이 창만 바꿉니다 — 중단하지 않으면 그 작업들은 옛"
        + " 설정 그대로 계속 진행됩니다. 중단하면 각 문서에 중단한 사실과 사유가"
        + " 남고, 나중에 그 카드의 「이어가기」로 다시 맡길 수 있습니다.",
      ok: "중단하고 바꾸기", cancel: "그만두기"});
    if (!go) return;
    req = Object.assign({}, req, {stopWorkers: true});
  }
  const d = await restartPost(sid, req);
  await restartTell(T, sid, req, d, what, cap || "다시 시작");
}

/* 재시작 완료·실패 마감 (REQ-20260825-047) — 진행 줄을 결과로 교체 */
function termRestartDone(T, kind, model){
  const r = T && T.restart;
  if (!r) return;
  clearInterval(r.timer);
  T.restart = null;
  const secs = fmtElapsed(new Date(r.t0).toISOString());
  if (r.el && r.el.isConnected){
    const b = r.el.querySelector(".b");
    // 실패해도 "재시작"이라는 낱말로 겁주지 않는다 — 무슨 일이 안 일어났는지를
    // 말한다. 세션은 끊긴 것이 아니라 **돌아오는 것이 확인되지 않은** 것이다.
    if (b) b.innerHTML = kind === "timeout"
      ? `<span style="color:var(--cc-red)">✗ 세션이 돌아온 것을 확인하지 못했습니다 (${secs}) — 세션 터미널을 봐 주세요</span>`
      : `<span style="color:var(--cc-green)">✓ 세션 재시작 완료 (${secs}) — ${esc((model || "").replace(/^claude-/, "") || "새 설정")}으로 이어집니다</span>`;
    const g = r.el.querySelector(".g");
    if (g) g.textContent = kind === "timeout" ? "✗" : "✓";
  }
  /* 헤더 칩도 함께 마감한다 (REQ-20260827-079 반려) — 두 자리가 같은 일을
     말하는데 하나만 끝나면, 남은 쪽이 거짓말이 된다. */
  if (kind === "timeout") restartChip("lost");
  else if (kind) restartChip("done");
}

/* Esc 중단 (REQ-20260825-001): 대시보드는 CC 프로세스에 키를 보낼 수 없다 —
   수신함에 kind=interrupt 줄을 남기면 세션이 다음 도구 경계에서 읽고 멈춘다.
   즉시 강제 중단은 세션이 떠 있는 터미널에서만 가능하다. */
async function termInterrupt(T){
  if (!T.sid || T.intBusy) return;
  T.intBusy = true;
  const out = $("#ccout"), w = $("#cc-wait");
  try{
    const r = await fetch("/api/chat", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({kind: "interrupt", sid: T.sid})});
    const d = await r.json();
    if (!d.ok) throw new Error(d.error || "중단 요청 실패");
    if (TERM === T && out && w){
      // signal=sent → SIGINT 즉시 중단 (REQ-20260825-008), skipped → 협조적 폴백
      const body = d.signal === "sent"
        ? `<span style="color:var(--cc-yellow)">⚡ 인터럽트 — 진행 중 턴을 즉시 중단</span>`
        : `<span style="color:var(--cc-dim)">중단 요청 큐잉${d.reason ? ` · ${esc(d.reason)}` : ""} — 세션은 다음 도구 경계에서 멈춘다</span>`;
      w.insertAdjacentHTML("beforebegin", ccLine("⨯", "var(--cc-dim)", body));
      out.scrollTop = out.scrollHeight;
    }
  }catch(ex){
    if (TERM === T) termErr("✗ " + ((ex && ex.message) || "중단 요청 실패"));
  }finally{
    T.intBusy = false;
  }
}

async function sendChat(){
  const T = TERM, ta = $("#chat-in");
  if (!T || !T.sid || !ta || ta.disabled) return;
  // disp = 화면에 보이는 것(접힌 칩 포함) · raw = 실제로 보내는 것(원문).
  // 둘을 섞지 마라 — 칩을 그대로 보내면 사용자가 붙인 내용이 조용히 사라진다.
  const disp = ta.value.trim();
  const raw = termPasteExpandAll(disp);
  if (T.atts.some(a => a.up)){ termErr("✗ 첨부 업로드 중 — 잠시 후 전송"); return; }
  const atts = T.atts.filter(a => a.path);
  if (!raw && !atts.length) return;
  let text = raw;
  // 이미지는 [Image:], 그 외 일반 파일은 [File:] — 문서 뷰 렌더가 갈린다
  /* 채팅 글은 화면이 지어서 보내므로(서버가 손댈 자리가 없다) 표기도 여기서
     붙인다 — 판정 창은 이제 서버(asset_mark)가 짓는다. 그림 판정은 IMAGE_EXT
     한 곳에서만 하고, 그 목록은 서버 TYPE_GROUPS["image"] 와 같아야 한다
     (어긋나면 그 확장자만 문서에서 깨진 칸이 된다 — 시험이 둘을 맞대어 본다). */
  atts.forEach(a => {
    const img = isImageName(a.name || a.path);
    text += `\n[${img ? "Image" : "File"}: ${a.path}]`;
  });
  // 로컬 에코 + 입력 클리어는 즉시(동기) — 네트워크 왕복과 결합하지 않는다 (L1).
  // 성공 시 수신함 echo 도착이 .pending을 제거·대체한다. 전송 중 입력 비활성화 금지.
  const out = $("#ccout"), w = $("#cc-wait");
  let pend = null;
  const tgt = T.target;
  const dt = tgt ? null : docTarget;   // 둘은 양립하지 않는다 — 에이전트가 이긴다
  if (out && w){
    const clip = atts.length
      ? ` <span style="color:var(--cc-dim)">📎${atts.length}</span>` : "";
    const to = tgt
      ? ` <span style="color:var(--cc-green)">→ ${esc(tgt.type || tgt.id)}</span>`
      : dt ? ` <span style="color:var(--cc-cyan)">→ ${esc(shortId(dt.id))}</span>` : "";
    w.insertAdjacentHTML("beforebegin",
      `<div class="ln pending"><span class="g" style="color:var(--cc-dim)">❯</span><span class="b">${ccText(disp || "(첨부)")}${clip}${to}</span></div>`);
    pend = w.previousElementSibling;
    out.scrollTop = out.scrollHeight;
  }
  if (disp && T.hist[T.hist.length - 1] !== disp) T.hist.push(disp);
  T.histIdx = null;
  ta.value = ""; ta.style.height = "auto";
  termPasteHint();          // 입력줄이 비었으니 안내줄도 내린다
  T.atts = []; termAttRender(T);
  termPalClose(T);
  T.lastRole = "user"; T.waitBase = Date.now();
  termSpinnerEval(T);
  try{
    const r = await fetch("/api/chat", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text, sid: T.sid,
                            ...(tgt ? {agent: tgt.id} : {}),
                            ...(dt ? {doc: dt.id} : {}),
                            ...(!tgt && !dt && asArticle ? {as_type: "article"} : {})})});
    const d = await r.json();
    if (TERM !== T) return;
    if (!d.ok){
      // 대상 부재(409)는 지목만 풀고 문구를 그대로 보여준다 — 사용자가
      // 같은 입력을 리드에게 바로 다시 보낼 수 있다 (아래 복원 경로)
      if (d.error === "agent-unavailable") termTargetClear(T);
      throw new Error(d.reason || d.error || "전송 실패");
    }
    termErrClear();
    // 전달 확인: 어느 에이전트에게 갔는지 즉시 한 줄로 확증 (REQ-095)
    if (d.agent && out && w){
      w.insertAdjacentHTML("beforebegin",
        ccLine("→", "var(--cc-green)",
          `<span style="color:var(--cc-dim)">${esc(d.agent_type || d.agent)} 에게 전달 — 리드가 중계한다</span>`, "sub"));
      out.scrollTop = out.scrollHeight;
    }
    // 서버측 audit가 REQ를 만들었으면 표시 — 세션 유휴여도 기록은 남았다는 확증.
    // 문서를 집어 보낸 경우엔 "만들어졌다"가 아니라 "그 문서에 붙었다"이다 —
    // 같은 줄로 뭉뚱그리면 새 요청이 하나 더 생긴 줄 안다 (REQ-20260827-064).
    if (d.req && out && w){
      const toDoc = dt && d.req === dt.id;
      const end = toDoc && (dt.status === "done" || dt.status === "cancelled");
      w.insertAdjacentHTML("beforebegin",
        ccLine("⎿", null, `<span style="color:var(--cc-dim)">${esc(d.req)} `
          + (toDoc ? "에 노트로 남았다" : "로 기록됨")
          // 끝난 요청은 노트만 남고 다시 열리지 않는다 — 한 줄로 말한다
          + (end ? ` — 이미 ${esc(dt.status)} 라 다시 열리지는 않는다`
                 + `<span style="color:var(--cc-faint)"> (열려면 상태를 옮겨라)</span>` : "")
          + `</span>`, "sub"));
      out.scrollTop = out.scrollHeight;
    }
    refreshTermChat(T);
  }catch(ex){
    if (TERM !== T) return;
    if (pend && pend.isConnected) pend.remove();
    termErr("✗ " + (ex && ex.message ? ex.message
      : "서버에 연결할 수 없습니다 — 잠시 후 다시 시도"));
    // 실패 시 입력 복원 — 접힌 표시 그대로 되돌린다(원문으로 펼쳐 놓으면
    // 사용자가 접어 둔 화면이 제멋대로 터진다). 매핑은 그대로 살아 있다.
    if (!ta.value){ ta.value = disp; termPasteHint(); }
    T.lastRole = null;
    termSpinnerEval(T);
  }
  ta.focus();
}

/* ------- graph (Obsidian-style: live physics, drag, pan/zoom, hover focus) ------- */
