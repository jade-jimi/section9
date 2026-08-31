/* project.js — 프로젝트 화면의 로직 한 벌 (REQ-20260831-028 · 설계 REQ-20260831-026)

   프로젝트는 새 탭도 새 화면도 갖지 않는다. 집은 **문서**고, 이 조각은 세 자리에
   얹힐 조각을 짓는다:

     ① Docs 좌측 `PROJECT` 목록 — 머리의 「새 프로젝트」와 행의 셋째 줄
     ② PRJ 문서 뷰의 프로젝트 패널 — 설정 인라인 · 멤버 표 · 관리 요약
     ③ Board/Graph 위 문맥 띠 — 244px 표를 대신하는 32px 한 줄

   이 물결(B1)은 **골격**이다: 짓는 함수는 진짜고, 데이터는 부르는 쪽이 준다.
   실연동(B2)에서 `/api/projects` 와 `catalog` 를 그 자리에 꽂는다. 검증 자는
   `web/verify-project.html` — 이 파일의 함수를 그대로 부르고 행만 지어 넣는다.

   ── 규율 넷 (어기면 이 파일이 아니라 화면이 갈라진다)

   1. **문구는 PRJ_TEXT 한 곳이다.** 아래 표 밖에 화면 글자를 적지 마라 —
      전량 초안이고, W2 의 판정(ux-writer·tech-writer·translator)이 이 표를
      통째로 갈아 끼운다. 문자열이 열 자리에 흩어져 있으면 그 교체가 비싸진다.
   2. **저장은 관문 하나다.** 설정 인라인이든 멤버 표든 `prjPost()` 를 지난다.
      한 화면에 저장 규칙이 둘이면 한 벌만 고쳐진다.
   3. **판정은 서버가 한다.** 여기 있는 권한 계산(prjLevel)은 **무엇을 그릴지**를
      정할 뿐이고, 거부는 전부 서버 응답 문구를 그대로 그린다 — 화면이 이유를
      지어내기 시작하면 CLI 와 다른 말을 하게 된다.
   4. **파생값을 들고 있지 않는다.** 열린 요청 수·마지막 활동은 catalog 에서
      그때 계산한다(prjStats). 별도 저장소를 만들지 않는다.

   ── mock API 가정 (A · REQ-20260831-027 명세와 B2 에서 맞춘다)

     GET  /api/projects        → {projects:[{id,slug,title,summary,status,customer,
                                   contact_name,contact_org,contact_email,contact_phone,
                                   members:[{user,role,since,until,position,active}],
                                   member_active,member_total}]}   ※ 기존 그대로
     POST /api/project/add     {user,slug,name,summary,customer} → {ok:true,id,slug}
                                                                 | {ok:false,error}
     POST /api/project/set     {user,slug, name?|summary?|customer?|status?|contact_*?}
                                                        → {ok:true} | {ok:false,error}
     POST /api/project/member  {user,slug,member,role?,position?,until?}   ※ 기존
     POST /api/project/member/rm {user,slug,member}                        ※ 기존

   변이 성공 뒤에는 폴링이 아니라 **한 번 다시 읽는다**(설계의 폴링 계약).       */
"use strict";

/* ── 문구 (전량 초안 — W2 의 C 판정 대상) ───────────────────────────────── */
const PRJ_TEXT = {
  // 목록
  head: "PROJECT",
  create: "새 프로젝트",                  // `.more` 가 앞에 "+ " 를 붙인다
  none: "아직 프로젝트가 없습니다",
  fold: n => `보관됨 ${n}개`,
  rowMeta: (mem, open, when) => `멤버 ${mem} · 열린 요청 ${open} · ${when}`,
  never: "활동 없음",                     // 목록 행의 셋째 칸(시각 자리)
  agoNone: "없음",                       // 「마지막 활동 …」 뒤에 설 때
  more: n => `${n}개 더 보기`,           // 목록의 「N개 더 보기」와 같은 말
  // 시간은 사람 기준으로 (s9-design 6절) — 계산은 prjAgo, 말은 여기
  agoNow: "방금",
  agoMin: n => `${n}분 전`,
  agoHour: n => `${n}시간 전`,
  agoYesterday: "어제",
  agoDay: n => `${n}일 전`,
  // 생성 창
  dlgCap: "프로젝트",
  dlgTitle: "새 프로젝트를 만듭니다",
  dlgDesc: "이름과 짧은 이름만 있으면 시작합니다 — 담당자와 멤버는 만든 뒤 문서에서 채웁니다.",
  dlgOk: "만들기",
  dlgCancel: "그만두기",
  fName: "표시명", fSlug: "짧은 이름", fSummary: "개요", fCustomer: "고객",
  phName: "예: 고객사 포털 개편",
  phSlug: "영문·숫자와 . _ - 만",
  phSummary: "선택 — 이 프로젝트가 무엇인지 한 줄",
  phCustomer: "선택 — 내부(자체) 또는 고객사 이름",
  hintSlug: "주소와 폴더 이름이 됩니다. 만든 뒤에는 바꿀 수 없습니다.",
  errName: "표시명을 적어 주세요",
  errSlugEmpty: "짧은 이름을 적어 주세요",
  errSlugBad: "영문·숫자와 . _ - 만 쓸 수 있습니다",
  errSlugTaken: "이미 있는 이름입니다",
  // 문서 뷰 패널
  hSet: "프로젝트 설정",
  hMembers: "멤버",
  hSummary: "관리 요약",
  kSlug: "slug", kStatus: "status", kSummary: "summary", kCustomer: "customer",
  /* 담당자는 **네 줄이다.** 설계의 스케치는 한 줄에 「이름 · 소속 · 메일 · 전화」를
     이어 보여 주지만, 그건 값을 읽는 모습이고 고치는 순간 네 필드가 한 칸에 든다 —
     이어 붙인 글자를 그대로 저장하면 이름 칸에 전화번호가 들어간다. 서버도 CLI도
     네 필드로 저장하므로 화면도 넷으로 편다(자리 판정은 designer 몫). */
  kContactName: "contact · 이름", kContactOrg: "contact · 소속",
  kContactEmail: "contact · 메일", kContactPhone: "contact · 전화",
  kMembers: "members",
  emptyVal: "—",
  memCap: (act, all) => `${act} 활성 / ${all}`,
  colUser: "사용자", colRole: "권한", colPos: "직무", colSince: "참여일",
  colUntil: "만료", colState: "상태",
  you: "ME",
  memNone: "아직 아무도 없습니다 — 이 프로젝트를 볼 수 있는 사람이 없습니다",
  memNoUsers: "먼저 사용자를 등록해야 합니다",
  memNoUsersGo: "Settings › 사용자 관리",
  addBtn: "추가", rmBtn: "제거",
  rmAria: u => `${u} 멤버 빼기`,
  viewerNote: "보기 권한입니다 — 멤버를 바꾸려면 maintainer 이상이 필요합니다",
  ownerLock: "owner 는 owner 만 바꿀 수 있습니다",
  lastOwner: "마지막 owner 는 뺄 수 없습니다",
  memOn: "활성", memOff: "만료",
  expSoon: "만료 14일 이내",
  untilFree: "무기한",                   // 값을 읽는 자리
  untilHint: "비우면 무기한",             // 고치는 자리(빈 날짜 상자)
  // 조사는 **받침으로 계산한다** — `을(를)` 은 서식 편지투다(josa 는 card.js 한 곳)
  rmTitle: (u, slug) => `${u}${josa(u, "을", "를")} ${slug} 에서 뺍니다`,
  rmDesc: "프로젝트 문서는 그대로 남고, 이 사람의 접근만 끊깁니다.",
  rmSelfDesc: "자신을 빼면 이 프로젝트를 더 볼 수 없습니다.",
  rmOk: "멤버 빼기",
  arcTitle: slug => `${slug}${josa(slug, "을", "를")} 보관합니다`,
  arcDesc: "이 프로젝트의 문서가 목록에서 접힙니다. 다시 활성으로 되돌릴 수 있습니다.",
  arcOk: "보관하기",
  unarcTitle: slug => `${slug}${josa(slug, "을", "를")} 다시 엽니다`,
  unarcDesc: "접혀 있던 문서가 목록으로 돌아옵니다.",
  unarcOk: "다시 열기",
  sumLine: (open, all, when) => `열린 요청 ${open} / 전체 ${all} · 마지막 활동 ${when}`,
  errPrefix: msg => `거부: ${msg}`,
  errNet: "서버에 연결할 수 없습니다",
  // 문맥 띠
  stripMeta: (mem, req) => `멤버 ${mem} · 요청 ${req}`,
  stripOpen: "프로젝트 문서 열기 →",
};

const PRJ_ROLES = ["owner", "maintainer", "contributor", "viewer"];
const PRJ_LVL = {viewer: 1, contributor: 2, maintainer: 3, owner: 4};
const PRJ_SLUG_RE = /^[A-Za-z0-9._-]+$/;      // 서버 do_project_add 와 같은 잣대
const PRJ_SOON_DAYS = 14;                     // 만료 임박 — MY PROJECTS 스트립과 같은 선
const PRJ_LIST_LIMIT = 20;                    // 밀도 규칙(Docs 그룹 20)

/* ── 권한: **무엇을 그릴지**만 정한다 (인가는 서버 project_can 단일 경로) ── */
function prjLevel(p, me, isAdmin){
  if (isAdmin) return 4;
  const m = me && (p.members || []).find(x => x.user === me && x.active);
  return m ? (PRJ_LVL[m.role] || 0) : 0;
}
function prjCtx(p, o){
  o = o || {};
  const lvl = prjLevel(p || {}, o.me, o.isAdmin);
  return {me: o.me || "", users: o.users || [], isAdmin: !!o.isAdmin, lvl,
          canManage: lvl >= 3, canOwn: lvl >= 4,
          now: o.now ? new Date(o.now) : new Date()};
}
// 마지막 owner 는 뺄 수도 강등할 수도 없다 — 서버가 막고, 화면은 왜인지 말한다
function prjOwnerCount(p){
  return (p.members || []).filter(m => m.role === "owner" && m.active).length;
}

/* ── 파생값: 들고 있지 않고 그때 센다 ─────────────────────────────────── */
function prjStats(rows, slug, now){
  const mine = (rows || []).filter(r => r.project === slug);
  const open = mine.filter(r => r.type === "request"
    && !["done", "cancelled"].includes(r.status)).length;
  let last = "";
  mine.forEach(r => { const u = r.updated || r.created || ""; if (u > last) last = u; });
  return {open, total: mine.length, last, when: last ? prjAgo(last, now) : PRJ_TEXT.never};
}
// "4분 전" — 사람 기준 (s9-design 6절). 자리 하나에서만 짓는다.
function prjAgo(iso, now){
  const t = Date.parse(iso);
  if (!isFinite(t)) return PRJ_TEXT.never;
  const s = Math.max(0, ((now ? +new Date(now) : Date.now()) - t) / 1000);
  if (s < 90) return PRJ_TEXT.agoNow;
  if (s < 3600) return PRJ_TEXT.agoMin(Math.round(s / 60));
  if (s < 86400) return PRJ_TEXT.agoHour(Math.round(s / 3600));
  if (s < 86400 * 2) return PRJ_TEXT.agoYesterday;
  if (s < 86400 * 30) return PRJ_TEXT.agoDay(Math.round(s / 86400));
  return iso.slice(0, 10);
}
// 만료 잣대는 셋이다: 지났나 · 14일 안인가 · 무기한인가
function prjUntilKind(m, now){
  if (!m.until) return "free";
  if (m.active === false) return "exp";
  const d = (Date.parse(m.until + "T23:59:59") - (now ? +new Date(now) : Date.now()))
    / 86400000;
  return d <= PRJ_SOON_DAYS ? "soon" : "ok";
}

/* ── ① Docs › PROJECT 목록 ───────────────────────────────────────────
   행 마크업은 문서 목록의 그것(.row/.st/.id)을 그대로 쓴다 — 같은 목록 안에서
   프로젝트 줄만 다른 문법이면 그 줄이 남의 것처럼 보인다. */
function prjSort(list, statsBy){
  // 일하는 사람은 최근 것을 찾는다 — 이름순이 아니라 최근 활동순 (설계 판정)
  return [...(list || [])].sort((a, b) => {
    const la = (statsBy?.[a.slug]?.last) || "", lb = (statsBy?.[b.slug]?.last) || "";
    if (la !== lb) return la < lb ? 1 : -1;
    return String(a.title || a.slug).localeCompare(String(b.title || b.slug));
  });
}
function prjRowHTML(p, o){
  const st = prjStats0(o, p.slug);
  const off = p.status === "archived";
  const sel = o && o.selected === p.id;
  return `<div class="row pjrow${off ? " off" : ""}${sel ? " sel" : ""}"`
    + ` data-doc="${esc(p.id)}" role="button" tabindex="-1" data-rove-item`
    + `${sel ? ' aria-current="true"' : ""}`
    + ` style="--sc:${off ? "var(--c-cancelled)" : "var(--text)"}">`
    + `<span class="st">${esc(p.status || "")}</span>`
    + `<div class="id">${esc(p.id)} · ${esc(p.slug)}</div>`
    + `<div>${esc(p.title || p.slug)}</div>`
    + `<div class="pjmeta">${esc(PRJ_TEXT.rowMeta(p.member_active ?? 0, st.open, st.when))}</div>`
    + `</div>`;
}
function prjStats0(o, slug){
  return (o && o.statsBy && o.statsBy[slug])
    || {open: 0, total: 0, last: "", when: PRJ_TEXT.never};
}
/* 목록 한 장 — 머리 · 활성 줄 · 보관 접힘. 0·1·N 에서 **구조가 같다**:
   1개일 때 머리를 빼거나 버튼을 옮기면 그때 배운 자리가 다음에 틀린다. */
function prjListHTML(list, o){
  o = o || {};
  const all = list || [];
  const live = prjSort(all.filter(p => p.status !== "archived"), o.statsBy);
  const arc = prjSort(all.filter(p => p.status === "archived"), o.statsBy);
  // 만들 권한이 없으면 **아예 안 그린다** — 회색 단추는 눌릴 것 같은 거짓 약속
  const newBtn = o.canCreate
    ? `<button class="more" data-prjnew type="button">${esc(PRJ_TEXT.create)}</button>` : "";
  const limit = o.limit || PRJ_LIST_LIMIT;
  const shown = o.expanded ? live : live.slice(0, limit);
  let body = shown.map(p => prjRowHTML(p, o)).join("");
  if (live.length > shown.length)
    body += `<button class="more" data-prjmore type="button">`
      + `${esc(PRJ_TEXT.more(live.length - shown.length))}</button>`;
  /* 하나도 없을 때도 **머리는 그대로** 선다 (0→1→N 구조 불변). 만드는 손잡이를
     빈 자리로 옮기면 첫 프로젝트를 만든 순간 단추가 다른 데로 걸어가고, 그때
     배운 자리가 두 번째부터 틀린다. 빈 자리에는 한 줄만 — 행동은 바로 위에 있다. */
  if (!all.length)
    body = `<div class="pjnone">${esc(PRJ_TEXT.none)}</div>`;
  else if (arc.length)
    body += o.arcOpen
      ? arc.map(p => prjRowHTML(p, o)).join("")
      : `<button class="more" data-prjarc type="button">${esc(PRJ_TEXT.fold(arc.length))}</button>`;
  return `<div class="pjlist"><div class="pjhead"><span>${esc(PRJ_TEXT.head)}`
    + `<span class="pjn"> ${all.length}</span></span>${newBtn}</div>`
    + body + `</div>`;
}

/* ── 생성 창 — 창은 `s9dlg` 것이다. 여기서 짓는 것은 네 줄과 그 검사뿐 ─── */
function prjSlugFrom(name){
  // 한글은 로마자로 옮기지 않는다(설계 판정) — 후보가 없으면 비워 두고 사람이 적는다
  const s = String(name || "").trim().toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").replace(/-{2,}/g, "-");
  return PRJ_SLUG_RE.test(s) ? s : "";
}
function prjFormCheck(v, taken){
  if (!String(v.name || "").trim()) return {ok: false, field: "name", err: PRJ_TEXT.errName};
  const slug = String(v.slug || "").trim();
  if (!slug) return {ok: false, field: "slug", err: PRJ_TEXT.errSlugEmpty};
  if (!PRJ_SLUG_RE.test(slug)) return {ok: false, field: "slug", err: PRJ_TEXT.errSlugBad};
  if ((taken || []).includes(slug))
    return {ok: false, field: "slug", err: PRJ_TEXT.errSlugTaken};
  return {ok: true, field: "", err: ""};
}
function prjFormHTML(v){
  v = v || {};
  const f = (k, label, ph, extra) =>
    `<label for="pjf-${k}">${esc(label)}</label>`
    + `<input class="pjc" id="pjf-${k}" data-pjf="${k}" type="text"`
    + ` value="${esc(v[k] || "")}" placeholder="${esc(ph)}"${extra || ""}>`;
  return `<div class="pjform">`
    + f("name", PRJ_TEXT.fName, PRJ_TEXT.phName, " autofocus")
    + f("slug", PRJ_TEXT.fSlug, PRJ_TEXT.phSlug)
    + `<div class="pjhint">${esc(PRJ_TEXT.hintSlug)}</div>`
    + f("summary", PRJ_TEXT.fSummary, PRJ_TEXT.phSummary)
    + f("customer", PRJ_TEXT.fCustomer, PRJ_TEXT.phCustomer)
    + `<div class="pjerr" hidden></div></div>`;
}
/* 창이 뜬 뒤 값을 모으고 검사를 건다. 확인 단추는 **검사가 통과할 때만** 눌린다 —
   눌러 보고 나서 다그치는 창이 되지 않게(s9dlg 의 required 와 같은 규율). */
function prjFormWire(root, v, o){
  o = o || {};
  const box = root.querySelector(".pjform");
  if (!box) return null;
  const err = box.querySelector(".pjerr");
  const yes = root.querySelector(".dlgyes");
  let slugTouched = false;
  const sync = () => {
    const r = prjFormCheck(v, o.taken || []);
    // 아직 아무것도 안 적은 창은 꾸짖지 않는다 — 손이 닿은 뒤부터 이유를 말한다
    const said = v.name || v.slug;
    err.hidden = r.ok || !said;
    err.textContent = r.ok ? "" : r.err;
    if (yes) yes.disabled = !r.ok;
    return r;
  };
  box.querySelectorAll("[data-pjf]").forEach(el => {
    const k = el.dataset.pjf;
    el.addEventListener("input", () => {
      v[k] = el.value;
      if (k === "slug") slugTouched = true;
      if (k === "name" && !slugTouched){
        v.slug = prjSlugFrom(el.value);
        const s = box.querySelector('[data-pjf="slug"]');
        if (s) s.value = v.slug;
      }
      sync();
    });
  });
  sync();
  /* 손은 **첫 칸에** 놓는다 — 창이 확인 단추에 초점을 주는 것은 물음이 하나인
     창의 규칙이고(s9dlg), 여기는 적을 것이 넷인 창이다. 적으러 온 사람에게
     Tab 부터 누르게 하지 않는다. */
  const first = box.querySelector('[data-pjf="name"]');
  if (first) first.focus();
  return sync;
}
async function prjCreateDlg(o){
  o = o || {};
  const v = {name: "", slug: "", summary: "", customer: ""};
  /* 창의 두 낱말은 **이름으로** 넘긴다 (card.js 의 `stopAsk` 선례).
     확인 창의 대장(tests/test_dialog_safe.py CENSUS)은 주·부 낱말로 창을
     가려내는데, 문안이 표에서 오면 대장이 읽을 이름이 있어야 한다. */
  const {dlgOk, dlgCancel} = PRJ_TEXT;
  const p = s9dlg({kind: "confirm", cap: PRJ_TEXT.dlgCap, title: PRJ_TEXT.dlgTitle,
    descHtml: `<div>${esc(PRJ_TEXT.dlgDesc)}</div>` + prjFormHTML(v),
    ok: dlgOk, cancel: dlgCancel});
  const root = document.querySelector(".dlg");
  if (root) prjFormWire(root, v, o);
  if (!await p) return null;
  return prjPost("/api/project/add", {slug: v.slug.trim(), name: v.name.trim(),
    summary: v.summary.trim(), customer: v.customer.trim()}, o);
}

/* ── ② PRJ 문서 뷰 패널 ─────────────────────────────────────────────── */
function prjSetRowsHTML(p, c){
  // 값 자리 인라인 편집 — 쉼 상태는 글자다. maintainer 미만은 컨트롤 없이 값만.
  const val = (k, text) => {
    const shown = text ? esc(text) : `<span class="none">${esc(PRJ_TEXT.emptyVal)}</span>`;
    return c.canManage
      ? `<button class="pjv" type="button" data-pjset="${k}"`
        + ` data-val="${esc(text || "")}">${shown}</button>`
      : shown;
  };
  const statusCell = c.canOwn
    ? `<select class="pjc" data-pjstatus>`
      + ["active", "archived"].map(s =>
          `<option value="${s}"${s === p.status ? " selected" : ""}>${s}</option>`).join("")
      + `</select>`
    : `<span style="color:${p.status === "archived"
        ? "var(--c-cancelled)" : "var(--text)"}">●</span> ${esc(p.status || "")}`;
  const row = (k, v) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`;
  /* **빈 칸은 채울 수 있는 사람에게만 자리다.** 문서 뷰의 메타 표는 값이 없는
     줄을 아예 안 그리는 문법이고(docs.js `fields.filter`), 읽기만 하는 사람에게
     「— · — · — · —」 넉 줄은 아무 말도 하지 않는다. 고칠 수 있는 사람에게는
     그 빈 줄이 곧 채울 자리이므로 그때만 선다. */
  const opt = (k, key, v) => (c.canManage || v) ? row(k, val(key, v)) : "";
  return row(PRJ_TEXT.kSlug, `<span class="path">${esc(p.slug)}</span>`)
    + row(PRJ_TEXT.kStatus, statusCell)
    + opt(PRJ_TEXT.kSummary, "summary", p.summary)
    + opt(PRJ_TEXT.kCustomer, "customer", p.customer)
    + opt(PRJ_TEXT.kContactName, "contact_name", p.contact_name)
    + opt(PRJ_TEXT.kContactOrg, "contact_org", p.contact_org)
    + opt(PRJ_TEXT.kContactEmail, "contact_email", p.contact_email)
    + opt(PRJ_TEXT.kContactPhone, "contact_phone", p.contact_phone);
}
function prjMemberRowHTML(m, p, c){
  const kind = prjUntilKind(m, c.now);
  const lastOwner = m.role === "owner" && prjOwnerCount(p) <= 1;
  const ownerLocked = m.role === "owner" && !c.canOwn;
  const name = m.user === c.me
    ? `<span class="m-you">${esc(m.user)}</span> <span class="m-tag">· ${esc(PRJ_TEXT.you)}</span>`
    : esc(m.user);
  const stateCls = m.active === false ? "m-off" : "m-on";
  const state = m.active === false ? PRJ_TEXT.memOff : PRJ_TEXT.memOn;
  if (!c.canManage)
    // 뷰어에게는 컨트롤을 **그리지 않는다** — 회색 나열은 눌릴 것 같은 거짓 약속
    return `<tr${m.active === false ? ' class="exp"' : ""}><td>${name}</td>`
      + `<td class="m-role">${esc(m.role)}</td>`
      + `<td>${m.position ? esc(m.position) : `<span class="m-tag">${esc(PRJ_TEXT.emptyVal)}</span>`}</td>`
      + `<td class="m-role">${esc(m.since || "")}</td>`
      + `<td class="m-role${kind === "soon" ? " m-soon" : ""}"`
      + `${kind === "soon" ? ` title="${esc(PRJ_TEXT.expSoon)}"` : ""}>`
      + `${m.until ? esc(m.until) : `<span class="m-tag">${esc(PRJ_TEXT.untilFree)}</span>`}</td>`
      + `<td class="m-state ${stateCls}">${esc(state)}</td></tr>`;
  const roles = (c.canOwn || m.role === "owner")
    ? PRJ_ROLES : PRJ_ROLES.filter(r => r !== "owner");
  return `<tr data-pjmem="${esc(m.user)}"${m.active === false ? ' class="exp"' : ""}>`
    + `<td>${name}</td>`
    + `<td><select class="pjc" data-pjrole${ownerLocked
        ? ` disabled title="${esc(PRJ_TEXT.ownerLock)}"` : ""}>`
      + roles.map(r => `<option value="${r}"${r === m.role ? " selected" : ""}>${r}</option>`).join("")
      + `</select></td>`
    + `<td><input class="pjc" data-pjpos value="${esc(m.position || "")}"`
      + ` placeholder="${esc(PRJ_TEXT.emptyVal)}" size="10"></td>`
    + `<td class="m-role">${esc(m.since || "")}</td>`
    + `<td><input class="pjc${kind === "soon" ? " m-soon" : ""}" type="date" data-pjuntil`
      + ` value="${esc(m.until || "")}" title="${esc(kind === "soon"
          ? PRJ_TEXT.expSoon : PRJ_TEXT.untilHint)}"></td>`
    + `<td class="m-state ${stateCls}">${esc(state)}</td>`
    + `<td><span class="acts pjcell"><button type="button" data-pjrm="${esc(m.user)}"`
      + `${lastOwner || ownerLocked
          ? ` disabled title="${esc(lastOwner ? PRJ_TEXT.lastOwner : PRJ_TEXT.ownerLock)}"` : ""}`
      + ` aria-label="${esc(PRJ_TEXT.rmAria(m.user))}">${esc(PRJ_TEXT.rmBtn)}</button>`
      + `</span></td></tr>`;
}
function prjMembersHTML(p, c){
  const mem = p.members || [];
  const cols = [PRJ_TEXT.colUser, PRJ_TEXT.colRole, PRJ_TEXT.colPos, PRJ_TEXT.colSince,
                PRJ_TEXT.colUntil, PRJ_TEXT.colState];
  const has = new Set(mem.map(m => m.user));
  const cand = (c.users || []).map(u => u.name || u).filter(n => !has.has(n));
  /* 멤버가 0명인데 후보도 0명이면 **다른 문구**다 — 추가 폼을 보여 주면 막다른
     길이 된다(설계 판정). 등록부터 하러 갈 자리를 준다. */
  if (!mem.length && (!c.canManage || !cand.length))
    return `<p class="pjnote">${esc(c.canManage ? PRJ_TEXT.memNoUsers : PRJ_TEXT.memNone)}`
      + (c.canManage
        // 주소 한 줄이면 된다 — `data-goto` 는 **탭 이름 하나**만 아는 손잡이라
        // 절(section)까지 실으면 그 핸들러가 탭을 못 찾고 조용히 삼킨다.
        ? ` <a class="doclink" href="#settings/users">`
          + `${esc(PRJ_TEXT.memNoUsersGo)}</a>` : "")
      + `</p>`;
  const addRow = c.canManage && cand.length ? `<tr class="pjadd">`
    + `<td><select class="pjc" data-pjnew="user">`
      + cand.map(n => `<option>${esc(n)}</option>`).join("") + `</select></td>`
    + `<td><select class="pjc" data-pjnew="role">`
      + PRJ_ROLES.filter(r => c.canOwn || r !== "owner")
          .map(r => `<option value="${r}"${r === "contributor" ? " selected" : ""}>${r}</option>`).join("")
      + `</select></td>`
    + `<td><input class="pjc" data-pjnew="position" placeholder="${esc(PRJ_TEXT.colPos)}" size="10"></td>`
    + `<td></td>`
    + `<td><input class="pjc" type="date" data-pjnew="until" title="${esc(PRJ_TEXT.untilHint)}"></td>`
    + `<td></td>`
    + `<td><span class="acts pjcell"><button type="button" data-pjadd>`
      + `${esc(PRJ_TEXT.addBtn)}</button></span></td></tr>` : "";
  const empty = !mem.length
    ? `<tr><td colspan="${cols.length + 1}" class="pjnote">${esc(PRJ_TEXT.memNone)}</td></tr>`
    : "";
  /* 좁은 판에서는 표가 **제 안에서** 구른다 — 일곱 칸(날짜 상자 둘 포함)이
     들어갈 폭이 없을 때 머리글이 두 줄로 접히면 표가 흔들려 보이고, 쪽 전체를
     가로로 굴리면 옆의 다른 절까지 따라 움직인다. */
  return `<div class="pmemwrap"><table class="pmem"><caption>`
    + esc(PRJ_TEXT.memCap(p.member_active ?? mem.filter(m => m.active !== false).length,
                          p.member_total ?? mem.length))
    + `</caption><thead><tr>`
    + cols.map(h => `<th scope="col">${esc(h)}</th>`).join("")
    + (c.canManage ? `<th scope="col"><span class="m-tag">&nbsp;</span></th>` : "")
    + `</tr></thead><tbody>${empty}${mem.map(m => prjMemberRowHTML(m, p, c)).join("")}`
    + `${addRow}</tbody></table></div>`
    + (c.canManage ? "" : `<p class="pjnote">${esc(PRJ_TEXT.viewerNote)}</p>`);
}
function prjPanelHTML(p, o){
  const c = prjCtx(p, o);
  const st = prjStats0(o, p.slug);
  return `<section class="pjpanel" data-pjslug="${esc(p.slug)}">`
    + `<table class="metatbl pjset">${prjSetRowsHTML(p, c)}</table>`
    + `<h2 class="pjh">${esc(PRJ_TEXT.hMembers)}</h2>`
    + prjMembersHTML(p, c)
    + `<h2 class="pjh">${esc(PRJ_TEXT.hSummary)}</h2>`
    // 「마지막 활동 활동 없음」이 되지 않게 — 같은 사실이 자리에 따라 다른
    // 낱말을 쓴다(행에서는 시각 자리라 「활동 없음」, 여기서는 뒤에 붙는 말)
    + `<p class="pjsum">${esc(PRJ_TEXT.sumLine(st.open, st.total,
        st.last ? st.when : PRJ_TEXT.agoNone))}</p>`
    + `<div class="pjerr" hidden></div></section>`;
}

/* ── ③ Board/Graph 위 문맥 띠 — 한 줄. 표가 먹던 244px 를 돌려준다 ────── */
function prjStripHTML(p, o){
  if (!p) return "";                     // 고른 프로젝트가 없으면 자리도 없다
  const st = prjStats0(o, p.slug);
  const off = p.status === "archived";
  return `<div class="pjstrip">`
    + `<span class="cdot" style="background:${off ? "var(--c-cancelled)" : "var(--text)"}"></span>`
    + `<span class="pjs-t">${esc(p.title || p.slug)}</span>`
    // 상태만 대문자다 — 목록 행의 `.st` 와 같은 얼굴이라야 두 자리가 같은 것을
    // 말한다고 읽힌다. slug 까지 함께 올리면 없는 이름이 된다(SECTION9).
    + `<span class="pjs-m">${esc(p.slug)}</span>`
    + `<span class="pjs-st">${esc(p.status || "")}</span>`
    + `<span class="pjs-m">${esc(PRJ_TEXT.stripMeta(p.member_active ?? 0, st.total))}</span>`
    + `<a class="doclink pjs-open" href="#docs/${esc(p.id)}" data-doc="${esc(p.id)}">`
      + `${esc(PRJ_TEXT.stripOpen)}</a></div>`;
}

/* ── 저장 관문 하나 ───────────────────────────────────────────────────
   설정 인라인도 멤버 표도 여기를 지난다. 거부 사유는 **서버가 준 문장**을 그대로
   그리고(화면이 이유를 짓지 않는다), 실패하면 컨트롤을 원복한다 — 화면에 남은
   값이 문서에 없는 값이면 그 화면은 거짓말을 하고 있다. */
async function prjPost(path, payload, o){
  o = o || {};
  /* 실패 줄은 **다시 그린 뒤의 자리**에 쓴다 (앞선 멤버 패널이 배운 것):
     원복(reload)이 패널을 통째로 갈아 끼우므로, 미리 잡아 둔 노드에 쓰면 그
     글자는 화면에서 떨어져 나간 판에 남아 아무도 못 본다. 그래서 노드가 아니라
     **자리(선택자)** 를 들고 다닌다. */
  const say = msg => {
    const box = document.querySelector(o.errSel || ".pjpanel .pjerr");
    if (!box) return;
    box.textContent = PRJ_TEXT.errPrefix(msg);
    box.hidden = false;
  };
  const send = o.post || (async (pth, body) => {
    const r = await fetch(pth, {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({user: o.me || "", ...body})});
    return r.json();
  });
  let d;
  try{ d = await send(path, payload); }
  catch(e){ if (o.reload) await o.reload(); say(PRJ_TEXT.errNet); return null; }
  if (!d || !d.ok){
    if (o.reload) await o.reload();      // 컨트롤 원복 — 그린 값과 문서를 맞춘다
    say((d && d.error) || PRJ_TEXT.errNet);
    return null;
  }
  if (o.reload) await o.reload();
  return d;
}

/* 배선 — 값이 실제로 바뀐 변경만 나간다(같은 값 재선택은 요청 0회).

   **부르는 쪽은 `o.reload` 를 주어야 한다**: 다시 읽고 다시 그리는 손. 성공이든
   거부든 화면은 그 한 손으로만 갱신된다 — 화면이 제 손으로 값을 고쳐 그리기
   시작하면 문서에 없는 값이 화면에 남는 길이 열린다(낙관적 갱신 금지). 없이
   부르면 고친 값이 문서에 들어가고도 화면은 옛 값을 보인다. */
function prjWire(root, p, o){
  o = o || {};
  const c = prjCtx(p, o);
  const slug = p.slug;
  const post = (path, body) => prjPost(path, {slug, ...body},
    {...o, errSel: `.pjpanel[data-pjslug="${slug}"] .pjerr`});
  // 설정 — 값 자리 인라인 편집(클릭/Enter 로 입력, blur·Enter 로 저장, Esc 로 물림)
  root.querySelectorAll("[data-pjset]").forEach(btn => {
    btn.addEventListener("click", () => {
      const k = btn.dataset.pjset, was = btn.dataset.val || "";
      const inp = document.createElement("input");
      inp.className = "pjc"; inp.value = was; inp.setAttribute("data-pjedit", k);
      btn.replaceWith(inp);
      inp.focus(); inp.select();
      let done = false;
      const close = save => {
        if (done) return;
        done = true;
        const v = inp.value;
        inp.replaceWith(btn);
        if (save && v !== was) post("/api/project/set", {[k]: v});
      };
      inp.addEventListener("blur", () => close(true));
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter"){ e.preventDefault(); close(true); }
        else if (e.key === "Escape"){ e.stopPropagation(); close(false); }
      });
    });
  });
  // status 만 확인 창을 거친다 — 보관은 그 프로젝트의 문서가 통째로 접히는 사건
  const stSel = root.querySelector("[data-pjstatus]");
  if (stSel) stSel.addEventListener("change", async () => {
    const to = stSel.value, was = p.status;
    if (to === was) return;
    const arc = to === "archived";
    // 문안은 둘(보관·되열기)이지만 **자리는 하나**다 — 대장의 열쇠도 하나
    const statusOk = arc ? PRJ_TEXT.arcOk : PRJ_TEXT.unarcOk;
    const {dlgCancel} = PRJ_TEXT;
    const ok = await s9dlg({kind: "confirm", cap: PRJ_TEXT.dlgCap,
      title: arc ? PRJ_TEXT.arcTitle(slug) : PRJ_TEXT.unarcTitle(slug),
      desc: arc ? PRJ_TEXT.arcDesc : PRJ_TEXT.unarcDesc,
      ok: statusOk, cancel: dlgCancel});
    if (!ok){ stSel.value = was; return; }
    post("/api/project/set", {status: to});
  });
  // 멤버 — 바꾼 그 자리에서 즉시 저장(되돌리기가 바로 옆에 있어 확인 창 없음)
  root.querySelectorAll("[data-pjmem]").forEach(tr => {
    const member = tr.dataset.pjmem;
    const on = (sel, key) => {
      const el = tr.querySelector(sel);
      if (!el || el.disabled) return;
      const was = el.value;
      el.addEventListener("change", () => {
        if (el.value === was) return;
        post("/api/project/member", {member, [key]: el.value});
      });
    };
    on("[data-pjrole]", "role");
    on("[data-pjpos]", "position");
    on("[data-pjuntil]", "until");
    const rm = tr.querySelector("[data-pjrm]");
    if (rm && !rm.disabled) rm.addEventListener("click", async () => {
      const {rmOk, dlgCancel} = PRJ_TEXT;
      const ok = await s9dlg({kind: "confirm", cap: PRJ_TEXT.hMembers,
        title: PRJ_TEXT.rmTitle(member, slug),
        desc: member === c.me ? PRJ_TEXT.rmSelfDesc : PRJ_TEXT.rmDesc,
        ok: rmOk, cancel: dlgCancel});
      if (ok) post("/api/project/member/rm", {member});
    });
  });
  const add = root.querySelector("[data-pjadd]");
  if (add) add.addEventListener("click", () => {
    const v = k => { const el = root.querySelector(`[data-pjnew="${k}"]`); return el ? el.value : ""; };
    if (!v("user")) return;
    post("/api/project/member", {member: v("user"), role: v("role"),
      position: v("position"), until: v("until")});
  });
}
