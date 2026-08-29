/* events.js — 드래그 전이 · 전역 이벤트 배선 · boot() */
"use strict";
/* ---------------- drag & drop 상태 전이 ---------------- */
document.addEventListener("dragstart", e => {
  const c = e.target.closest('.card[draggable="true"]');
  if (!c) return;
  e.dataTransfer.setData("text/plain",
    JSON.stringify({id: c.dataset.doc, from: c.dataset.status}));
  e.dataTransfer.effectAllowed = "move";
  window.__dragFrom = c.dataset.status;
});
document.addEventListener("dragend", () => {
  window.__dragFrom = null;
  document.querySelectorAll(".col.dropok").forEach(el => el.classList.remove("dropok"));
});
document.addEventListener("dragover", e => {
  const col = e.target.closest(".col[data-colstatus]");
  document.querySelectorAll(".col.dropok").forEach(el => el.classList.remove("dropok"));
  if (!col || !window.__dragFrom) return;
  if ((TRANS[window.__dragFrom] || []).includes(col.dataset.colstatus)){
    e.preventDefault();  // 허용 전이 컬럼만 drop 가능
    col.classList.add("dropok");
  }
});
document.addEventListener("drop", e => {
  const col = e.target.closest(".col[data-colstatus]");
  if (!col) return;
  e.preventDefault();
  try{
    const d = JSON.parse(e.dataTransfer.getData("text/plain"));
    const to = col.dataset.colstatus;
    if (!d.id || d.from === to || !(TRANS[d.from] || []).includes(to)) return;
    /* 끌어 옮기는 것도 **같은 판정**이다 (REQ-20260828-007 3차 반려 — 전체 흐름).
       review 카드를 끌어 놓으면 여기만 창 없이 "drag 이동" 이라고 적혔다. 그래서
       ① 반려에 사유가 필수라는 규칙이 이 길로만 비껴갔고 ② 같은 행동이 History
       에 세 가지 말로 남았다(승인 / 반려 / drag 이동). 판정으로 나가는 이동은
       버튼과 같은 창을 띄우고, 그 밖의 이동만 예전처럼 바로 옮긴다. */
    if (d.from === "review") judgeAct(d.id, to, d.from);
    else postStatus(d.id, to, "drag 이동");
  }catch(err){}
});

/* ---------------- events ---------------- */
document.addEventListener("click", e => {
  /* 코드 블록 복사 (REQ-20260828-023). 터미널·스트림은 통째로 다시 그려지므로
     리스너는 손잡이마다가 아니라 여기 위임 하나로 둔다 — 붙이면 재렌더마다
     죽는다. */
  const cbc = e.target.closest(".ccbcp");
  if (cbc){ e.preventDefault(); ccBlockCopy(cbc); return; }
  /* 구간 ↔ 메모 오가기 (REQ-20260827-072 반려). 본문의 ⌖ 는 그 구간에 달린
     메모로, 메모의 "⌖ 그 구간" 은 본문의 그 자리로 데려간다. 위임을 여기서
     하는 이유는 anchorMark 주석에 적어 뒀다 — 리스너가 쌓이지 않게. */
  const anj = e.target.closest("[data-anjump],[data-anback]");
  if (anj){
    e.preventDefault();
    const md = anj.closest(".md");
    const to = !md ? null : anj.dataset.anjump
      ? md.querySelector(`blockquote.anchorq[data-anq="${cssq(anj.dataset.anjump)}"]`)
      : md.querySelector(`.anchored[data-anq="${cssq(anj.dataset.anback)}"]`);
    anchorGo(to);
    return;
  }
  // 본문 안에서 탭으로 건너뛰는 링크 — 헤더 탭 버튼의 active 표시를 빼앗지 않도록
  // data-tab 이 아니라 data-goto 로 둔다(그 핸들러는 클릭된 요소를 active로 만든다).
  // data-goto 는 두 뜻으로 쓰인다: 탭 이름("graph") 과 문서 본문의 상태 전이
  // ("REQ-…|to|from"). 여기서 전이까지 삼키면 본문의 승인/반려 버튼이 조용히
  // 죽는다 — 아래 전이 핸들러가 **같은 리스너 안**이라 return 이 곧 무반응이다
  // (REQ-20260826-025: 보드에서는 되는데 본문에서는 안 되던 결함).
  const go = e.target.closest("[data-goto]");
  if (go && !go.dataset.goto.includes("|")){
    const hdr = document.querySelector(
      `header [data-tab="${go.dataset.goto}"]`);
    if (hdr) hdr.click();
    return;
  }
  const tabBtn = e.target.closest("[data-tab]");
  if (tabBtn){
    tab = tabBtn.dataset.tab;
    if (tab === "audit") auditCache = null;
    tabSync();
    pushRoute();
    render();
    refreshCatalog(true);
    // 탭 전환은 visibilitychange 를 일으키지 않는다 — 터미널로 돌아온 순간
    // 스트립을 서버 목록으로 맞춘다 (REQ-20260826-016).
    if (tab === "terminal" && TERM && TERM.agTick) TERM.agTick();
    return;
  }
  const gt2 = e.target.closest("[data-gtype]");
  if (gt2){
    const t = gt2.dataset.gtype;
    gtypes.has(t) ? gtypes.delete(t) : gtypes.add(t);
    if (!gtypes.size) gtypes.add("request");  // 전부 끄면 무의미 — 최소 1종 유지
    // 켠 것만 기억한다 — 끄는 건 의도적 축소라 인정할 것이 없다.
    gLastOn = gtypes.has(t) ? t : null;
    try{ localStorage.setItem("s9gtypes", JSON.stringify([...gtypes])); }catch(e){}
    render(); return;
  }
  // 빈 화면 안내의 되돌리기 (REQ-20260826-039) — 안내가 원인을 말했으면
  // 되돌리는 손도 같은 자리에 있어야 한다. 말만 하고 손이 없으면 절반이다.
  const gf = e.target.closest("[data-gfix]");
  if (gf){
    if (gf.dataset.gfix === "filters"){
      const q = $("#q"); if (q) q.value = "";
      const qb = $("#q-body"); if (qb) qb.checked = false;
      ["#f-user", "#f-project", "#f-tag", "#f-type"].forEach(sel => {
        const el = $(sel); if (el) el.value = "";
      });
      // '내 것만'도 필터다 — 안 풀면 이 버튼이 조용히 죽는다
      const mi = $("#f-mine");
      if (mi && mi.checked){
        mi.checked = false;
        try{ localStorage.setItem("s9mine", "0"); }catch(e2){}
        fillProjects();
      }
    } else if (gf.dataset.gcond){
      // 범인 하나만 푼다 (REQ-20260827-054) — 사용자가 걸어 둔 나머지 조건까지
      // 쓸어내면 되돌리기가 아니라 초기화가 된다.
      const c = HCOND.find(x => x.k === gf.dataset.gcond);
      if (c) c.clear();
    } else {
      (gf.dataset.gtypes || "").split(",").filter(Boolean).forEach(t => gtypes.add(t));
      try{ localStorage.setItem("s9gtypes", JSON.stringify([...gtypes])); }catch(e2){}
    }
    gLastOn = null;   // 되돌렸으니 직전 헛클릭에 대한 인정은 더 이상 사실이 아니다
    render(); return;
  }
  const gl = e.target.closest("[data-glayout]");
  if (gl){
    graphLayout = gl.dataset.glayout;
    try{ localStorage.setItem("s9glayout", graphLayout); }catch(e2){}
    graphTf = null;  // 레이아웃 전환 시 뷰 리셋
    render();
    return;
  }
  // 문서 본문의 전이 버튼 — 속성 이름이 data-goto 와 갈라져 있어야 한다.
  // 같은 이름을 쓰면 위 탭 점프 분기가 먼저 집어삼킨다 (REQ-20260826-025).
  const gt = e.target.closest("[data-trans]");
  if (gt){
    // 문서 화면에서 누르든 보드 카드에서 누르든 **같은 판정**이다
    // (REQ-20260828-007 3차 반려). 여기서 창을 따로 짓지 않는다.
    const [id, to, from] = gt.dataset.trans.split("|");
    judgeAct(id, to, from);
    return;
  }
  // 보드 판정 카드의 승인·반려 — 문서 화면의 같은 버튼과 한 함수를 쓴다.
  const ap = e.target.closest("[data-approve]");
  if (ap){ judgeAct(ap.dataset.approve, "done", "review"); return; }
  const rj = e.target.closest("[data-reject]");
  if (rj){ judgeAct(rj.dataset.reject, "in-progress", "review"); return; }
  // 상단 계정 칩 — 얹으면 한도를 펴고, 누르면 계정을 바꾼다 (REQ-20260827-079)
  if (e.target.closest("#usage-chip")){ hideHover(); claudeAccountSwitch(); return; }
  // 깨우기도 카드(문서 열기)보다 먼저 잡는다 — 카드 안의 손잡이는 카드가
  // 아니다 (REQ-20260828-041). 보드 카드와 문서 화면이 같은 길로 들어온다.
  const wk = e.target.closest("[data-wake]");
  if (wk){ e.stopPropagation(); wakeDoc(wk.dataset.wake); return; }
  // 세우기도 같은 자리에서 잡는다 (REQ-20260829-024) — 깨우기의 반대편이고,
  // 카드 안의 손잡이는 카드가 아니라는 규칙도 그대로다.
  const sp = e.target.closest("[data-stop]");
  if (sp){ e.stopPropagation(); stopDoc(sp.dataset.stop); return; }
  /* 작업 자리 칩 (REQ-20260829-030 2차) — 카드보다 먼저 잡는다. 카드 안의
     손잡이는 카드가 아니라는 이 화면의 규칙 그대로다. 보드 카드와 문서 화면
     제목 줄에 선 같은 칩이 이 한 길로 들어온다 — 두 자리가 각자 길을 가지면
     언젠가 한쪽만 고쳐진다. */
  const wa = e.target.closest("[data-wsat]");
  if (wa){ e.stopPropagation(); wsOpen(wa.dataset.wsat); return; }
  /* 못 박은 줄을 놓는 손잡이 — 문서를 여는 길보다 **먼저** 잡는다
     (REQ-20260829-012). 이 손잡이는 못 박은 줄의 머리글 안에 있어 [data-doc]
     행 밖이지만, 손잡이가 행보다 앞에 서는 규칙은 이 화면 전체에 하나다. */
  const po = e.target.closest("[data-pinoff]");
  if (po){ e.stopPropagation(); docDeselect(); return; }
  // 문서 집기 손잡이는 카드(문서 열기)보다 **먼저** 잡는다 (REQ-20260827-064)
  const pk = e.target.closest("[data-pick]");
  if (pk){ e.stopPropagation(); docPick(pk.dataset.pick); return; }
  // 상단 상태 띠(data-statf)는 내렸다 — 이유는 renderBoard 주석에 (REQ-20260827-070).
  // MY PROJECTS 스트립 행: 클릭 = 단일 프로젝트 선택, 선택 행 재클릭 = 합집합(all) 복귀
  const mr = e.target.closest("[data-mine-slug]");
  if (mr){
    const el = $("#f-project");
    el.value = el.value === mr.dataset.mineSlug ? "" : mr.dataset.mineSlug;
    auditLimit = AUDIT_PAGE;
    render(); return;
  }
  const tf = e.target.closest("[data-typef]");
  if (tf){
    const el = $("#f-type");
    el.value = el.value === tf.dataset.typef ? "" : tf.dataset.typef;  // 같은 걸 다시 누르면 전체
    auditLimit = AUDIT_PAGE;
    render(); return;
  }
  const ex = e.target.closest("[data-expand]");
  if (ex){
    const k = ex.dataset.expand;
    expanded.has(k) ? expanded.delete(k) : expanded.add(k);
    render(); return;
  }
  if (e.target.closest("[data-depmore]")){
    // 전체 render()는 그래프 물리·카메라를 리셋한다 — 표만 제자리에서 갈아끼운다
    expanded.has("depsum") ? expanded.delete("depsum") : expanded.add("depsum");
    const ds = $("#depsum");
    if (ds) ds.outerHTML = depSummaryHTML(filtered());
    syncRailH();
    return;
  }
  if (e.target.closest("[data-audit-more]")){
    auditLimit += AUDIT_PAGE; render(); return;
  }
  const st = e.target.closest("[data-stream]");
  if (st){ selectedStream = st.dataset.stream; pushRoute(); loadStream(st.dataset.stream); return; }
  const ss = e.target.closest("[data-sset]");
  if (ss){ settingsSection = ss.dataset.sset;
    const meAdmin = isAdmin();
    document.querySelectorAll("[data-sset]").forEach(el => el.classList.toggle("sel", el === ss));
    pushRoute(); renderSettingsSection(meAdmin); return; }
  const rd = e.target.closest("[data-retrydoc]");
  if (rd){ loadDoc(rd.dataset.retrydoc); return; }
  // 전이표 다시 받기 (REQ-20260828-027) — 누르는 동안 무슨 일인지 버튼이 말한다.
  const rt = e.target.closest("[data-retrans]");
  if (rt){
    rt.disabled = true; rt.textContent = "받는 중…";
    transFailed = false;                 // 다시 "받는 중" 으로 되돌린다
    transRefill(rt.dataset.retrans);
    return;
  }
  /* 못 받은 값을 그 자리에서 다시 받는다 (REQ-20260828-039) — 문서 화면의
     `data-retrans` 와 같은 어휘를 값 전체로 넓힌 것이다. */
  const rs = e.target.closest("[data-resupply]");
  if (rs){
    rs.disabled = true; rs.textContent = "받는 중…";
    supplyAgain(rs.dataset.resupply);
    return;
  }
  /* 터미널 안의 문서 언급 (REQ-20260828-021 · -022). `[data-doc]` 보다 **먼저**
     잡는다 — 그 아래 핸들러는 Docs 탭으로 화면을 갈아치우는데, 여기서 원하는
     것은 읽던 자리를 지키는 것이다. 수식키·가운데클릭은 손대지 않는다:
     "새 탭에서 열기" 는 앵커의 href 가 그대로 맡는다. */
  const tp = e.target.closest(".ccpeek [data-ppick],.ccpeek [data-popen],"
    + ".ccpeek [data-pclose],.ccpeek [data-pmore],.ccpeek [data-cmore],"
    + ".ccpeek [data-cretry]");
  if (tp){
    e.stopPropagation();
    if (tp.dataset.ppick !== undefined){ ccPeekClose(); docPick(tp.dataset.ppick); }
    else if (tp.dataset.popen !== undefined){ const t = tp.dataset.popen; ccPeekClose(); docOpen(t); }
    else if (tp.dataset.pmore !== undefined){
      const pb = tp.closest(".ccpeek").querySelector("[data-pbody]");
      if (pb){ pb.innerHTML = ccPeekBody(ccPeekText, true); pb.scrollIntoView({block:"nearest"}); }
    }
    /* 코드 카드의 앞뒤 더 보기 — 누르는 동안 버튼이 무슨 일인지 말한다
       (문서 화면의 `data-retrans` 와 같은 어휘). */
    else if (tp.dataset.cmore !== undefined || tp.dataset.cretry !== undefined){
      const bx = tp.closest(".ccpeek");
      tp.disabled = true; tp.textContent = "받는 중…";
      ccCodeLoad(bx, bx.dataset.crel, +bx.dataset.cline || 0,
                 tp.dataset.cmore !== undefined
                   ? CODE_CTX_MORE : (+bx.dataset.cctx || CODE_CTX));
    }
    else ccPeekClose();
    return;
  }
  /* 터미널 안의 코드 파일 경로 (REQ-20260828-028). 문서 언급과 같은 자리·같은
     카드라 바로 옆에 둔다. 수식키·가운데클릭은 손대지 않는다 — 이 손잡이에는
     href 가 없으므로 브라우저가 알아서 아무 일도 하지 않는다. */
  const cp = e.target.closest("[data-tcode]");
  if (cp && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)){
    e.preventDefault(); e.stopPropagation();
    hideHover();
    ccCodePeek(cp);
    return;
  }
  const td = e.target.closest("[data-tdoc]");
  if (td && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)){
    e.preventDefault(); e.stopPropagation();
    hideHover();                       // 미리보기 카드와 얹기 카드가 겹치지 않게
    ccPeek(td);
    return;
  }
  const doc = e.target.closest("[data-doc]");
  if (doc){
    // 문서 링크가 진짜 href 를 갖게 되면서(REQ-20260827-013) 클릭에는 두 주인이
    // 생겼다. 수식키/가운데클릭은 브라우저 몫으로 남긴다 — 새 탭으로 여는 중에
    // 이 탭의 문서까지 바꾸면 "새 탭에서 열기"가 아니라 "두 군데서 열기"다.
    // 맨클릭은 우리가 막는다: 해시 이동과 pushRoute 가 겹쳐 뒤로가기가 두 번
    // 눌려야 하는 일을 없앤다. 카드·행(div)에는 막을 기본 동작이 없다.
    const link = doc.tagName === "A" && doc.getAttribute("href");
    if (link && (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)) return;
    if (link) e.preventDefault();
    docOpen(doc.dataset.doc);
  }
});
["#q","#q-body","#f-user","#f-project","#f-tag","#f-type"].forEach(s =>
  $(s).addEventListener("input", () => {
    auditLimit = AUDIT_PAGE;
    gLastOn = null;   // 조건이 바뀌면 직전 클릭에 대한 인정은 무효다
    render();
  }));
/* ?qdbg=<검색어> · ?qdbg-on — 머리 띠의 질문 칸을 **다른 상태로 세워 본다**
   (REQ-20260828-018). 눈으로 봐야 할 상태가 셋인데 지금 저장소 데이터로 나오는
   것은 하나뿐이다: 답이 다 찬 칸(46/46)은 표본을 좁혀야 나오고, 판을 잉크로
   반전하는 스킨(terminal·calm)의 활성 칸은 눌러 봐야 나온다.
   화면을 속이지 않는다 — 진짜 검색 칸에 진짜 글자를 넣고 진짜 버튼을 눌러,
   그 표본의 진짜 숫자를 그린다. */
if (/[?&]qdbg/.test(location.search)) setTimeout(() => {
  const m = /[?&]qdbg=([^&]*)/.exec(location.search);
  const el = $("#q");
  if (m && el){
    el.value = decodeURIComponent(m[1]);
    el.dispatchEvent(new Event("input", {bubbles: true}));
  }
  if (/[?&]qdbg-on/.test(location.search)) setTimeout(() => {
    const b = document.querySelector('[data-typef="question"]');
    if (b && !b.classList.contains("on")) b.click();
  }, 250);
}, 400);
// '내 것만' 토글 — 필터 변경으로 취급: 저장(s9mine) + 드롭다운 재스코핑 + 목록 제한 리셋.
// URL 해시에는 넣지 않는다(기기 로컬 정체성 — DOC-20260823-006 명시적 결정).
$("#f-mine").addEventListener("change", e => {
  try{ localStorage.setItem("s9mine", e.target.checked ? "1" : "0"); }catch(e2){}
  expanded.delete("mystrip");
  auditLimit = AUDIT_PAGE;
  gLastOn = null;   // '내 것만'도 조건이다 — 바뀌면 직전 클릭에 대한 인정은 무효
  fillProjects();   // 옵션 스코핑 + 범위 밖 선택은 all로 리셋
  render();
});

boot();
