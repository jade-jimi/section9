/* state.js — 화면 상태와 정렬 — catalog/tab/펼침, workOrder·recentOrder·stableOrder, esc·shortId */
"use strict";
let catalog = [], graph = null, auditCache = null, TRANS = {}, projects = [];
let tab = "board", selectedDoc = null, selectedStream = null;
let streamTimer = null, reqStreamTimer = null;  // live follow 폴링 (화면 이탈 시 정리)
// 그래프 타입 표시 집합 — 기본은 request/knowledge (세션 로그 노드 숨김, REQ-20260824-026)
const GTYPES_DEFAULT = ["request", "article", "knowledge", "question"];
// 이미 화면에 있던 종류 — 사용자가 끈 것과 "아직 있어 본 적 없는 것"을 가른다
const GTYPES_SEEN = (() => {
  try{ const v = JSON.parse(localStorage.getItem("s9gtypeseen") || "null");
       return new Set(Array.isArray(v) ? v : []); }catch(e){ return new Set(); }
})();
let gtypes = new Set(GTYPES_DEFAULT);
try{ const s = JSON.parse(localStorage.getItem("s9gtypes") || "null");
     if (Array.isArray(s) && s.length) gtypes = new Set(s); }catch(e){}
/* 나중에 생긴 종류는 **켠 채로** 들어온다 (REQ-20260827-073). 저장된 집합은
   그 종류가 있기 전에 만들어졌으므로 그대로 쓰면 새 종류가 영영 꺼진 채다 —
   사용자는 끈 적이 없는데 안 보이고, 범례를 눌러 볼 생각도 하지 않는다.
   기본으로 켜는 종류에만 적용한다: 사용자가 실제로 끈 것은 그대로 둔다. */
GTYPES_DEFAULT.forEach(t => { if (!GTYPES_SEEN.has(t)) gtypes.add(t); });
try{ localStorage.setItem("s9gtypeseen", JSON.stringify(GTYPES_DEFAULT)); }catch(e){}
// 방금 범례에서 켠 종류. 켰는데도 화면이 그대로면 빈 화면 안내가 그 사실을
// 인정한다 (REQ-20260826-039 재작업) — 같은 문장을 말없이 다시 그리면 사용자는
// 컨트롤이 죽은 줄 안다. 조건이 바뀌거나 되돌리기가 성공하면 무효가 된다.
let gLastOn = null;
let expanded = new Set();      // board 컬럼 / docs 그룹 펼침 상태
let auditLimit = AUDIT_PAGE;

// 작업 순서 — Board 컬럼/Docs 목록/검색 결과 공통. 진입점은 여기 하나다
// (CLI의 work_order()와 같은 원리): 규칙이 흩어지면 탭마다 순서가 달라지고
// 우선순위를 신뢰할 수 없게 된다.
// 1차 키는 우선순위 내림차순 (REQ-20260826-005) — 표기만 하고 순서가 그대로면
// 축이 화면을 바꾸지 않는다. 2차 키는 최근 갱신순으로 남긴다: CLI는 굶주림을
// 막으려 생성 순(오래된 것 먼저)이지만, 보드는 대기열이 아니라 지금 상태를
// 보는 화면이라 done 227건이 가장 오래된 것부터 쌓이면 쓸모가 없다.
const workOrder = rows => [...rows].sort((a, b) =>
  (prioOf(b) - prioOf(a)) ||
  (b.updated || b.created || "").localeCompare(a.updated || a.created || ""));

// Docs 목록만은 **최근 수정 순**이다 (REQ-20260827-051). Board 는 "무엇부터
// 집을까"를 묻는 화면이라 우선순위가 앞서지만, Docs 는 "무슨 일이 있었나"를
// 훑는 화면이다 — 거기서는 우선순위 50짜리 옛 문서가 방금 고친 문서 위에
// 앉아 있는 것이 방해가 된다. 정렬 규칙을 흩지 않으려고 여기 나란히 둔다.
const recentOrder = rows => [...rows].sort((a, b) =>
  (b.updated || b.created || "").localeCompare(a.updated || a.created || ""));

/* **읽는 동안 목록이 발밑에서 움직이지 않게** 한다 (REQ-20260828-009).

   사용자: "지금 왼쪽 문서 목록이 거의 실시간으로 목록이 갱신이 되어버리니
   본문 제목을 캐치하기 어렵다."

   원인은 폴링 주기가 아니라 **정렬 축**이다. 목록은 `updated` 내림차순인데, 이
   저장소에서는 에이전트가 쉬지 않고 노트를 붙이므로 15초마다 여러 문서의
   `updated` 가 바뀌고 목록 전체가 다시 섞인다. 주기를 늦추면 덜 자주 섞일 뿐
   같은 일이 난다.

   그래서 **순서를 얼린다**: 화면에 들어온 순간의 순위를 기억하고, 배경 갱신에는
   그 순위를 그대로 쓴다. 얼음을 깨는 것은 사람이 한 일뿐이다 — 필터·검색·타입을
   바꾸거나 Docs 화면에 새로 들어올 때. 그 사이에 **새로 생긴 문서는 맨 위로**
   올라온다: 그건 발밑이 흔들리는 것이 아니라 실제로 새것이 온 것이다. */
const curType0 = () => { const e = document.querySelector("#f-type"); return e ? e.value : ""; };
let docRank = null, docRankKey = "";
function stableOrder(rows, key, refreeze){
  if (docRank === null || refreeze || docRankKey !== key){
    docRank = new Map(); docRankKey = key;
    recentOrder(rows).forEach((r, i) => docRank.set(r.id, i));
  }
  const fresh = rows.filter(r => !docRank.has(r.id));
  if (fresh.length){
    let min = Math.min(0, ...docRank.values());
    // 뒤집어 넣어야 가장 최근 것이 가장 작은 순위(=맨 위)를 받는다
    recentOrder(fresh).reverse().forEach(r => docRank.set(r.id, --min));
  }
  return [...rows].sort((a, b) => docRank.get(a.id) - docRank.get(b.id));
}

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
// uid 표시 축약 (REQ-20260825-031/-034): 지문 접미(-xxxx)는 같은
// (타입-날짜-순번)이 실제로 겹칠 때만 보여준다 — git 짧은 해시 원리.
// 참조(data-doc)는 항상 전문 uid, 축약은 렌더 시점에만.
const SYS_TAGS = new Set(["auto-audit"]);
// 태그별 안정적 색조 — 같은 태그는 항상 같은 색(문자열 해시 → hue).
// 무채색 칩만 늘어놓으면 눈이 태그를 구분하지 못한다(REQ-20260825-068).
function tagHue(t){
  let h = 0;
  for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) % 360;
  return h;
}   // 출처 표식 — 태그 UI에서 숨김
let idBaseCount = new Map();
function rebuildIdMap(){
  idBaseCount = new Map();
  for (const r of catalog){
    const m = /^([A-Z]{3}-\d{8}-\d+)-[0-9a-z]{4}$/.exec(r.id || "");
    if (m) idBaseCount.set(m[1], (idBaseCount.get(m[1]) || 0) + 1);
  }
}
function shortId(id){
  const m = /^([A-Z]{3}-\d{8}-\d+)-[0-9a-z]{4}$/.exec(id || "");
  if (!m) return id;
  return (idBaseCount.get(m[1]) || 0) > 1 ? id : m[1];
}
// 문서 링크는 이 한 곳에서만 만든다 (REQ-20260827-013). href 가 있어야 앵커가
// 링크가 된다 — Tab·가운데클릭·"새 탭에서 열기"가 전부 여기서 따라온다. 아홉
// 자리에 손으로 적으면 언젠가 한 자리가 빠지고, 그 자리만 마우스 전용이 된다.
// href 와 data-doc 은 **반드시 같은 값**이다: 갈라지면 새 탭만 다른 문서를 연다.
// inner 는 이미 escape 된 HTML(짧은 id·세션 이름 등)이다.
const cssq = v => window.CSS && CSS.escape ? CSS.escape(String(v))
  : String(v).replace(/["\\]/g, "\\$&");
const dlink = (id, inner) =>
  `<a class="doclink" href="#docs/${esc(id)}" data-doc="${esc(id)}">${inner}</a>`;
function catFind(id){         // 정확 일치 우선, 아니면 유일 prefix (resolve와 동형)
  const r = catalog.find(x => x.id === id);
  if (r) return r;
  const c = catalog.filter(x => x.id.startsWith(id + "-"));
  return c.length === 1 ? c[0] : null;
}
/* ---- 축약 번호(`REQ-028`) 풀기 (REQ-20260828-021) ----

   사람은 대화에서 `REQ-028` 로 식별한다 — "가장 최근 날짜의 28번째" 라는 뜻을
   암묵적으로 쓴다. 그 뜻을 코드로 옮길 때 기준시각을 **렌더하는 지금**으로
   잡으면 안 된다: 이 저장소의 축약 언급에 그 규칙을 대 보면 셋 중 둘이 다른
   문서로 풀린다. 하루에 29~91건씩 발번되므로 **스크롤백이 하루도 못 버틴다.**

   그래서 기준시각은 **그 글이 쓰인 때**다. (종류, 날짜, 번호) 중복이 카탈로그에
   0건이라 임의 시각 t 에 대해 "t 이전에 생긴 그 번호 중 최신"은 언제나
   유일하고, **시간에 대해 고정된다** — 내일 새 문서가 생겨도 오늘 쓴 줄의
   해석이 바뀌지 않는다.

   `bin/s9` 의 `resolve_short()` 와 **같은 규칙**이다. 두 벌이 있는 것은
   좋지 않아서, 아래 CC_SHORT_VECTORS 를 두 엔진이 함께 통과해야 하는
   계약서로 박아 뒀다 (tests/test_short_ref.py 가 이 표를 읽어 서버를
   검사하고, `?shortref` 가 같은 표로 화면을 검사한다). */
