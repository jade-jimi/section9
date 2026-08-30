/* card.js — 카드 한 장 — 멈춤·작업 자리·깨우기·판정 전이, 그리고 Board 컬럼 */
"use strict";
/* 손잡이의 낱말은 **한 곳**에 있다 (REQ-20260829-024 라운드4, designer 지적).

   글자가 HTML 을 짓는 자리와 눌린 뒤 다시 칠하는 자리 두 곳에 있었다. 그래서
   개명 한 번에 둘이 갈렸고, 처음 그려진 낱말과 한 번 눌렀다 돌아온 낱말이
   다른 화면이 실제로 났다 — 이 화면이 판정 버튼에서 세 번 배운 그 규칙이다.

   낱말 자체는 사용자가 고른 것이다(라운드4 반려: "깨우기, 세우기 라는 용어가
   너무 어색한데"). 멈춘 것도 중단해 둔 것도 하는 일이 같아 **한 낱말**을
   쓴다 — 처지의 차이는 버튼이 아니라 그 위의 줄이 말한다. */
const WAKE_LABEL = "이어가기", WAKE_GOING = "이어가는 중…";
const STOP_LABEL = "중단하기", STOP_GOING = "중단 중…";
const wokeAt = new Map();          // REQ id → 누른 시각(ms)
const WOKE_HOLD = 180000;          // 3분. 스폰이 조용히 죽어도 다시 누를 수 있게
function wokePending(id){
  const t = wokeAt.get(id);
  if (t == null) return false;
  if (Date.now() - t > WOKE_HOLD){ wokeAt.delete(id); return false; }
  return true;
}
/* 세우기도 같은 기억을 쓴다 (REQ-20260829-024). 다만 잠금은 짧다 — 세우기는
   서버가 SIGTERM 뒤 최대 5초를 기다렸다 답하고, 그 답이 오면 곧 행에서
   `worker` 가 사라져 손잡이 자체가 없어진다. 깨우기의 3분은 "스폰이 조용히
   죽어도 다시 누를 수 있게"라는 다른 사정에서 온 수라 그대로 쓰지 않는다. */
const stopAt = new Map();          // REQ id → 누른 시각(ms)
const STOP_HOLD = 20000;
function stopPending(id){
  const t = stopAt.get(id);
  if (t == null) return false;
  if (Date.now() - t > STOP_HOLD){ stopAt.delete(id); return false; }
  return true;
}
/* **멈춤 술어는 화면에 하나뿐이다** (REQ-20260828-041 2차 반려).

   화면에는 갈래가 둘 남아 있었다. ① 카드만 `!bl.length` 관문을 가져, 선행 대기
   줄이 선 요청은 카드에서 손잡이를 통째로 잃었는데 문서 화면은 그 관문을 몰라
   같은 요청을 깨울 수 있었다 — **같은 요청이 두 자리에서 다른 말을 한다**.
   ② 점은 `live_kind` 를, 손잡이는 `stalled_mins` 를 각자 읽었다. 서버가 라운드1
   에서 둘을 한 벌로 만들어도, 화면이 두 필드를 따로 읽는 한 한쪽만 서는 조합이
   남는다 — 그것이 사용자가 본 "멈췄다고 적혀 있는데 누를 게 없는 카드"다.

   그래서 판정을 여기 한 곳으로 모은다. 점·줄·손잡이·열 머리 수·정렬이 전부 이
   함수를 먹으므로 어긋날 자리가 구조적으로 없다.

   **화면은 분을 짓지 않는다**: 서버가 실어 준 값을 옮길 뿐이고(REQ-20260828-036),
   분이 없으면 서버가 준 이유(live_reason)를 그대로 쓴다. 스스로 세기 시작하면
   CLI(`s9 stalled`)와 다른 수를 말하게 된다.

   **문은 하나, 얼굴은 둘.** 문(멈췄나?)은 서버가 지금 다시 잰 `stalled_mins`
   하나가 연다 — 색인에 굳은 작업자 기록은 문을 열지 못한다(어제 22:36 의 정지가
   오늘 카드를 칠하던 자리다). `live_kind` 는 문 안에서 **얼굴만** 고른다:
   처리 주체가 죽은 것이 기록돼 있으면 실패의 사각(정지 신호의 관습), 아니면
   같은 사각의 속 빈 형태. 이렇게 하면 점·줄·손잡이가 셋 다 같은 문을 지나므로
   "멈췄다고 그려 놓고 못 누르는 카드"도, 그 반대(누를 수 있는데 점은 조용한
   카드)도 구조적으로 생길 수 없다.

   반환: null(안 멈췄다) 또는 {mins, face, reason}
     face "dead" = 처리 주체가 죽었다(spawn_failed) · "mild" = 진전이 끊겼다 */
function stallState(r){
  if (!r || r.type !== "request" || r.status !== "in-progress") return null;
  if (r.stalled_mins == null) return null;   // 서버가 안 잰 것은 멈춤이 아니다
  return {mins: r.stalled_mins,
          face: r.live_kind === "spawn_failed" ? "dead" : "mild",
          reason: r.live_reason || ""};
}
/* 이 요청에 지금 **사람이 할 수 있는 일**을 짓는 한 함수 (REQ-20260828-041,
   REQ-20260829-024).

   보드 카드와 문서 화면이 각자 글자를 가지면 한쪽만 고쳐진다 — 판정 버튼이
   그 이유로 세 번 반려됐다 (REQ-20260828-007). 같은 함수를 부르면 갈라질 자리가
   없다. 안 멈춘 행에는 빈 문자열을 돌려준다 — 부르는 쪽이 조건을 따로 갖지
   않게 하려는 것이다(그 조건이 갈래를 낳았다).

   손잡이는 이제 둘이다. 멈춘 것은 **깨우고**, 도는 것은 **세운다**. 둘을 한
   함수에 둔 이유도 같다: 부르는 자리가 둘(카드·문서)인데 조건을 따로 두면
   같은 요청이 한 자리에선 세워지고 다른 자리에선 안 세워진다 — 이 화면이
   이미 한 번 겪은 갈래다. 둘은 사실상 배타적이다(도는 것은 멈춘 것이 아니다).
   그래도 겹쳐 서는 순간이 있으면 그대로 둘 다 그린다: 서버가 그렇게 말한
   것이고, 화면이 서버의 말을 지우는 자리는 두지 않는다. */
/* 손길 줄 (REQ-20260830-019·021 designer 검토 ③) — 문서는 조용하지만 최근
   손길이 있는 카드. 종전에는 카드가 아무 말도 안 해 건강한 카드와 구별되지
   않았고, 그 사실이 문서로 들어가 깨우기를 눌러야 뜨는 거절 창에만 살았다 —
   "조용함을 감추지 않는다"의 정면 위반. 같은 .rvpt 한 줄, 버튼 없음(버튼이
   없는 것 자체가 "지금 할 일 없음"의 신호), 문장은 서버의 stall_why 그대로. */
function handRowHTML(r){
  if (!r || r.type !== "request" || r.stall_state !== "attached") return "";
  if (r.hand_mins == null || r.quiet_mins == null) return "";
  return `<div class="rvpt hand" title="${esc(r.stall_why || "")}">`
    + `<span class="rvcap">손길</span>`
    + (r.hand_mins < 1 ? "방금" : `${fmtStall(r.hand_mins).replace(/째$/, "")} 전`)
    + ` · ${fmtStall(r.quiet_mins)} 조용</div>`;
}
function stallHTML(r){
  const work = workRowHTML(r);
  const stopped = stoppedRowHTML(r);
  const st = stallState(r);
  /* 중단해 둔 카드에는 **줄이 하나만** 선다 (라운드4 반려). 중단하면 그 사유가
     문서에 적히고, 15분이 지나면 그 문서는 다시 '조용한' 것이 되어 멈춤 줄이
     함께 서려 한다 — 그러면 한 카드가 같은 요청을 두고 「멈춤」과 「중단」을
     한꺼번에 말한다. 사람이 자기 손으로 중단한 것이 더 구체적인 근거이므로
     그쪽을 세운다(마커 판정이 점을 이기는 그 규칙과 같다). */
  if (stopped) return work + stopped;
  const hand = handRowHTML(r);
  if (!st && !work && !hand) return "";
  if (!st) return work + hand;
  // 마지막 시각을 못 읽으면 그 조각만 빠진다 — "· 마지막 " 로 끝나는 줄은 값이
  // 있는데 못 그린 것처럼 보인다.
  const last = fmtLast(r.updated || r.status_since);
  const going = wokePending(r.id);
  return `<div class="rvpt stall" title="이 문서가 마지막으로 바뀐 뒤로 `
    + `${st.mins}분 — 그동안 이 문서에 아무것도 적히지 않았다`
    // 죽음이 기록돼 있으면 그 말을 함께 싣는다 — 점의 툴팁과 같은 문장이다.
    + (st.face === "dead" && st.reason ? ` (${esc(st.reason)})` : "") + `">`
    /* 커밋 드리프트 (REQ-20260830-018, 낱말·순서는 REQ-20260830-021 검토):
       고친 것은 있는데 문서가 안 닫힌 카드는 "이어서 일할 것"이 아니라
       "끝났는지 확인할 것"이라 손잡이의 낱말이 바뀐다. 조각 순서는 시간순이
       아니라 결정 무게순 — 이 줄은 ellipsis 라 뒤부터 잘리는데, 「고친 것
       있음」이 잘리면 버튼만 다른 낱말로 서는 근거 없는 손잡이가 된다. */
    + `<span class="rvcap">멈춤</span>${fmtStall(st.mins)} 진전 없음`
    + (r.commit_drift ? ` · 고친 것 있음` : "")
    + (last ? ` · 마지막 ${esc(last)}` : "") + `</div>`
    + `<div class="acts wakerow"><button type="button" class="deed wake"`
    + ` data-wake="${esc(r.id)}"${going ? " disabled" : ""}`
    + ` title="${r.commit_drift
      ? "고친 것이 있습니다 — 자동 작업이 요청한 일이 다 됐는지 확인해서, 됐으면 마무리하고 아니면 이어갑니다"
      : "자동 작업이 이 요청을 이어서 진행합니다"}">`
    + `${going ? WAKE_GOING : (r.commit_drift ? "끝났는지 확인" : WAKE_LABEL)}</button></div>` + work;
}
/* 도는 작업자와 그 손잡이 — 깨우기의 반대편 (REQ-20260829-024).

   사용자: "반대로 진행 중인 작업들을 강제로 중단하는 기능도 만들어라. 그래야
   계정을 변경하거나 모델을 바꿀 때 그 기능을 같이 섞어서 사용할 수 있다."

   **조건은 서버가 준 `worker` 하나다.** 점(`live_kind`)으로 대신하지 않는다:
   그 값은 클레임 **전**(spawned)만 말하고, 작업자가 문서를 집는 순간 direct 로
   덮여 "지금 돌고 있다"는 사실이 행에서 사라진다 — 정작 세울 것이 있는 카드에
   손잡이가 안 서는 조합이다.

   줄을 함께 세우는 이유: 버튼만 있으면 무엇을 세우는지가 안 적힌다. 점은
   얹어야 읽히는 툴팁이고, 이 카드에서 세워지는 것은 **사람이 안 보는 곳에서
   도는 프로세스**라 카드 위에 글자로 한 번은 서야 한다.

   분은 서버가 준 초를 단위만 바꿔 옮긴다 — 화면이 스스로 시계를 대면 CLI 와
   다른 수를 말하게 된다 (REQ-20260828-036). */
function workRowHTML(r){
  if (!r || r.type !== "request") return "";
  /* 긴 잡 조각 (REQ-20260830-022): 이 요청에 귀속된 테스트 스위트 등. 서버가
     pid 생존·명령줄 대조를 지나 실은 값만 그린다 — 화면 재판정 없음. */
  const jbit = (r.jobs || [])
    .map(j => `${esc(j.name)} ${fmtStall(+j.mins || 0)}`).join(" · ");
  if (!r.worker){
    if (!jbit) return "";
    return `<div class="rvpt work" title="이 요청에 귀속된 작업이 돌고 있습니다`
      + ` — 끝나면 저절로 이어집니다">`
      + `<span class="rvcap">진행 중</span>${jbit}</div>`;
  }
  const going = stopPending(r.id);
  const mins = fmtStall(Math.floor((+r.worker.age || 0) / 60));
  return `<div class="rvpt work" title="자동 작업이 이 요청을 맡아 진행 중입니다`
    + ` — 중단하면 지금 하던 일이 거기서 끝나고, 중단한 사유가 문서에 남습니다">`
    // 캡션이 이미 "진행 중"을 말한다 — 본문이 그 말을 되풀이하면 좁은 줄에서
    // 낱말 하나(`작업`)가 세 번 선다. 멈춤 줄과 같은 틀이다: 캡션 + 사실.
    + `<span class="rvcap">진행 중</span>자동 작업 ${mins}`
    + (jbit ? ` · ${jbit}` : "") + `</div>`
    + `<div class="acts stoprow"><button type="button" class="deed stop"`
    + ` data-stop="${esc(r.id)}"${going ? " disabled" : ""}`
    + ` title="진행 중인 자동 작업을 중단합니다 — 계정이나 모델을 바꾸기 전에 씁니다">`
    + `${going ? STOP_GOING : STOP_LABEL}</button></div>`;
}
/* 사람이 세워 둔 요청과 그것을 되돌리는 손잡이 (REQ-20260829-024 라운드4).

   사용자: "멈춰놓고선, 다시 시작할 수 있는 기능이 없다."

   맞는 지적이었다. 세우면 그 사유가 문서에 적히고, 그 순간 이 요청은 '방금
   움직인 것'이 되어 멈춤 판정에서 빠진다 — 그래서 세운 직후 15분 동안 카드에
   **아무 손잡이도 없었다.** 세운 사람이 자기가 세운 것을 되돌릴 수 없는 화면은
   세우기가 절반만 있는 것과 같다.

   길은 깨우기와 **같은 길**이다(`wakeDoc` → `/api/wake`). 하는 일이 같은데
   길을 둘로 파면 한 벌만 고쳐진다 — 이 화면이 판정 버튼에서 세 번 배운 것이다.
   다른 것은 낱말뿐이라, 낱말만 손잡이가 들고 다닌다(`data-wlabel`). */
function stoppedRowHTML(r){
  if (!r || r.type !== "request" || !r.stopped || r.worker) return "";
  const going = wokePending(r.id);
  // 캡션이 이미 `중단` 을 말한다 — 본문은 언제였는지만 얹는다(`진행 중` 줄이
  // 세운 틀). 분은 서버가 준 초를 단위만 바꿔 옮긴다.
  const mins = fmtStall(Math.floor((+r.stopped.age || 0) / 60))
    .replace(/째$/, " 전");
  return `<div class="rvpt held" title="이 요청의 자동 작업을 사람이 중단했습니다`
    + ` — 「이어가기」를 누르기 전까지는 저절로 이어지지 않습니다">`
    + `<span class="rvcap">중단</span>${mins}</div>`
    // 손잡이의 낱말이 멈춘 카드의 것과 **같다**: 하는 일이 같기 때문이다
    // (같은 길·같은 응답). 처지의 차이는 버튼이 아니라 위의 줄이 말한다.
    + `<div class="acts wakerow"><button type="button" class="deed wake"`
    + ` data-restart="${esc(r.id)}"${going ? " disabled" : ""}`
    + ` title="중단한 이 요청을 자동 작업이 다시 이어서 진행합니다">`
    + `${going ? WAKE_GOING : WAKE_LABEL}</button></div>`;
}
/* ?stall=<분>[&stallkind=stalled|spawn_failed][&stalldep][&stallhold] — 멈춤 줄과
   `깨우기` 를 **진짜로 세운다** (REQ-20260828-041 반려).

   네 얼굴: 보통(분만) · 죽음이 기록된 것(stallkind=spawn_failed, 채운 사각) ·
   선행 대기와 동거(stalldep) · 누른 직후 잠김(stallhold, `깨우는 중…`).

   이 손잡이는 카탈로그 행에 `stalled_mins` 가 실릴 때만 그려지는데, 그 조건은
   저장소가 한동안 조용해야 성립한다 — 여러 세션이 몇 분마다 노트를 쓰는 이
   환경에서는 캡처를 찍으려는 바로 그 순간에 거의 없다. 그래서 이 단추는 두 번
   고쳐 올려지는 동안 **한 번도 눈으로 확인된 적이 없었다.** 진단 파라미터가
   예순 개 넘게 있는데 이 화면을 세우는 것만 없었다.

   그림을 따로 만들지 않는다 — 서버가 준 행에 **서버가 줬을 값**을 얹고, 그
   다음은 평소 그리던 길(cardHTML → stallHTML)이 그대로 그린다. 진단이 하는
   일은 값 하나를 넣는 것뿐이다. */
/* ?drift — 멈춤 줄에 「고친 것 있음」과 「끝났는지 확인」 손잡이를 세운다.
   ?hand=<분>[&handquiet=<분>] — 손길 줄을 세운다 (REQ-20260830-021 designer ④:
   이 두 화면은 실데이터에선 캡처 순간에 거의 없어, 파라미터 없이는 또
   "만들었다는데 본 적은 없는" 것이 된다). 서버가 줬을 값을 얹기만 한다. */
function driftProbe(rows){
  if (!/[?&]drift\b/.test(location.search) || !Array.isArray(rows)) return rows;
  for (const r of rows)
    if (r.type === "request" && r.status === "in-progress")
      r.commit_drift = true;
  return rows;
}
function handProbe(rows){
  const m = /[?&]hand=(\d+)/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  const q = +((/[?&]handquiet=(\d+)/.exec(location.search) || [])[1] || 34);
  let n = 0;
  for (const r of rows){
    if (r.type !== "request" || r.status !== "in-progress") continue;
    // 서버 규칙 그대로: attached 는 stalled_mins 를 싣지 않는다.
    r.stall_state = "attached";
    r.hand_mins = Math.max(0, +m[1] + n);
    r.quiet_mins = q + 7 * n;
    r.stall_why = "다른 곳에서 이 요청을 만지는 중입니다 — 진단으로 세운 값";
    r.stalled_mins = null;
    n++;
  }
  return rows;
}
function stallProbe(rows){
  // 한 카드의 두 손잡이는 부르는 자리를 하나로 둔다 — 진단이 늘어날 때마다
  // 파이프라인에 줄이 붙으면, 어느 진단이 어느 화면을 세우는지 흩어진다.
  workProbe(rows);
  heldProbe(rows);
  handProbe(rows);
  driftProbe(rows);
  const m = /[?&]stall=(\d+)/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  const mins = Math.max(1, Math.min(9999, +m[1] || 20));
  const kind = (/[?&]stallkind=(\w+)/.exec(location.search) || [])[1] || "";
  const dep = /[?&]stalldep\b/.test(location.search);
  const hold = /[?&]stallhold\b/.test(location.search);
  const open = rows.filter(r => r.type === "request" && r.status === "open");
  let n = 0;
  for (const r of rows){
    if (r.type !== "request" || r.status !== "in-progress") continue;
    if (r.stalled_mins == null) r.stalled_mins = mins + 7 * n;
    if (kind && !r.live_kind){ r.live_kind = kind; r.live_reason = "진단으로 세운 값"; }
    // 선행 대기 줄과 **함께** 서는 카드 — 2차 반려가 뒤집은 그 자리다. 이 조합은
    // 실데이터에 거의 없어서(in-progress 인데 선행이 안 끝난 경우), 뒤집힌 규칙이
    // 맞게 그려지는지 눈으로 볼 길이 없었다.
    if (dep && open.length && !(r.blocked_by || []).length)
      r.blocked_by = [open[n % open.length].id];
    // 누른 직후의 잠긴 얼굴(`깨우는 중…`). 서버 왕복 중에만 보이는 화면이라
    // 손이 없으면 못 찍는다 — ?svchip= 이 낸 선례와 같은 자리다. 한 칸 걸러
    // 잠가 **잠긴 얼굴과 안 잠긴 얼굴이 한 화면에** 서게 한다.
    if (hold && n % 2 === 0) wokeAt.set(r.id, Date.now());
    n++;
  }
  return rows;
}
/* ?work[=<분>][&workhold] — `작업 중` 줄과 `세우기` 를 진짜로 세운다
   (REQ-20260829-024).

   깨우기가 두 번 고쳐 올려지는 동안 한 번도 눈으로 확인된 적이 없던 이유가
   여기 그대로 있다: 이 손잡이는 **그 순간 무인 작업자가 돌고 있어야** 그려진다.
   사람이 캡처를 찍으려는 바로 그때 도는 작업자가 없으면 화면을 볼 길이 없고,
   그러면 또 "만들었다는데 본 적은 없는" 것이 된다.

   그림을 따로 짓지 않는다 — 서버가 줬을 값(`worker`)을 행에 얹고, 그다음은
   평소 그리던 길(cardHTML → stallHTML → workRowHTML)이 그대로 그린다. */
/* ?jobrow[=<분>] — 카드의 긴 잡 조각을 세운다 (REQ-20260830-022). */
function jobRowProbe(rows){
  const m = /[?&]jobrow(?:=(\d+))?\b/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  for (const r of rows)
    if (r.type === "request" && r.status === "in-progress")
      r.jobs = [{name: "테스트", mins: +(m[1] || 4)}];
  return rows;
}
function workProbe(rows){
  jobRowProbe(rows);
  const m = /[?&]work(?:=(\d+))?\b/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  const mins = Math.max(0, Math.min(9999, +(m[1] || 12)));
  const hold = /[?&]workhold\b/.test(location.search);
  let n = 0;
  for (const r of rows){
    if (r.type !== "request" || r.status !== "in-progress") continue;
    // 서버의 규칙을 그대로 흉내 낸다 (designer 지적): 도는 작업이 있으면
    // 서버는 멈춤을 싣지 않는다. 진단만 둘을 함께 세우면 **존재할 수 없는
    // 카드**를 지어내고, 다음 사람이 그 그림에 맞춰 화면을 고치게 된다.
    if (!r.worker) r.worker = {pid: 424242 + n, age: mins * 60 + 37 * n};
    r.stalled_mins = null;
    delete r.stopped;
    // 누른 직후의 잠긴 얼굴(`세우는 중…`)은 서버 왕복 중에만 보인다 — 한 칸
    // 걸러 잠가 두 얼굴이 한 화면에 서게 한다 (?stallhold 가 낸 선례).
    if (hold && n % 2 === 0) stopAt.set(r.id, Date.now());
    n++;
  }
  return rows;
}
/* ?held[=<분>][&heldhold] — 「중단」 줄과 「이어가기」를 진짜로 세운다
   (REQ-20260829-024 라운드4).

   이 줄은 **사람이 방금 중단한 요청이 있어야** 그려진다 — 캡처를 찍으려는 그
   순간에는 대개 없고, 만들려면 진짜 자동 작업을 하나 죽여야 한다. 진단이
   없으면 이 화면은 또 "만들었다는데 본 적은 없는" 것이 된다(깨우기가 두 번
   그렇게 올라갔다). 여기서도 그림을 따로 짓지 않는다: 서버가 줬을 값을 얹고
   평소 그리던 길이 그대로 그린다. */
function heldProbe(rows){
  const m = /[?&]held(?:=(\d+))?\b/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  const mins = Math.max(0, Math.min(9999, +(m[1] || 12)));
  const hold = /[?&]heldhold\b/.test(location.search);
  let n = 0;
  for (const r of rows){
    if (r.type !== "request" || r.status !== "in-progress") continue;
    if (!r.stopped)
      r.stopped = {at: Date.now() / 1000 - mins * 60, by: "nicehugepark",
                   age: mins * 60 + 41 * n};
    // 서버는 이 셋을 함께 싣지 않는다 — 진단도 그 규칙을 지킨다.
    delete r.worker;
    if (hold && n % 2 === 0) wokeAt.set(r.id, Date.now());
    n++;
  }
  return rows;
}
/* ---- 작업 자리 (REQ-20260829-030) ----------------------------------------

   무인 작업자는 워크트리(격리된 사본)에 앉는 것이 기본이지만, 아직 커밋되지
   않은 코드가 있으면 그 사본이 **낡은 자리**가 되므로 본 저장소에 앉는다
   (REQ-20260829-028). 말없이 다르게 동작하면 다음 사람이 또 헤맨다 — 워크트리
   에서 고친 화면은 지금 도는 서버(9909)에 영영 안 나타나므로, 무엇을 어디서
   확인할지가 자리에 달려 있다.

   **화면은 판정하지 않는다.** 서버가 행에 실어 준 `workspace{kind,reason,wt,at}`
   를 옮길 뿐이다 — 멈춤 줄이 이미 세운 규칙이다(REQ-20260828-036: 화면이 스스로
   재기 시작하면 CLI 와 다른 말을 하게 된다). 여기에 판정을 한 줄이라도 적으면
   서버의 `workspace_decision` 과 두 벌이 되고, 그때부터 한 벌만 고쳐진다.

   **키는 없을 수 있다.** 그 문서에 새 코드로 스폰이 아직 없으면 서버가 키
   자체를 안 싣는다. 없으면 아무것도 그리지 않는다 — 빈 칸도, "미상"도 아니다.
   모르는 것에 자리를 주면 판이 매일 그 자리를 먹는다(같은 규칙을 취소 열에서
   한 번 더 쓴다 — REQ-20260829-031). */
const WS_PLACE = {main: "본 저장소", worktree: "워크트리"};
/* 자리에는 **표가 붙는다** (REQ-20260829-030 2차 반려: "어떤 화면에서 확인할 수
   있는지 모르겠다"). 1차는 낱말만 세웠는데, 메타 줄은 이미 이름·급·크기·태그가
   서는 자리라 낱말 하나는 지나가는 태그로 읽혔다 — 실제로 보드에 값이 붙은
   카드가 있었는데도 사람이 못 찾았다.

   지금 이 표가 서는 자리는 **문서의 메타 표 한 곳뿐**이다(4·5차 반려로 카드와
   헤더에서 차례로 내렸다). 그래도 표를 남기는 것은, 메타 표의 다른 칸들이
   전부 글자뿐이라 이 칸만 눌러서 펼 수 있다는 것을 표가 말해 주기 때문이다. */
const WS_MARK = "◇";
/* 사유 → [사람 말, 사람이 무엇을 하면 풀리는가].

   둘째 칸은 **비어 있어도 된다.** 풀 것이 없는 자리에 할 일을 지어내면 그
   문장은 매번 참이라 곧 안 읽히고, 진짜로 손이 필요한 자리까지 함께 묻힌다.
   실제로 손이 드는 것은 둘뿐이다 — 미커밋 코드(커밋)와 워크트리 쌓임(거두기). */
/* 말결은 창의 것이다 (REQ-20260830-007). 이 문장들이 서는 자리는 손 위의 글과
   창 하나뿐인데, 창의 다른 줄(WS_MEANS)은 존댓말이라 여기만 반말이면 한 창
   안에서 말이 두 결로 갈린다 — 사용자가 깨우기 창에서 지적한 그 어긋남이다. */
const WS_FIX_COMMIT = "커밋하면 다음 작업부터 다시 워크트리로 갑니다";
const WS_FIX_SWEEP = "다 쓴 워크트리를 거두면 다시 워크트리로 갑니다";
/* 자리가 **나에게 무슨 뜻인가** — 자리 이름·사유보다 이것이 먼저 궁금하다.
   사유는 왜 저기 앉았는지를 말할 뿐, 내가 지금 보고 있는 화면에서 그 작업을
   확인할 수 있는지는 말하지 않는다. 그게 이 요청이 애초에 세우려던 사실이다.
   자리 이름을 문장 안에 다시 적지 않는다 — 이름은 WS_PLACE 한 곳에서만 온다. */
const WS_MEANS = {main: "고친 것은 지금 보고 있는 이 화면에 바로 나타납니다",
  worktree: "고친 것은 따로 떼어 둔 사본에 있어, 커밋되기 전까지 이 화면에 나타나지 않습니다"};
const WS_WHY = {
  "off": ["워크트리를 쓰지 않도록 설정돼 있습니다", ""],
  "fresh": ["미커밋 코드가 없어 새 워크트리를 냈습니다", ""],
  "fresh-outside": ["미커밋 코드가 이 요청이 고칠 범위 밖이라 워크트리를 냈습니다", ""],
  "worktree-exists": ["이 요청의 워크트리가 이미 살아 있어 둘째를 만들지 않았습니다", ""],
  "worktree-pile": ["워크트리가 한도까지 쌓여 더 만들지 않습니다", WS_FIX_SWEEP],
  "dirty-spine": ["모두가 쓰는 파일이 아직 커밋되지 않아, 워크트리에 앉히면 "
                  + "그 코드가 빠진 낡은 사본에서 일하게 됩니다", WS_FIX_COMMIT],
  "dirty-overlap": ["이 요청이 고칠 파일이 아직 커밋되지 않았습니다", WS_FIX_COMMIT],
  "dirty-unknown": ["아직 커밋되지 않은 코드가 있고, 이 요청이 어느 파일을 "
                    + "고칠지는 문서에 적혀 있지 않습니다", WS_FIX_COMMIT],
  // 문장 안에 줄표를 넣지 않는다 — 손 위의 문장이 이미 줄표로 사유를 잇는다.
  // 한 문장에 줄표가 둘이면 어디까지가 사유인지 눈이 다시 훑는다.
  "live-verify": ["살아 있는 서버로 확인해야 하는 작업이라서입니다(워크트리에서 고친 "
                  + "화면은 그 서버에 나타나지 않습니다)", ""],
  "self-edit": ["작업 도구 자신을 고치는 일이라서입니다(워크트리에서는 그 도구가 잘립니다)", ""],
  "create-failed": ["워크트리를 만들지 못했습니다", ""],
};
/* 반환 null(그릴 것이 없다) 또는 {kind, wt, place, why, fix}.
   조건은 stallState 와 같은 자리에 둔다 — 카드와 문서 화면이 각자 관문을 가지면
   같은 요청이 두 자리에서 다른 말을 한다(REQ-20260828-041 2차가 그 병이었다). */
function wsState(r){
  if (!r || r.type !== "request" || r.status !== "in-progress") return null;
  const w = r.workspace;
  if (!w || !WS_PLACE[w.kind]) return null;   // 없는 것은 그리지 않는다
  const why = WS_WHY[w.reason] || ["", ""];
  return {kind: w.kind, wt: w.wt || "", place: WS_PLACE[w.kind],
          why: why[0], fix: why[1]};
}
// 손 위의 문장도 한 곳에서 짓는다 — 칩·창·헤더가 같은 말을 쓴다.
function wsTitle(s){
  // 낱말은 WS_PLACE 한 곳에서 온다 — 여기에 다시 적으면 자리 이름이 두 벌이 된다.
  // 워크트리는 **어느 워크트리인지**까지 말한다(사람이 cd 해서 볼 자리다).
  // `wt` 는 kind 가 main 일 때도 실릴 수 있어서(이미 있는 워크트리를 두고 본
  // 저장소로 간 경우) 이름을 붙이는 조건은 kind 로 본다.
  const where = s.kind === "worktree" && s.wt ? `${s.place} ${s.wt}` : s.place;
  return `이 요청을 이어서 하는 자동 작업이 ${where}에서 돕니다`
    + (s.why ? ` — ${s.why}` : "") + (s.fix ? `. ${s.fix}` : "");
}
/* 카드에는 서지 않는다 (REQ-20260829-030 4차 반려).

   사용자: "'◇ 본 저장소' 이 기능은 사용자에겐 굳이 노출할 필요가 없는 정보
   아닌가? … 시스템이 사용하는 변수아닌가? 문서에 포함은 되어도 상관은 없을 것
   같은데 카드에 보여주는건 혼란만 가중하는것같다."

   맞는 지적이고, 2·3차가 답을 **더 크게 만드는 쪽**으로 갔던 것이 잘못이었다.
   1차 반려("못 찾겠다")에 표를 붙였고, 2차("어디서 확인하나")에 창을 달았다 —
   못 찾는다는 말에 계속 키워서 답했는데, 정작 물음은 "이걸 왜 내가 보나"였다.
   보드는 **지금 무슨 일이 어디까지 왔나**를 훑는 판이고, 작업자가 어느 사본에
   앉았는지는 그 물음의 답이 아니다. 카드 아홉 장에 아홉 번 서면 그건 사실이
   아니라 배경이 된다.

   그래서 이 칩이 서는 자리는 이제 **하나뿐**이다 — 문서 화면의 메타 표.
   사용자가 "문서에 포함은 되어도 상관없다"고 한 자리이고, 제목 옆이 아니라
   표 안이다(제목 줄은 훑는 자리라 카드와 같은 문제가 된다).

   헤더 칩도 5차 반려로 내렸다(아래 wsBoardNote 자리의 주석에 경위가 있다).
   훑는 자리 둘에서 차례로 내려온 셈인데, 다섯 번의 반려가 가리킨 것은 하나다:
   **깃을 모르는 사람에게 이 사실은 읽을 것도 할 일도 아니다.**

   표 + 낱말, 그리고 **누를 수 있다** (REQ-20260829-030 2차 반려).

   1차는 손 위의 글(title)에만 설명을 뒀다. 손 위의 글은 찾은 사람에게만 열리는
   문이라, 못 찾았다는 반려에 답이 되지 못한다 — 이 화면은 이미 같은 값을 두 번
   치렀다(판정 창의 상태 이름을 귀띔에서 문장으로 내린 REQ-20260828-007 반려).
   그래서 표를 붙여 찾게 하고, 누르면 창이 열려 읽게 한다. 손 위의 글은 그대로
   둔다: 빠른 쪽은 여전히 얹기만 하면 된다.

   `<span>` 이다. 버튼 요소로 세우면 지우개 규칙(배경·테두리 없애기)이 붙는데,
   이 칩의 재질 계약은 "색면·테두리를 **주지 않는다**"라 지울 것도 없어야 맞다. */
function wsChip(r){
  const s = wsState(r);
  if (!s) return "";
  return `<span class="wsat${s.kind === "main" ? " here" : ""}" role="button"`
    + ` tabindex="0" data-wsat="${esc(r.id)}"`
    + ` title="${esc(wsTitle(s))} (눌러서 자세히)">`
    + `<i class="wsm">${WS_MARK}</i>${esc(s.place)}</span>`;
}
/* 칩을 누르면 그 요청 **하나**의 자리를 편다 (REQ-20260829-030 2차).

   이 창은 눈앞의 문서 한 건을 말한다 — 사람이 누른 것이 그 문서라, 답도 그
   문서여야 한다. 글은 새로 짓지 않는다: 자리·사유·푸는 법은 wsState 가 이미
   고른 것이고, 여기서 더하는 것은 "그래서 나에게 무슨 뜻인가"(WS_MEANS)
   한 줄뿐이다. (저장소 전체를 모아 말하던 헤더 칩은 5차 반려로 없앴다.)

   **뜻이 사유보다 먼저다** (3차 반려). 2차는 사유 → 뜻 → 푸는 법 순이었는데,
   사람이 이 칩을 누르며 품은 질문은 "왜 저기 앉았나"가 아니라 "그래서 이걸
   **어느 화면에서 확인하나**"다 — 반려문이 그대로 그 문장이었다. 창의 첫 줄이
   질문의 답이 아니면 사람은 답을 못 찾은 채로 창을 닫는다. 사유는 답을 받은
   뒤에 궁금해지는 것이라 둘째 줄로 내린다. */
function wsOpen(id){
  const s = wsState(catFind(id));
  if (!s) return;
  const where = s.kind === "worktree" && s.wt ? `${s.place} ${s.wt}` : s.place;
  s9dlg({kind: "alert", cap: "작업 자리", stop: false,
    title: `${shortId(id)} 를 이어서 하는 자동 작업은 ${where}에서 돕니다`,
    descHtml: `<div class="wsrow wsans">${esc(WS_MEANS[s.kind] || "")}.</div>`
      + (s.why ? `<div class="wsrow">${esc(s.why)}.</div>` : "")
      + (s.fix ? `<div class="wsfix">${esc(s.fix)}.</div>` : ""),
    ok: "닫기"});
}
/* 헤더 칩(wsBoardNote)은 **없앴다** (REQ-20260829-030 5차 반려).

   사용자: "이 시스템이 워크트리도 만들고, 커밋도 해야하지. 하지만 사용자는
   깃을 전혀 모르는 상태에서도 요청이 잘 되느냐 마느냐, 질문이 답변을 받느냐
   마느냐 등만 관심분야다. 개발자나 엔지니어가 아닌 사용자가 이 시스템을
   사용한다고 가정하고 판단해라."

   그 칩이 하던 말은 「◇ 본 저장소에서 4건 · 커밋하면 다시 워크트리로 간다」
   였다. 깃을 모르는 사람에게 그것은 읽을 수 없는 문장이고, 읽어도 **자기가
   할 일이 아니다** — 커밋은 이 시스템이 알아서 하는 일이다. 헤더 칩은 사람
   손이 드는 사실만 서는 자리인데(REQ-20260827-018), 이 사실은 그 자격이 없다.

   1~4차가 답을 계속 **키우는 쪽**으로 갔던 것이 잘못이었다: 못 찾겠다 → 표를
   붙이고, 어디서 보나 → 창을 달고, 카드에 왜 있나 → 카드에서 내렸다. 물음은
   줄곧 "이걸 왜 내가 봐야 하나"였고, 옳은 답은 **안 보여 주는 것**이었다.

   사실이 사라지는 것은 아니다. `workspace` 는 문서의 메타 표에 남고(4차에서
   사용자가 "문서에 포함은 되어도 상관없다"고 했다), 운영하는 쪽은 `s9 doctor`·
   `s9 worktree ls` 로 본다 — 화면에서 내린 것은 **읽으라고 요구하는 자리**뿐이다.

   진행이 실제로 막히는 경우는 이것과 다르다. 그때는 카드가 「차례를 기다리는
   중」으로 말한다(REQ-20260829-036) — 깃을 몰라도 읽히는 문장이다. */
/* ?ws[=main/dirty-spine,worktree/fresh,…] — 자리 표시를 **진짜로 세운다**.

   서버가 이 값을 싣기 시작하는 것은 그 문서에 새 코드로 스폰이 한 번 일어난
   뒤부터라, 오늘 이 저장소에는 값을 가진 카드가 하나도 없다. 손잡이 하나가
   두 번 고쳐 올려지는 동안 한 번도 눈으로 확인된 적이 없던 일이 이미
   있었다(REQ-20260828-041) — 같은 일을 되풀이하지 않는다.

   그림을 따로 만들지 않는다: 서버가 줬을 값을 행에 얹고, 그다음은 평소 그리던
   길(cardHTML → wsChip · renderSvChip)이 그대로 그린다. 자리 판정은 여기서도
   하지 않는다 — 어느 사유가 어느 자리로 가는지는 서버가 아는 것이라, 진단은
   `kind/reason` 을 그대로 받아 적을 뿐 사유에서 자리를 유추하지 않는다. */
const WS_DEMO = ["main/dirty-spine", "worktree/fresh", "main/worktree-pile",
                 "main/self-edit", "worktree/fresh-outside", "main/dirty-overlap",
                 "main/live-verify", "main/dirty-unknown", "main/worktree-exists"];
function wsProbe(rows){
  const m = /[?&]ws(?:=([\w,/-]*))?(?:&|$)/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  const spec = (m[1] || "").split(",").filter(Boolean);
  const list = spec.length ? spec : WS_DEMO;
  let n = 0;
  for (const r of rows){
    if (r.type !== "request" || r.status !== "in-progress") continue;
    if (r.workspace) continue;               // 진짜 값이 있으면 덮지 않는다
    const [a, b] = list[n % list.length].split("/");
    const kind = b ? a : "main", reason = b || a;
    r.workspace = {kind, reason,
      wt: kind === "worktree" ? "w-" + String(r.id).slice(-12) : "",
      at: new Date().toISOString()};
    n++;
  }
  return rows;
}
/* ?cancelfresh[=N] — 취소 열이 **서는 날**을 세운다 (REQ-20260829-031).

   이 저장소의 취소 다섯 건은 전부 이틀이 넘었다. 그래서 "취소된 것이 있는
   날에는 반드시 보인다"는 쪽은 평소에 눈으로 볼 길이 없다 — 안 보이는 것만
   확인하고 마치면 감춘 것이 아니라 잃은 것일 수 있다. 새 문서를 지어내지 않고
   있는 취소 문서의 시각만 오늘로 당긴다. */
function cancelProbe(rows){
  const m = /[?&]cancelfresh(?:=(\d+))?/.exec(location.search);
  if (!m || !Array.isArray(rows)) return rows;
  let left = m[1] ? +m[1] : 2;
  for (const r of rows){
    if (left <= 0) break;
    if (r.type !== "request" || r.status !== "cancelled") continue;
    r.status_since = new Date(Date.now() - 3600 * 1000).toISOString();
    left--;
  }
  return rows;
}
/* 눌린 순간 화면이 먼저 답한다 — 서버 왕복(수백 ms)과 다음 폴링을 기다리면
   사람은 버튼이 죽은 줄 안다. 카드와 문서 화면에 같은 id 가 동시에 떠 있을 수
   있으므로 전부 고친다. */
function paintWake(id){
  const going = wokePending(id);
  // 중단해 둔 카드의 손잡이(`data-restart`)도 같은 붓이 칠한다 — 하는 일도
  // 낱말도 같고, 다른 것은 그 위에 선 줄뿐이다 (REQ-20260829-024 라운드4).
  const q = CSS.escape(id);
  document.querySelectorAll(`[data-wake="${q}"],[data-restart="${q}"]`)
    .forEach(b => {
      b.disabled = going;
      b.textContent = going ? WAKE_GOING : WAKE_LABEL;
    });
}
/* 멈춘 요청 하나를 사람이 눌러 다시 굴린다 (REQ-20260828-041).

   **화면은 이유를 짓지 않는다.** 서버가 준 `message` 를 그대로 옮긴다 —
   `action` 으로 문구를 갈라 쓰면 같은 말이 서버와 화면 두 벌이 되고, 그때부터
   한 벌만 고쳐진다. 화면이 읽는 것은 `ok` 와 `message` 둘뿐이다.

   `ok=false` 는 **오류가 아니라 설명**이다. `capped`(한도 소진)·`busy`(이미
   붙어 있음)·`moving`(아직 멈춘 게 아님)은 전부 정상적인 답이라, 붉은 실패로
   그리지 않는다(창머리 잉크를 .stop 으로 올리지 않는다). */
async function wakeDoc(id){
  if (wokePending(id)) return;              // 연타 — 이미 도는 중이다
  wokeAt.set(id, Date.now());
  paintWake(id);
  let d = null, reached = false;
  try{
    const r = await fetch("/api/wake", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(withAs({id}))});  // actor는 서버 whoami 파생
    reached = true;
    d = await r.json();
  }catch(e){}
  if (!d || !d.message){
    wokeAt.delete(id); paintWake(id);
    // 서버가 답을 못 준 경우다 — 이유가 없으니 화면이 전송을 말한다(요청의
    // 사정을 지어내는 것과 다르다). 옛 서버에는 이 손잡이가 아직 없다.
    s9dlg({kind: "alert", cap: "연결", stop: true,
      title: reached ? "서버가 이어가기를 알지 못합니다"
                     : "서버에 닿지 못했습니다",
      desc: reached ? "s9 serve 를 다시 띄우면 이 손잡이가 붙습니다."
                    : "잠시 뒤 다시 시도해 주세요. 서버가 재기동 중일 수 있습니다.",
      ok: "닫기"});
    return;
  }
  if (!d.ok){ wokeAt.delete(id); paintWake(id); }
  wakeDlg(id, d);
  if (d.ok) refreshCatalog(true);
}
/* 깨우기의 답을 창으로 옮기는 자리는 **하나다** (REQ-20260829-030). 진단
   (`?dlg=wakewait`·`?dlg=wakespawn`)도 이 함수를 부른다 — 창을 따로 지으면 보고
   고친 것이 사람이 보는 창이 아니게 된다.

   **화면이 읽는 것은 `ok` 와 `message` 둘뿐이다.** 서버에 `action` 값이 하나
   늘어도(028 이 더한 `waiting`) 여기는 그대로다 — 값마다 문구를 갈라 쓰기
   시작하면 같은 말이 서버와 화면 두 벌이 되고, 그때부터 한 벌만 고쳐진다.

   `ok=false` 는 **오류가 아니라 설명이다**. `waiting`(누가 무엇을 잡고 있어
   차례를 기다린다)·`busy`·`capped`·`moving` 이 전부 정상적인 답이라 창머리
   잉크를 붉히지 않는다(stop:false). 대기는 고장이 아니라 차례다. */
function wakeDlg(id, d){
  /* 눈썹은 **사람이 누른 그 낱말**이다 (REQ-20260830-007). `깨움` 은 동사를
     명사로 굳힌 시스템의 말이라, 사용자가 방금 누른 낱말과 같은 것인지 한 박자
     맞춰 봐야 한다 — 누른 낱말이 그대로 돌아와야 답으로 읽힌다. */
  return s9dlg({kind: "alert", cap: d.ok ? WAKE_LABEL : "이어가지 않음",
    stop: false,
    doc: shortId(id), title: d.message, ok: "닫기"});
}
/* 눌린 순간 화면이 먼저 답한다 — 깨우기와 같은 규칙이다. */
function paintStop(id){
  const going = stopPending(id);
  document.querySelectorAll(`[data-stop="${CSS.escape(id)}"]`).forEach(b => {
    b.disabled = going;
    b.textContent = going ? STOP_GOING : STOP_LABEL;
  });
}
/* 도는 작업자를 사람이 눌러 세운다 (REQ-20260829-024).

   **먼저 묻는다.** 깨우기는 아무 일도 안 하던 것을 굴리는 일이라 되돌릴 것이
   없지만, 세우기는 지금 일하고 있는 프로세스를 끝낸다 — 되돌릴 수 없는 쪽에는
   한 걸음을 더 둔다(계정 창이 "멈추고 바꾸기"를 묻는 그 자리와 같은 규칙).
   무엇을 잃는지도 함께 적는다: 하던 일은 문서에 적힌 데까지만 남는다.

   답은 서버의 `message` 를 그대로 옮긴다 — `action` 으로 문구를 갈라 쓰면 같은
   말이 서버와 화면 두 벌이 되고, 그때부터 한 벌만 고쳐진다(깨우기가 세운
   규칙). 화면이 읽는 것은 `ok` 와 `message` 둘뿐이다. */
async function stopDoc(id){
  if (stopPending(id)) return;              // 연타 — 이미 세우는 중이다
  const go = await s9dlg({kind: "confirm", cap: STOP_LABEL, stop: false,
    doc: shortId(id),
    // 어느 요청인지는 창머리의 주소가 말한다 — 제목은 물음 하나만 한다.
    title: "진행 중인 자동 작업을 중단할까요?",
    desc: "지금 하던 일은 문서에 적힌 데까지만 남고, 그 뒤로 진행 중이던 것은"
      + " 사라집니다. 중단한 사실과 사유는 문서에 남습니다. 다시 맡기려면 같은"
      + " 자리에 생기는 「이어가기」를 누르면 됩니다.",
    ok: STOP_LABEL, cancel: "그대로 두기"});
  if (!go) return;
  stopAt.set(id, Date.now());
  paintStop(id);
  let d = null, reached = false;
  try{
    const r = await fetch("/api/stop", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(withAs({id}))});  // actor는 서버 whoami 파생
    reached = true;
    d = await r.json();
  }catch(e){}
  stopAt.delete(id); paintStop(id);
  if (!d || !d.message){
    // 옛 서버에는 이 손잡이가 아직 없다 — 깨우기가 세운 그 문장과 같은 자리다.
    s9dlg({kind: "alert", cap: "연결", stop: true,
      title: reached ? "서버가 중단하기를 알지 못합니다"
                     : "서버에 닿지 못했습니다",
      desc: reached ? "s9 serve 를 다시 띄우면 이 손잡이가 붙습니다."
                    : "잠시 뒤 다시 시도해 주세요. 서버가 재기동 중일 수 있습니다.",
      ok: "닫기"});
    return;
  }
  // 눈썹은 사람이 누른 그 낱말이다 — 깨우기 창이 세운 규칙과 같은 자리다.
  s9dlg({kind: "alert", cap: d.ok ? STOP_LABEL : "중단하지 않음", stop: false,
    doc: shortId(id), title: d.message, ok: "닫기"});
  if (d.ok) refreshCatalog(true);
}

/* 카드가 내주는 긴 글 한 덩어리 — 세 줄 + (잘렸으면) 그 자리에서 펴는 손잡이
   (REQ-20260829-009, 그 반려).

   확인 요청과 대기 사유는 같은 종류의 글이다: 사람이 손대기 전에 읽어야 하는
   문단이고, 둘 다 카드 폭에서는 다 못 읽는다. 한 함수로 지어야 한쪽만 고쳐져
   blocked 카드가 문장 벽으로 남는 일이 없다.

   본문을 캡션과 분리해 span 으로 싼다 — 클램프를 블록에 걸면 캡션이 세 줄 중
   한 줄을 먹는다. 손잡이는 클램프 박스 **밖**에 형제로 둔다: 안에 넣으면
   자기가 잘린다.

   손잡이는 **이 화면의 펼침 문법을 그대로 쓴다**(`data-expand` → `expanded`
   → `render()`). 그래서 15초 폴링이 보드를 다시 그려도 열어 둔 것이 접히지
   않고, 새 클릭 핸들러도 필요 없다 — 열 머리의 `+ N개 더 보기` 와 같은 길이다.
   `data-expand` 는 카드(문서 열기)보다 먼저 잡히므로 눌러도 Docs 로 새지 않는다.

   문구는 ux-writer 몫이라 이 두 상수에만 있다. */
const RVMORE_LABEL = "더 보기";
const RVLESS_LABEL = "접기";
/* 집어 둔 카드가 스스로를 부르는 이름 (REQ-20260829-011). 문구는 ux-writer
   몫이지만 폭 예산이 붙는다: id 줄에 남는 자리가 ~45px 이라 두어 자를 넘기면
   경과시각과 다시 자리를 다툰다. */
const PICKED_MARK = "대상";
function rvClamped(cap, text, key, open){
  return `<div class="rvpt clampy${open ? " open" : ""}">`
    + `<span class="rvcap">${esc(cap)}</span>`
    // 펼친 상자는 스크롤한다 — 키보드로도 닿아야 그 스크롤이 쓸모가 있다.
    + `<span class="rvtx"${open ? ` tabindex="0" role="group" aria-label="${esc(cap)} 전문"` : ""}>`
    + `${esc(text)}</span></div>`
    + `<button type="button" class="rvmore" data-expand="rv:${esc(key)}"`
    + ` aria-expanded="${open ? "true" : "false"}">`
    + `${open ? RVLESS_LABEL : RVMORE_LABEL}</button>`;
}

function cardHTML(r){
  const isReq = r.type === "request";
  // "무엇을 기다리는가" 한 줄 (REQ-20260826-009). blocked 전용이 아니다 —
  // open/in-progress 카드도 안 끝난 선행을 가질 수 있고, 사용자가 알고 싶었던
  // 것이 바로 그 경우다. 카드에선 선행 1건 제목 + 외 N건까지만; 전부와 이동
  // 경로는 문서 뷰가 맡는다.
  const bl = isReq ? liveBlockers(r) : [];
  /* 멈춤은 **서버가 재고 화면은 읽는다** (REQ-20260828-036). 여기서 다시 재면
     CLI(`s9 stalled`)와 화면이 다른 말을 하게 된다 — 이번 사고가 정확히 그것이다.
     그래서 이 화면 어디에도 "몇 분 지났나"를 판정하는 자리는 없고, 판정은
     stallState 한 곳만 지난다 (REQ-20260828-041 2차: 카드가 자기 몫의 조건을
     따로 가지면 문서 화면과 갈라진다 — 실제로 갈라져 있었다). */
  const st = stallState(r);
  // 펼쳐 둔 확인 요청/대기 사유는 다시 그려도 살아남는다 (REQ-20260829-009 반려) —
  // 이 화면이 이미 쓰는 기억(expanded)에 얹는다. 15초 폴링이 접지 않는다.
  const rvOpen = expanded.has("rv:" + r.id);
  const dep = bl.length
    ? `<div class="rvpt dep" title="${esc(bl.map(b => shortId(b.id) + " " + b.title).join(" · "))}">`
      + `<span class="rvcap">선행 대기</span>${esc(bl[0].title || shortId(bl[0].id))}`
      + (bl.length > 1 ? `<span class="depmore"> 외 ${bl.length - 1}건</span>` : "") + `</div>`
    : "";
  // 판정 카드: 배경 → 판단 요구 → 행동 (DOC-20260826-015). 요약 한 줄이 없으면
  // 제목만으로 무슨 건인지 떠오르지 않은 채 결론부터 읽게 된다 — 그래서 확인
  // 포인트 "위에" 요약을 놓는다. 이 블록(판정 카드)에만 붙인다.
  const acts = isReq && r.status === "review"
    ? `<div class="judge">${r.summary ? `<div class="rvpt what"><span class="rvcap">무엇을</span><span class="wtx">${esc(r.summary)}</span></div>` : ""}${r.review_point ? rvClamped("확인 요청", r.review_point, r.id, rvOpen) : ""}<div class="acts"><button class="deed" data-approve="${esc(r.id)}" title="승인하면 done 상태가 됩니다">${rvLabel("done")}</button><button class="deed" data-reject="${esc(r.id)}" title="반려하면 in-progress 상태로 돌아갑니다">${rvLabel("in-progress")}</button></div></div>`
    // 선행이 잡히면 구조화된 대기 줄이 이긴다 — 같은 사실을 두 줄로 말하지 않는다.
    // 관계가 없는 과거 문서만 note 본문의 대기 사유로 폴백 (DOC-20260826-001 규칙 7).
    : isReq && r.status === "blocked" && r.block_reason && !bl.length
    ? rvClamped("대기 사유", r.block_reason, r.id, rvOpen)
    : "";
  /* 멈춤 한 줄. **선행 대기가 있어도 손잡이를 뺏지 않는다** (REQ-20260828-041
     2차 반려로 뒤집음).

     전에는 선행 대기 줄이 이겼다 — 근거는 "같은 사실을 두 줄로 말하지 않는다"
     (DOC-20260826-001 규칙 7)였고, 문장에 대해서는 지금도 옳다. 그러나 그 관문이
     지운 것은 문장 하나가 아니라 **행동 하나**였다. 게다가 이 관문은 카드에만
     있었다: 같은 요청이 카드에선 못 깨우고 문서에선 깨워졌다 — 판정 단추가 세 번
     반려된 그 결함(REQ-20260828-007)과 같은 모양이다.

     사실로 봐도 둘은 다른 축이다. 선행 대기는 **관계**(무엇이 안 끝났나),
     멈춤은 **시계**(여기 아무도 안 적고 있다)다. 선행이 안 끝났는데 아무도 안
     붙어 있는 요청이야말로 사람이 깨워야 하는 것이다. 두 줄은 각각 한 줄이라
     문장 벽도 아니다. */
  // 글자와 손잡이는 stallHTML 한 곳에서 짓는다 — 문서 화면이 같은 함수를
  // 부르고, 안 멈춘 행에는 빈 문자열이 온다 (REQ-20260828-041).
  const stall = stallHTML(r);
  /* 점의 사다리. **멈춤이 초록보다 먼저 걸린다** (REQ-20260828-036).
     전에는 r.live 가 맨 위에 있어서, 문서가 한 시간째 안 움직인 요청도 그것을
     잡아 둔 세션이 살아 있기만 하면 초록으로 뛰었다 — 점이 재던 것은 "이
     요청의 진전"이 아니라 "이 요청을 잡고 있는 세션의 맥박"이었다. 그 상태로
     아래에 "멈춤" 줄만 붙이면 같은 카드가 점으로는 돈다고, 글자로는 멈췄다고
     말한다. 둘이 어긋나면 사람은 **둘 다** 안 믿는다.
     죽은 워커(dot-stopped)는 더 구체적인 근거를 가지므로 위에 그대로 둔다. */
  /* **정지 마크는 서버의 멈춤 판정이 받쳐 줄 때만 선다** (REQ-20260828-041 반려).

     사용자가 겪은 화면: 카드에 정지 마크가 붙어 "멈췄다"고 말하는데 깨울
     손잡이가 없다. 두 신호가 다른 시계를 봤기 때문이다 — 마크는 색인에 굳은
     작업자 판정(어제 22:36 의 기록이 오늘도 켜져 있었다)에서 오고, 손잡이는
     서버가 지금 다시 잰 `stalled_mins` 에서 온다.

     화면은 **분을 다시 재지 않는다**(REQ-20260828-036). 대신 순서를 세운다:
     작업자가 죽었다는 기록이 있어도 그 뒤로 **문서가 움직였으면**(서버가
     stalled_mins 를 안 준다) 그 기록은 낡은 것이니 마크를 세우지 않고 아래
     사다리로 내려간다. 이렇게 하면 "멈췄다고 그려 놓고 할 일은 안 주는 카드"가
     구조적으로 생길 수 없다 — 마크가 서는 조건이 손잡이가 서는 조건의
     부분집합이다.

     2차 반려에서 **부분집합을 같은 집합으로** 좁혔다. 종전에는 손잡이가 선
     카드 중 작업자 기록이 없는 것들이 `.livedot.off`(속 빈 회색 링)로 그려졌다 —
     그 마크는 "in-progress 인데 스트림이 조용하다"는 **모름**의 자리에도 쓰인다.
     그래서 점만 훑는 눈에는 "45분째 멈춰 깨울 수 있는 것"과 "그냥 조용한 것"이
     같은 마크였고, 열 머리의 `멈춤 N` 과도 세는 대상이 어긋나 보였다. 이제
     stallState 가 연 문을 지난 행은 전부 사각(정지)으로 그린다: 죽음이 기록된
     것은 채운 사각, 아니면 속 빈 사각. */
  const liveDot = r.status === "in-progress"
    ? (st && st.face === "dead"
         ? `<span class="livedot dot-stopped" title="처리 주체가 멈췄다 — ${esc(st.reason||"프로세스 종료")}"></span>`
       : st
         ? `<span class="livedot dot-stopped mild" title="${st.mins}분째 이 요청에 진전이 없다${esc(st.reason ? " — " + st.reason : "")}${r.live ? " (잡고 있는 세션은 활동 중이지만 다른 일을 하고 있다)" : ""}"></span>`
       /* 사람이 중단해 둔 것은 **모름이 아니다** (REQ-20260829-024 라운드4).
          이 갈래가 없으면 사다리 끝의 `.off`(속 빈 회색 원 = "in-progress 인데
          스트림이 조용함, 모름")로 떨어져, 카드가 왜 조용한지 알면서도 모른다고
          그린다 — 점이 서는 조건과 손잡이가 서는 조건을 다시 어긋내는 자리다
          (REQ-20260828-041 2차 반려가 지운 그 조합). 마크는 이미 있는 것을
          쓴다: 멈춤과 같은 속 빈 사각이되, 까닭은 툴팁이 갈라 말한다. */
       : r.stopped
         ? `<span class="livedot dot-stopped mild" title="사람이 이 요청의 자동 작업을 중단했습니다 — 카드의 「${WAKE_LABEL}」를 누르면 다시 이어집니다"></span>`
       : r.live
         ? `<span class="livedot on" title="이 요청을 실행 중인 세션이 활동 중 (${r.live_age}s 전 갱신 — last_req/active_reqs 등록)"></span>`
       : r.live_kind === "session"
         ? `<span class="livedot sess" title="담당 세션은 활동 중이나 이 요청의 직접 신호는 없음 (${r.live_age}s 전 세션 갱신)"></span>`
       : r.live_kind === "spawned"
         ? `<span class="livedot spawn" title="자동 작업이 막 시작됐습니다 (${r.live_age}초 전) — 이 요청을 집기까지 잠시 걸립니다"></span>`
         : `<span class="livedot off" title="in-progress지만 스트림 조용함 — 실제 동작 아닐 수 있음"></span>`)
    : "";
  return `<div class="card" ${isReq ? 'draggable="true"' : ""} tabindex="0" role="button" style="--sc:${SCOLOR[r.status]||"var(--muted)"}" data-doc="${esc(r.id)}" data-status="${esc(r.status)}">
    <button type="button" class="pickdoc" data-pick="${esc(r.id)}"
      aria-label="${esc(shortId(r.id))} 에 이어 말하기">이어 말하기</button>
    <div class="id">${liveDot}<span class="idn">${esc(shortId(r.id))}</span><span class="pkst" title="이어 말할 대상 — 카드에 얹어 손잡이를 다시 누르면 놓는다">${PICKED_MARK}</span></div>
    <div class="t">${esc(r.title)}</div>
    <div class="m">
      <span class="badge" style="--ah:${tagHue(r.user||"?")}"><i class="av">${esc((r.user||"?").slice(0,1).toUpperCase())}</i>${esc(r.user)}</span>
      ${prioHTML(r)}
      ${r.size ? `<span class="size">${esc(r.size)}</span>` : ""}
      ${r.tdd ? `<span class="tdd${r.tdd.passed===r.tdd.total?" full":""}" title="TDD 시나리오 ${r.tdd.passed}/${r.tdd.total} 통과">TDD ${r.tdd.passed}/${r.tdd.total}</span>` : ""}
      ${(r.tags||[]).filter(t=>!SYS_TAGS.has(t)).slice(0,2).map(t=>`<span class="tag" style="--th:${tagHue(t)}">#${esc(t)}</span>`).join("")}
    </div>${acts}${dep}${stall}
    ${r.status_since ? `<span class="elapsed" data-since="${esc(r.status_since)}" title="현재 상태(${esc(r.status)}) 시작 이후 경과">${fmtElapsed(r.status_since)}</span>` : ""}</div>`;
}

// 반려: 사유 필수. Board·문서 뷰어 공용 (REQ-20260827-071 로 제품 대화상자 사용).
// 빈 값에 두 번째 창을 띄우던 흐름은 없앴다 — 그건 벌주는 흐름이고, 한 창 안에서
// 확인이 안 눌리는 것으로 족하다.
/* 판정 창의 머리(주소)와 제목을 **한 곳에서** 짓는다 (REQ-20260828-007).
   반려·승인·전이·취소가 각자 문장을 지어 쓰면 언젠가 하나만 제목을 잃는다 —
   실제로 넷 다 id 만 적고 있었다.

   제목은 카탈로그에서 찾아 낫표로 감싼다(집기 줄이 이미 쓰는 어휘 — 제목이
   동사로 끝나면 뒤에 붙는 조사와 엉켜 한 문장으로 읽히기 때문이다). 아주 긴
   제목은 60자에서 자른다: 뒤따르는 동사("반려합니다")가 잘려 나가면 무엇을
   하려는 창인지가 사라진다. 이 저장소의 제목 규약은 20자 이내라 실제로 잘릴
   일은 드물고, 60자면 창 폭(432px)에서 세 줄이다. */
/* 조사는 **계산한다** (REQ-20260828-007 4차). `을(를)` 은 이 화면에 남은 유일한
   서식 편지투다 — 제목은 동적이지만 받침 유무는 마지막 글자 하나로 정해진다.
   한글로 끝나지 않으면(문서 id 폴백·로마자 제목) 지금처럼 물러선다: 읽는 법이
   글자에 없는 것을 화면이 지어내는 것보다, 두 개를 다 적어 주는 편이 정직하다. */
function josa(word, withT, withoutT){
  const last = String(word || "").trim().slice(-1);
  const c = last ? last.charCodeAt(0) : 0;
  if (c < 0xAC00 || c > 0xD7A3) return `${withT}(${withoutT})`;
  return (c - 0xAC00) % 28 ? withT : withoutT;
}
function dlgFor(id, tail){
  const r = catFind(id);
  let t = String((r && r.title) || "").trim();
  const full = t;
  if (t.length > 60) t = t.slice(0, 60) + "…";
  const name = t ? `「${t}」` : shortId(id);
  // 조사가 무는 것은 낫표가 아니라 그 안의 마지막 글자다. 잘린 제목에서는
  // 말줄임표 앞의 글자로 정한다 — 사람이 읽는 소리를 따른다.
  return {doc: shortId(id),
          titleHtml: `${esc(name)}${josa(full, "을", "를")} ${tail}`};
}
/* 상태 이름을 문장 속에 세운다 (REQ-20260828-007 반려).

   사용자: "다른 상태에서는 open, in-progress, done인데 리뷰 단계에서만 …
   한글로 승인/반려 라고 표시된다. 용어를 통일할 필요가 있다."

   통일은 **번역**이 아니다. `done` 은 화면에만 있는 낱말이 아니라 문서 앞머리와
   CLI 출력과 커밋 메시지에 같은 글자로 박혀 있는 **이름**이고, 이름은 번역하지
   않는다 — 화면만 한글로 바꾸면 화면에서 본 말과 문서에서 읽는 말이 달라져
   "이게 그거인가"를 매번 이어 붙여야 한다. 대신 **이름은 이름처럼, 행위는
   행위처럼** 보이게 한다: 상태는 mono 식별자로, 승인·반려는 문장 속 동사로.

   그리고 조사를 피한다 — "done 으로"·"in-progress 로" 는 이름마다 갈리고 어느
   쪽으로 통일해도 절반은 틀린다. "…상태로" 를 끼우면 어느 이름에도 문장이 선다. */
const stName = to => `<span class="dlgst">${esc(to)}</span>`;
/* 판정 버튼의 글자는 **한 곳에서** 짓는다 (REQ-20260828-007 4차).

   보드 판정 카드와 문서 화면이 각자 글자를 갖고 있어서, 3차까지 한쪽만
   고쳐지는 일이 되풀이됐다. 두 화면이 같은 함수를 부르면 갈라질 수 없다.

   글리프(✓/↺)는 뺐다 — 실측: `✓ 승인 done` 은 보드 카드 폭(215px)에서 두
   줄로 감긴다. 글리프는 두 버튼을 가르려고 있던 것인데 이제 done/in-progress
   가 그보다 강하게 가른다. 축약(`in-prog`)은 쓰지 않는다 — 어디에도 없는
   글자를 만드는 순간 "화면과 문서와 CLI 가 같은 이름" 이라는 전제가 무너진다.

   키는 TRANSITIONS["review"] 의 부분집합이어야 한다 (계약: test_judge_dialog). */
const RVDEED = {done: "승인", "in-progress": "반려"};
/* 옮기기 버튼과 판정 버튼은 **같은 틀**이다 (REQ-20260828-007 5차):
   앞 칸이 행위, 뒤 칸이 도착지의 이름. 행위 칸에 기호가 서면 그냥 이동이고
   낱말이 서면 판정이다. 두 종류가 각자 함수를 가지면 5차에서 그랬듯 이름의
   생김새가 갈린다 — 한 함수가 짓게 두면 갈릴 자리가 없다. */
const actLabel = (to, judging) =>
  `${judging && RVDEED[to] ? RVDEED[to] : "→"}<span class="stn">${esc(to)}</span>`;
const rvLabel = to => RVDEED[to] ? actLabel(to, true) : "";
/* 판정은 **한 곳에서** 한다 (REQ-20260828-007 3차 반려).

   사용자: "보드 화면에서 승인을 할 때는 '승인하기'이고 문서에서 승인을 할 때에는
   '상태옮기기' 라고 나온다. 판정 이 단계만 보거나, 국소적으로 판단하지말고,
   전체적인 디자인, 흐름, 맥락을 다 챙기도록 해."

   원인은 문구가 아니라 **길이 둘이었다는 것**이다. 보드 카드는 `data-approve` 로
   승인 창을 열고, 문서 화면의 같은 `✓ 승인` 버튼은 `data-trans` 로 일반 상태
   옮기기 창을 열었다. 반려만 두 길이 한 함수를 쓰고 있었고 승인은 갈라져 있었다.

   이 저장소가 반복해 배운 것과 같다: **판정이 두 벌이면 한 벌만 고쳐진다.**

   행동의 이름은 **어디서 왔는가**로 정해진다. review 에서 나가는 것만 판정이다 —
   `in-progress → done` 은 일을 끝낸 것이지 승인이 아니다. */
async function judgeAct(id, to, from){
  const judging = from === "review";
  if (judging && to === "done"){
    const memo = await s9dlg({kind:"prompt", cap:"판정", attach: true,
      ...dlgFor(id, `승인해 ${stName("done")} 상태로 넘깁니다`),
      desc:"메모는 History 에 남습니다. 비워 두어도 승인됩니다. " + DLG_ATTACH_HINT,
      ok:"승인하기", cancel:"그만두기"});
    if (memo === null) return;                 // 취소
    // 화면은 사람이 쓴 **원문만** 보낸다 (REQ-20260828-007 4차). 앞서는 여기서
    // 접두어를 이어 붙였다 — 의미를 문자열에 실어 보내면 서버가 그 한글 두
    // 글자를 파싱하게 되고,
    // 화면 낱말 하나를 고치는 순간 승인 메모 인계가 소리 없이 죽는다.
    // 접두어는 (from,to) 를 아는 do_transition 이 짓는다.
    postStatus(id, "done", memo.text, memo.atts);
    return;
  }
  if (judging && to === "in-progress"){
    const why = await s9dlg({kind:"prompt", cap:"판정", attach: true,
      ...dlgFor(id, `반려해 ${stName("in-progress")} 상태로 돌려보냅니다`),
      desc:"사유는 History 에 그대로 남습니다. 무엇이 부족한지 한 줄이면 됩니다. "
         + DLG_ATTACH_HINT,
      required:true, ok:"반려하기", cancel:"그만두기"});
    if (why === null) return;                  // 취소
    postStatus(id, "in-progress", why.text, why.atts);   // 접두어는 서버가 짓는다
    return;
  }
  // 판정이 아닌 이동 — 사람이 상태를 직접 옮기는 자리다.
  /* 창 머리도 어디서 왔는가로 정해진다 (REQ-20260828-007 4차). 넷 다 `판정`
     이라 `in-progress → done` 창이 스스로를 판정이라 부르면서 버튼은 `상태
     옮기기` 라고 말하고 있었다. review 에서 나가는 것만 판정이다. */
  if (to === "cancelled" && !await s9dlg({kind:"confirm", cap:"상태 옮기기",
        ...dlgFor(id, `${stName("cancelled")} 상태로 옮깁니다`),
        desc:"취소한 요청은 보드에서 내려갑니다. 되돌리려면 다시 옮기면 됩니다.",
        ok:"취소하기", cancel:"그만두기"})) return;
  const note = await s9dlg({kind:"prompt", cap:"상태 옮기기", attach: true,
    ...dlgFor(id, `${stName(to)} 상태로 옮깁니다`),
    desc:"메모는 History 에 남습니다. 비워 두어도 됩니다. " + DLG_ATTACH_HINT,
    ok:"상태 옮기기", cancel:"그만두기"});
  if (note === null) return;
  postStatus(id, to, note.text, note.atts);
}
const rejectWithReason = id => judgeAct(id, "in-progress", "review");

async function postStatus(id, to, note, atts){
  /* **붙이기와 전이가 한 번에 간다** (REQ-20260829-015 반려 재작업).

     1차에서는 화면이 두 번 두드렸다 — `/api/note` 로 사유+파일을 붙이고
     `/api/status` 로 옮겼다. 그래서 순서("파일이 먼저")와 실패 처리("못 붙이면
     옮기지 않는다")를 화면이 손으로 엮어야 했고, 앞이 되고 뒤가 안 되면
     근거만 남고 상태는 안 옮겨진 어중간한 자리가 생겼다. 그 둘을 서버가
     한 몸으로 가져갔다(`/api/status` 가 `atts` 를 받는다) — 이제 화면은
     **한 번 보내고 결과만 읽는다.**

     표기(`[Image:]`·`[File:]`)도 더 이상 화면이 짓지 않는다. 그림이냐 아니냐는
     파일의 성질이지 화면의 취향이 아니고, 화면 둘이 각자 확장자 표를 들면
     영상에 `[Image:]` 가 붙어 문서에 깨진 칸이 남는다(서버 `asset_mark`).

     라벨은 `response` 다. 앞서는 `/api/note` 가 `ask` 로 박아 두어 **반려 근거가
     문서에 질문으로 적혔다** — 나중에 읽는 사람이 답해야 할 질문과 판정의
     근거를 구별할 수 없었다. */
  try{
    const r = await fetch("/api/status", {method: "POST",
      headers: {"Content-Type": "application/json"},
      // actor 는 서버 whoami 파생 — 화면이 실어 보내지 않는다
      body: JSON.stringify(withAs({id, to, note, atts: atts || [],
                                   label: "response"}))});
    const d = await r.json();
    if (!d.ok){
      /* `거부` 는 사람이 판정에서 거절했다는 말로 읽힌다 — 실제로는 서버가
         받지 못한 것이다 (REQ-20260828-007 4차).

         파일을 함께 보냈다면 **모르는 것을 아는 척 말하지 않는다.** 붙이기가
         먼저이므로 갈래가 둘이다: 파일에서 막혔으면 아무것도 안 남았고, 전이에서
         막혔으면(흔한 쪽이다 — "review 에서 done 으로는 갈 수 없다") 파일은
         이미 문서에 있다. 어느 쪽이든 사람이 할 일은 같으니 그 하나를 말한다. */
      s9dlg({kind:"alert", cap:"실패", title:"상태를 바꾸지 못했습니다",
        desc: String(d.error || "")
          + (atts && atts.length
             ? " 붙인 파일이 문서에 남았는지는 문서를 열어 확인해 주세요." : ""),
        ok:"닫기"});
      return;
    }
    refreshCatalog(true);
  }catch(e){
    s9dlg({kind:"alert", cap:"연결", title:"서버에 닿지 못했습니다",
      desc:"잠시 뒤 다시 시도해 주세요. 서버가 재기동 중일 수 있습니다.", ok:"닫기"});
  }
}

// 빈 상태는 안내가 아니라 다음 행동을 주는 자리다 (s9-design 완성도 기준 3)
// 다섯 컬럼이 똑같이 "비어 있음"이면 어느 칸이 빈 것인지 눈이 다시 위를 훑어야
// 한다. 각 칸이 비었다는 사실의 뜻을 한 줄로 말한다 (REQ-20260825-081).
const EMPTY_COL = {
  open: '<div class="colempty">착수를 기다리는 요청 없음</div>',
  "in-progress": '<div class="colempty">진행 중인 요청 없음</div>',
  blocked: '<div class="colempty">막혀 있는 요청 없음</div>',
  review: '<div class="colempty">판정을 기다리는 요청 없음</div>',
  done: '<div class="colempty">완료된 요청 없음</div>',
};

// 끝난 컬럼이 접혀 있을 때 하는 말 — "몇 개 더"가 아니라 **왜 안 보이는지**를 말한다
// (REQ-20260827-057). 숫자만 있는 버튼은 목록이 잘렸다는 뜻으로 읽히지만, 여기서
// 가려진 것은 잘린 것이 아니라 하루가 지난 것이다.
const TERM_WORD = {done: "완료", cancelled: "취소"};

/* 이 열이 지금 담고 있는 것 — 끝난 열은 하루가 지난 것을 내린다
   (REQ-20260827-057). 판이 "이 열을 세울까"를 묻는 자리(colStanding)와 열이
   "무엇을 그릴까"를 묻는 자리(colHTML)가 같은 답을 봐야 한다: 두 벌이면 열이
   섰는데 안이 비거나, 안에 있는데 열이 안 서는 조합이 생긴다. */
const colLive = (key, grp) => TERMINAL.has(key)
  ? grp.filter(r => termAt(r) >= Date.now() - TERMINAL_WINDOW_MS) : grp;
/* 판에서 한 칸을 받을 열인가 (REQ-20260829-031).

   사용자: "이걸 보여줄 필요가 있나?" — 취소 열이 `하루 안에 취소된 요청 없음`
   한 줄만 담은 채 한 칸을 통째로 쓰고 있었다.

   이 파일이 이미 적어 둔 규칙이 있다(아래 colHTML): "0건이면 아예 안 나온다 —
   매번 참인 문장은 곧 안 읽히고, 없는 것을 굳이 말하는 자리가 늘면 있는 것이
   묻힌다." 취소 열이 그 규칙의 예외로 남아 있었다.

   **다른 열과 가르는 근거는 '비어 있음이 정보인가'다.** open·in-progress·
   review·blocked 는 비어 있음 자체가 사람이 확인하러 오는 값이다("판정 대기
   0"). done 은 "오늘 무엇을 끝냈나"라 매일 보는 값이라 비어도 선다. 취소는
   예외적 사건이라 **비어 있는 것이 기본값**이고, 기본값을 매일 한 칸으로
   말할 이유가 없다.

   감추는 것이지 잃는 것이 아니다: 취소된 것이 생긴 날에는 그대로 서고(그 열의
   접기·개수도 그대로다), 하루가 지나 내려간 것은 done 과 똑같이 Docs 에 있다.
   딸려 오는 값 하나 — 열이 없는 날에는 **끌어다 취소하는 자리도 없다.** 취소는
   문서 화면의 `→ cancelled` 로 늘 갈 수 있고 되돌릴 수도 있어서, 매일 한 칸을
   내주고 지킬 만큼의 지름길은 아니라고 봤다. */
const COL_ALWAYS = ["open", "in-progress", "review", "done"];
const colStanding = (key, grp) => key === "cancelled"
  ? colLive(key, grp).length > 0
  : (grp.length > 0 || COL_ALWAYS.includes(key));

function colHTML(key, label, color, grp){
  const term = TERMINAL.has(key);
  const word = TERM_WORD[key] || "완료";
  // ① 내린다 — 하루가 지난 끝난 요청은 이 열에 없다. 접은 안쪽에도 없다.
  const live = colLive(key, grp);
  const cut = grp.length - live.length;
  // ② 남은 것에 원래 접기를 그대로 — 끝난 열 3건, 나머지 7건.
  const limit = term ? COL_LIMIT_TERMINAL : COL_LIMIT;
  const open = expanded.has("col:"+key);
  const shown = open ? live : live.slice(0, limit);
  const hidden = live.length - shown.length;
  // 하루 안에 끝난 것이 없는데 "완료된 요청 없음"이라고만 하면, 322건이 어디
  // 갔는지 답하지 않는 셈이다 — 어느 하루를 말하는지 밝힌다.
  const body = live.length ? shown.map(cardHTML).join("")
    : (cut ? `<div class="colempty">하루 안에 ${word}된 요청 없음</div>`
           : (EMPTY_COL[key] || ""));
  // 내린 것을 설명하는 문구는 두지 않는다 (2026-08-27 사용자 지시 "이런건 문구로
  // 남기지마라"). 하루가 지난 것이 안 보이는 건 **이 화면이 늘 도는 규칙**이지
  // 사고가 아니다 — 규칙을 매번 변명하는 줄은 자리만 먹고 곧 안 읽힌다.
  // (사용자가 건 조건 때문에 안 보이는 경우는 다르다. 그건 원인을 짚어 줘야
  //  풀 수 있어서 Graph 빈 화면이 이름으로 말한다 — REQ-20260827-054.)
  /* 열 머리가 **멈춘 건수**를 함께 센다 (REQ-20260828-036). 사용자가 물은 것은
     "진행 중 몇 건인가"가 아니라 "그중 진짜 도는 게 몇 건인가"였다. 그 답은
     세는 대상 바로 위, 이미 총량을 말하는 그 줄에 있어야 한다 — 새 띠를 얹으면
     헤더의 경고 띠와 층위가 겹쳐 둘 다 안 읽힌다.
     0건이면 아예 안 나온다: "멈춤 0"은 매번 참인 문장이라 곧 안 읽히고, 없는
     것을 굳이 말하는 자리가 늘면 있는 것이 묻힌다. */
  // 세는 술어도 카드가 쓰는 그 하나다 (REQ-20260828-041 2차) — 배지가 세는 수와
  // 손잡이가 선 카드 수가 어긋나면, 사용자는 배지를 세다 말고 카드를 센다.
  const stalls = key === "in-progress"
    ? live.filter(r => stallState(r)).length : 0;
  // 컬럼은 이제 전부 request 상태다 (REQ-20260825-084로 etc 컬럼 제거) — 드롭 대상 표시 상시
  return `<div class="col" style="--sc:${color}" data-colstatus="${key}"><h2><span class="cdot"></span>${label}<span class="n">${live.length}</span>${stalls ? `<span class="stn" title="이 열의 ${live.length}건 중 ${stalls}건은 문서가 오래 안 움직였다">멈춤 ${stalls}</span>` : ""}</h2>
    <div class="cards">${body}
    ${hidden>0 ? `<button class="more" data-expand="col:${key}">${hidden}개 더 보기</button>`
      : (open && live.length>limit ? `<button class="more" data-expand="col:${key}">접기</button>` : "")}
    </div></div>`;
}

// Board는 요청의 상태 흐름만 다룬다 — knowledge/session 컬럼 제거 (REQ-20260825-084).
// 그 컬럼이 하던 일("지식·세션 문서에 도달한다")은 Docs 목록 최상단의 타입바가 받는다.
function renderBoard(rows){
  const reqs = rows.filter(r => r.type === "request");
  /* **상단 상태 띠를 내렸다** (REQ-20260827-070 2차 — 사용자 물음에 대한 답).

     사용자: "컬럼 헤더랑 동일한 기능인데 굳이 보여줘야 하는게 맞나?"
     아니다. 세어 보고 눌러 보고 내린 결론이다.

     ① 1차에서 띠의 셈을 열에 맞춘 뒤로 **두 줄이 같은 집합을 같은 낱말로 두 번
        센다.** 숫자가 다르면 고장으로 읽히고, 같으면 자리만 먹는다.
     ② 분포를 한눈에 보는 일도 열 머리가 그대로 한다 — 여섯 열 머리는 이미 같은
        높이에 가로로 늘어서 있어, 띠는 그 줄을 40px 위에서 되풀이하고 있었다.
        게다가 띠는 0건인 상태의 칩을 아예 뺐다 — 열은 비어도 자리를 지키는데.
        같은 화면이 같은 질문에 두 가지로 답하고 있었던 셈이다.
     ③ 띠의 필터는 **보드에서 할 일이 없었다.** 눌러도 그 열만 남는 것이 아니라
        나머지 네 열이 "…없음" 으로 비어, 걸기 전보다 나쁜 화면이 된다. 상태로
        가르는 일은 열이 이미 한다 — 칸반에 상태 필터를 겹쳐 놓은 셈이었다.
        게다가 걸린 줄은 작은 밑줄 하나로만 표시돼 빠져나오는 길이 흐렸다.
     ④ 열을 깊이 보는 일은 `+ N개 더 보기` 가 이미 맡고 있다.

     그래서 열 머리 하나만 남긴다 — **한 숫자는 한 곳에만.** CSS(.stats/.stat)는
     지우지 않고 둔다: 열 스킨 블록에 흩어져 있어 되돌리는 값이 크고, 이 판단이
     뒤집히면 이 자리 한 줄로 돌아온다. */
  let html = "";
  // 병목 한 줄 (REQ-20260826-009 2차): 카드마다 "선행 대기" 줄은 이미 있다 —
  // 카드가 말할 수 없는 것, 즉 "한 선행이 여러 건을 붙잡고 있다"일 때만 띄운다.
  // 그 외에는 같은 사실을 두 번 말하는 것이라 보드를 그대로 둔다.
  const dbk = depBoard(reqs);
  if (dbk.top && dbk.top[1] > 1){
    const b = catFind(dbk.top[0]);
    if (b) html += `<div class="bneck"><span class="bcap">병목</span> `
      + `${dlink(b.id, esc(shortId(b.id)))} `
      + `<b>${esc(b.title)}</b> 이(가) ${dbk.top[1]}건을 붙잡고 있다 · `
      + `전체 ${dbk.groups.length}건이 선행을 기다린다`
      + `<button class="bgo" data-goto="graph">선행 대기 현황 →</button></div>`;
  }
  html += `<div class="board">`;
  for (const st of STATUSES){
    let grp = reqs.filter(r => r.status === st);
    // 끝난 컬럼은 우선순위로 세우지 않는다 (REQ-20260827-016).
    // 우선순위는 "다음에 무엇을 할 것인가"에 답하는 축이다 — 이미 끝난 일에는
    // 그 질문이 없다. done 286건이 가중치 계단으로 묶여 있으면 방금 끝난 것을
    // 찾으려고 계단마다 훑어야 한다.
    //
    // 세우는 기준은 **카드가 실제로 보여주는 시각**이다 — `status_since`,
    // 즉 그 상태가 된 때. `updated` 로 세웠다가 반려를 받았다(1차): 그 필드는
    // 노트·링크·인덱스 작업으로 계속 밀려서, 21시간 전에 끝난 문서가 "방금
    // 갱신"으로 맨 위에 왔다. 화면의 시계와 정렬의 자가 다르면 사용자에게는
    // 정렬이 안 된 것으로 보인다 — 그리고 그 말이 맞다.
    if (TERMINAL.has(st))
      grp = [...grp].sort((a, b) => (b.status_since || b.updated || b.created || "")
        .localeCompare(a.status_since || a.updated || a.created || ""));
    /* in-progress 열은 **오래 멈춘 순 → 도는 중 순** (REQ-20260828-036).
       이 열이 답하는 질문은 "무엇부터 손대야 하나"이고, 그 답은 가장 오래
       조용한 것이다. 기본 정렬(우선순위 → 최근 갱신)은 그 반대로 세운다 —
       방금 움직인 것이 위로 오니, 손 뗀 지 한 시간 된 요청이 접힌 아래로
       내려가 사용자가 스크롤해야 찾는 자리에 있었다.
       멈추지 않은 것들끼리는 기존 차례를 그대로 둔다(안정 정렬). */
    if (st === "in-progress")
      grp = [...grp].sort((a, b) => {
        const x = stallState(a), y = stallState(b);
        return (y ? y.mins : -1) - (x ? x.mins : -1);
      });
    // 주요 컬럼은 비어도 자리를 지킨다 — 드롭 대상이자 상태 안내 자리(ux-craft)
    // 필터가 사라졌으니 "걸러서 빈 것"과 "원래 빈 것"을 가를 일도 없다
    // (REQ-20260827-070 2차) — 주요 네 열은 비어도 자리를 지킨다.
    // 취소 열만 잣대가 다르다 — 판정은 colStanding 한 곳에 있다 (REQ-20260829-031).
    if (!colStanding(st, grp)) continue;
    html += colHTML(st, st, SCOLOR[st], grp);
  }
  html += `</div>`;
  $("#view").innerHTML = html;
  markPicked();   // 집어 둔 카드 표시 복원 (REQ-20260827-064)
  // 세 줄에서 잘린 카드에만 "전문 보기"를 연다 — 잘림은 재서 안다 (REQ-20260829-009).
  // 그림이 붙은 다음 프레임에 잰다: innerHTML 직후에는 아직 레이아웃이 없다.
  requestAnimationFrame(() => markClamped($("#view")));
  elapsedTimer = setInterval(tickElapsed, 1000);  // 카드 경과시간 실시간 갱신
}

/* 잘렸는지는 **재서** 안다 (REQ-20260829-009). 글자 수로 짐작하면 스킨마다
   틀린다 — 열 폭(210~252px)·글꼴·줄간·밀도가 열 벌 넘는 스킨에서 다 달라서,
   같은 문장이 한 스킨에선 세 줄, 다른 스킨에선 네 줄이다. 짐작이 빗나가면
   둘 중 하나가 된다: 안 잘린 카드에 손잡이가 붙는 소음이거나, 잘린 채로
   아무 말도 없는 화면이거나. 후자가 이 요청의 원인이다.

   재는 자리가 둘인 이유: 베이스는 본문 span(.rvtx)에 클램프를 걸고, calm 은
   캡션을 인라인으로 눕히므로 블록(.rvpt) 전체에 건다. 실제로 넘친 쪽을 잡는다.
   1px 여유는 소수점 줄 높이의 반올림 때문이다 — 없으면 안 잘린 글도 잘렸다고
   말한다. 계약: tests/test_review_clamp.py */
function markClamped(root){
  (root || document).querySelectorAll(".rvpt.clampy").forEach(el => {
    const tx = el.querySelector(".rvtx");
    const box = tx && tx.clientHeight ? tx : el;
    /* 문턱은 px 상수가 아니라 **줄 높이**다. 클램프가 자르면 최소 한 줄이
       남으므로 넘침은 늘 한 줄 이상이다 — 그보다 작은 차이는 레이아웃
       반올림이지 잘림이 아니다. 상수 1px 로 쟀다가 실제로 틀렸다: 넓은
       창에서 딱 세 줄로 끝난 대기 사유가(말줄임표도 없이) 잘렸다고
       보고돼 손잡이가 붙었다. 반 줄을 문턱으로 둔다. */
    const lh = parseFloat(getComputedStyle(box).lineHeight) || 16;
    el.classList.toggle("iscut", box.scrollHeight - box.clientHeight > lh * 0.5);
  });
}
// 열 폭이 바뀌면 몇 줄인지도 바뀐다 — 창을 줄였는데 손잡이가 그대로면 거짓말이다.
let clampResizeT;
function markClampedSoon(){ clearTimeout(clampResizeT); clampResizeT = setTimeout(markClamped, 60); }
window.addEventListener("resize", markClampedSoon);

/* ---------------- docs ---------------- */
function hl(text, q){
  let out = esc(text);
  for (const t of q.split(/\s+/).filter(Boolean)){
    const re = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    out = out.replace(re, m => `<b>${m}</b>`);
  }
  return out;
}

/* 못 박은 줄의 머리글과 그 손잡이의 낱말 (REQ-20260829-012). 문구는 ux-writer
   몫이라 한 곳에만 둔다 — 다만 머리글은 **타입 이름처럼 보이면 안 된다**
   (request·knowledge 옆에 또 하나의 덩어리로 읽힌다). */
