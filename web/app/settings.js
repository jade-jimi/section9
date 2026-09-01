/* settings.js — Settings 탭 — 표시/계정/사용자 구획과 머신 이력 */
"use strict";
/* ---------------- users 탭 (계정/프로필/개인화) ---------------- */
let selectedUser = null;

// admin 대리 모드(asUser)면 쓰기 본문에 as 를 첨부 — 그 외 신원 파라미터는 보내지
// 않는다 (actor 는 서버 whoami 파생, REQ-20260824-027)
const withAs = body => asUser ? {...body, as: asUser} : body;

// 쓰기 공통 — 결과 객체 반환 (팝업 없음). 인라인 표시가 필요한 폼은 이걸 직접 쓴다.
async function postJSONRaw(url, body){
  try{
    const r = await fetch(url, {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(withAs(body))});
    const d = await r.json();
    if (!d.ok) return {ok: false, refused: true, error: d.error || `HTTP ${r.status}`};
    // 서버가 실어 보낸 답을 그대로 넘긴다 — `{ok:true}` 만 돌려주면 부르는 쪽이
    // **서버가 판정한 사실을 못 본다**. 비밀을 바깥에 넣었을 때 "그 값은 안쪽에
    // 가려 쓰이지 않는다"가 응답에만 있고 화면에는 안 나오는 일이 실제로 있었다.
    return {ok: true, ...d};
  }catch(e){ return {ok: false, error: "서버에 연결할 수 없습니다"}; }
}

async function postJSON(url, body){
  const res = await postJSONRaw(url, body);
  if (!res.ok)
    s9dlg({kind:"alert", cap:res.refused ? "거부" : "연결",
      title:res.refused ? "서버가 거절했습니다" : "서버에 닿지 못했습니다",
      desc:String(res.error || ""), ok:"닫기"});
  return res.ok;
}

let settingsSection = "display";  // display | account | worker | users | about

async function renderSettings(){
  // 같은 값은 같은 문을 지난다 (REQ-20260828-039) — 여기서만 조용히 빈 목록으로
  // 물러나면 "등록된 사용자가 없다" 는 거짓말이 화면에 선다.
  await loadUsers();
  const data = {users: window.__users || []};
  updateProfileBadge();
  const me = getMe();   // 서버 파생 whoami (미등록이면 "")
  const meAdmin = isAdmin();
  const myMiss = me ? profileMissing((data.users || []).find(x => x.name === me)) : [];
  const SECTIONS = [
    ["display", "디스플레이", "스킨·톤·밀도 (내 계정에 저장)"],
    ["account", "내 계정", me
      ? `@${me} 프로필·개인화${myMiss.length ? ` ⚠ 미기재 ${myMiss.length}` : ""}`
      : "미등록 계정"],
    /* 「무인 작업」은 나 → 나 → 남 → 전체 순서의 둘째 자리다 (REQ-20260901-022).
       「내 계정」 안에 아홉째 덩이로 얹지 않는 이유는 캡처가 근거다: 그 판은
       이미 덩이 여덟에 세로 1,400px 를 넘고, 「내가 누구인가」와 「내가 없을 때
       무엇이 일어나는가」를 한 스크롤에 섞게 된다.
       부제는 상태를 겸한다 — 목록만 봐도 열려 있는 문이 보인다. */
    ["worker", "무인 작업", workerNavSub(
      me ? (data.users || []).find(x => x.name === me) : null)],
    ["users", "사용자 관리", meAdmin ? "등록·역할·시점 미리보기 (admin)" : "admin 전용"],
    ["about", "시스템", "저장소·통계·문서 안내"],
  ];
  $("#count").textContent = `Settings — ${me ? "@"+me : "미등록 계정"}`;
  const nav = SECTIONS.map(([k, label, sub]) =>
    `<div class="row${k===settingsSection?" sel":""}" data-sset="${k}">
      <div>${esc(label)}</div><div class="path">${esc(sub)}</div></div>`).join("");
  $("#view").innerHTML = `<div class="docs">
    <div class="doclist"><div class="grp">설정</div>${nav}
      <a class="row" href="/guide.html" target="_blank" style="display:block;text-decoration:none"><div>가이드 열기</div><div class="path">/guide.html — 사용자 안내서</div></a></div>
    <div class="viewer" id="sview"></div></div>`;
  renderSettingsSection(meAdmin);
}

function renderSettingsSection(meAdmin){
  const v = $("#sview");
  if (!v) return;
  document.querySelectorAll("[data-sset]").forEach(el =>
    el.classList.toggle("sel", el.dataset.sset === settingsSection));
  const me = getMe();
  if (settingsSection === "display"){
    const cur = {};
    UI_DIMS.forEach(d => cur[d.attr] = document.documentElement.dataset[d.attr] || d.def);
    const rows = UI_DIMS.map(d => `<tr><td>${esc(d.label)}</td><td>
      <select class="uf" data-dim="${d.attr}">
        ${d.opts.map(([val,txt]) => `<option value="${esc(val)}"${val===cur[d.attr]?" selected":""}>${esc(txt)}</option>`).join("")}
      </select></td></tr>`).join("");
    v.innerHTML = `<h1 style="margin:0 0 4px">디스플레이</h1>
      <div class="path">${me ? `@${me} 계정에 저장 — 다른 기기에서도 적용됩니다.` : "미등록 계정 — s9 user add 로 등록하면 계정에 저장되어 기기 간 동기화됩니다. 지금은 이 브라우저에만 저장."}</div>
      <table class="metatbl">${rows}</table>
      <div class="path">skin은 화면의 구조와 형태, tone은 색, density는 여백을 바꿉니다. 세 축은 자유롭게 조합되고 변경 즉시 적용됩니다.</div>`;
    // 각 select에 change 바인딩 — render() 없이 값만 적용(재렌더로 select 파괴되던 버그 수정).
    // skin/density는 다른 탭 레이아웃에 영향 → Settings에 머무는 동안엔 즉시 CSS 반영으로 충분.
    v.querySelectorAll("select[data-dim]").forEach(sel => {
      sel.addEventListener("change", async () => {
        const d = UI_DIMS.find(x => x.attr === sel.dataset.dim);
        await setUIDim(d, sel.value);
      });
    });
  } else if (settingsSection === "account"){
    if (!me){ v.innerHTML = `<p class="empty">이 OS 계정(${esc((window.__whoami||{}).user||"?")})은 미등록입니다 — 터미널에서 <code>s9 user add ${esc((window.__whoami||{}).user||"&lt;이름&gt;")}</code> 으로 등록하세요. 다른 이름의 기존 계정에 연결하려면 <code>s9 user attach &lt;이름&gt;</code>.</p>`; return; }
    const u = (window.__users||[]).find(x => x.name === me);
    // 못 받아 왔을 때 빈 판을 두면 "설정이 사라졌다"로 읽힌다 — 서버가 목록을
    // 안 준 것과 계정이 없는 것은 다른 일이고, 다시 시도할 손잡이를 줘야 한다.
    if (u) showUserForm(u, v, false);
    else v.innerHTML = `<p class="empty">계정 정보를 받아오지 못했습니다.
      <button class="gefix" type="button" id="uf-retry">다시 불러오기</button></p>`;
    const rt = $("#uf-retry");
    if (rt) rt.addEventListener("click", () => renderSettings());
  } else if (settingsSection === "worker"){
    if (!me){ v.innerHTML = `<p class="empty">이 OS 계정(${esc((window.__whoami||{}).user||"?")})은 미등록입니다 — 터미널에서 <code>s9 user add ${esc((window.__whoami||{}).user||"&lt;이름&gt;")}</code> 으로 등록하세요.</p>`; return; }
    const wu = (window.__users||[]).find(x => x.name === me);
    // 못 받아 온 것과 계정이 없는 것은 다른 일이다 (「내 계정」과 같은 손잡이).
    if (wu) showWorkerCfg(wu, v);
    else v.innerHTML = `<p class="empty">계정 정보를 받아오지 못했습니다.
      <button class="gefix" type="button" id="uf-retry">다시 불러오기</button></p>`;
    const wrt = $("#uf-retry");
    if (wrt) wrt.addEventListener("click", () => renderSettings());
  } else if (settingsSection === "users"){
    if (!meAdmin){ v.innerHTML = `<p class="empty">사용자 관리는 admin만 가능합니다. (whoami=${esc((window.__whoami||{}).user||"?")})</p>`; return; }
    const list = (window.__users||[]).map(u => `<div class="urow" data-uname="${esc(u.name)}">
        <span class="st">${esc(u.role)}</span> <b>${esc(u.display||u.name)}</b>
        <span class="path">@${esc(u.name)} · ${esc((u.registered||"").slice(0,10))}</span>${
          profileMissing(u).length ? `<span class="pbadge" title="프로필 미기재: ${esc(profileMissing(u).join(" · "))}">⚠</span>` : ""}</div>`).join("");
    // 못 받은 목록을 "등록된 사용자가 없다" 로 그리지 않는다 (REQ-20260828-039)
    v.innerHTML = `<h1 style="margin:0 0 10px">사용자 관리</h1>`
      + (supplyLost("users") ? supplyLine("users", "사용자 목록")
                             : `<div class="ulist">${list}</div>`)
      + `
      <div class="cfg-h">새 사용자 등록</div>
      <div class="uform" style="max-width:340px">
        <input id="nu-name" type="text" placeholder="계정명 (영문/숫자/._-)">
        <input id="nu-display" type="text" placeholder="표시 이름 (선택)">
        <input id="nu-email" type="text" placeholder="email (선택)">
        <select id="nu-role"><option value="member">role: member</option>
          <option value="viewer">role: viewer</option><option value="admin">role: admin</option></select>
        <button id="nu-add">＋ 등록</button>
      </div>
      <div class="cfg-h">시점 미리보기 / 대리 (admin)</div>
      <div class="path">다른 사용자의 화면(열람 격리)을 그대로 보고, 그 사용자로 조작합니다. 저장되지 않으며 이 화면에서만 유효합니다.</div>
      <select id="as-user" class="uf">
        <option value="">(내 시점 — 미리보기 해제)</option>
        ${(window.__users||[]).filter(x => x.name !== me).map(x =>
          `<option value="${esc(x.name)}"${x.name===asUser?" selected":""}>@${esc(x.name)} [${esc(x.role)}] 시점으로 보기</option>`).join("")}
      </select>
      <div id="uedit" style="margin-top:20px"></div>`;
    $("#as-user").addEventListener("change", e => {
      asUser = e.target.value;
      onViewerChanged();
    });
    $("#nu-add").addEventListener("click", async () => {
      const name = $("#nu-name").value.trim();
      if (!name){
        s9dlg({kind:"alert", cap:"입력",
          title:"계정명을 적어 주세요",
          desc:"터미널에서 s9 를 쓸 때 이 이름으로 불립니다.", ok:"닫기"});
        $("#nu-name").focus(); return;
      }
      if (await postJSON("/api/user/add", {name, display: $("#nu-display").value.trim(),
          email: $("#nu-email").value.trim(), role: $("#nu-role").value}))
        renderSettings();
    });
    v.querySelectorAll("[data-uname]").forEach(el => el.addEventListener("click", () => {
      const u = (window.__users||[]).find(x => x.name === el.dataset.uname);
      if (u) showUserForm(u, $("#uedit"), true);
    }));
  } else if (settingsSection === "about"){
    const c = catalog;
    const byType = {}, byStatus = {};
    c.forEach(r => { byType[r.type]=(byType[r.type]||0)+1;
      if(r.type==="request") byStatus[r.status]=(byStatus[r.status]||0)+1; });
    v.innerHTML = `<h1 style="margin:0 0 10px">시스템</h1>
      <table class="metatbl">
        <tr><td>저장소</td><td class="path">~/section9 (로컬 md + git 동기화)</td></tr>
        <tr><td>문서 수</td><td>${c.length} — request ${byType.request||0}, knowledge ${byType.knowledge||0}, session ${byType.session||0}</td></tr>
        <tr><td>요청 상태</td><td>${Object.entries(byStatus).map(([k,n])=>`${k} ${n}`).join(" · ")||"(없음)"}</td></tr>
        <tr><td>등록 사용자</td><td>${(window.__users||[]).map(u=>`@${esc(u.name)}[${esc(u.role)}]`).join(" ")||"(없음)"}</td></tr>
      </table>
      <div class="cfg-h">설계 문서</div>
      <div class="path" style="line-height:1.9">
        docs/00~11 (개요·포맷·인덱스·상태머신·검색·대시보드·audit·사용자·git·설치/인가·부트스트랩·Windows)<br>
        harness/README.md (멀티 하네스) · harness/claude/agents/README.md (에이전트 26종)<br>
        CLI: <code>s9 digest / ls / search --body / show / status / note / serve / shot</code>
      </div>
      <div class="cfg-h">이 대시보드</div>
      <div class="path" style="line-height:1.9">
        읽기 = 자유, 쓰기 = 상태 옮기기만(CLI와 동일 함수 경유, History에 [via dashboard]).<br>
        탭/문서/설정 이동은 URL 해시로 기록되어 브라우저 뒤로가기·딥링크 지원.
      </div>`;
  }
}

/* ------- 머신·계정 이력 (REQ-20260827-066) -------
   서버가 `/api/users` 의 사용자마다 `machine_accounts` 를 준다: 어느 머신에서,
   어떤 운영체제로, 어떤 OS 계정으로 이 계정을 썼는지 + 처음 본 때 · 마지막 본 때.

   열 이름은 `OS 계정` 이 아니라 그냥 `계정` 이다 (2026-08-27 반려: "이 머신에
   nicehugepark 이라는 os 계정은 없다. 그냥 하네스 아이디를 내가 자주 쓰는 순수
   개인 아이디로서 정한거다"). 이 칸에는 그 머신의 OS 계정이 올 수도 있고 사람이
   정한 하네스 이름이 올 수도 있다 — 둘 중 하나라고 이름 붙이면 절반은 거짓말이
   된다. 화면이 모르는 것을 아는 척하지 않는다.

   화면의 일은 하나다 — **"지금도 쓰는 머신"과 "한 번 스쳐간 머신"을 가른다.**
   그 둘을 가르는 값이 first/last 이고, 그래서 둘을 나란히 둔다. 가르는 방법은
   색면이 아니라 세 가지다:
   ① 마지막으로 본 때 순으로 세운다 — 지금 쓰는 것이 맨 위다.
   ② 마지막 칸에 **경과**를 붙인다(카드가 쓰는 그 표기). "6d 12h" 는 날짜보다
      먼저 읽히고, 날짜를 머릿속에서 빼지 않아도 된다.
   ③ 하루가 넘은 줄은 잉크를 한 급 내린다 — 목록이 길어져도 위쪽 몇 줄이
      살아 있는 머신임이 먼저 보인다. 색상이 아니라 명도다.
   처음과 마지막이 같은 줄은 그 자리에서 **한 번**이라고 말한다 — 스쳐간 머신의
   가장 흔한 모습이고, 두 날짜를 눈으로 비교하게 만들 이유가 없다. */
const MACHINE_FRESH_MS = 24 * 60 * 60 * 1000;
const shortWhen = iso => (iso || "").slice(0, 16).replace("T", " ");
/* ?mh=demo|empty — 진단·헤드리스 캡처용 (?usagecard·?dlg·?ccjump 와 동형).
   지금 이 저장소에는 살아 있는 머신 줄만 있어서, 오래 안 쓴 머신과 빈 계정이
   어떻게 보이는지 손으로 확인할 길이 없다. 화면을 눈으로 못 보면 고칠 수도 없다. */
function machineDemo(rows){
  const m = /[?&]mh=([a-z]+)/.exec(location.search);
  if (!m) return rows;
  if (m[1] === "empty") return [];
  const ago = d => new Date(Date.now() - d * 86400000).toISOString();
  return rows.concat([
    {machine: "MACBOOK-AIR", os: "macOS", account: "sjpark", first: ago(9), last: ago(9)},
    {machine: "BUILD-BOX-02", os: "Linux", account: "runner", first: ago(31), last: ago(4)},
  ]);
}
function machineHistoryHTML(u){
  const rows = machineDemo((u.machine_accounts || []).slice())
    .sort((a, b) => (Date.parse(b.last || "") || 0) - (Date.parse(a.last || "") || 0));
  // 빈 것은 고장이 아니다 — 이 계정으로 세션을 연 적이 없을 뿐이다. 옛 프로필은
  // 정말로 비어 있으므로 표를 세우지 않고 한 줄로 이유를 말한다.
  if (!rows.length)
    return `<div class="cfg-h">머신·계정 이력</div>
      <p class="empty mhempty">이 계정으로 세션을 연 적이 없습니다.</p>`;
  const body = rows.map(r => {
    const t = Date.parse(r.last || "") || 0;
    const stale = !t || Date.now() - t > MACHINE_FRESH_MS;
    // 처음과 마지막이 같으면 같은 시각을 두 번 적지 않는다 — 그 자리에 무슨
    // 뜻인지를 적는다. 스쳐간 머신의 가장 흔한 모습이고, 두 날짜를 눈으로
    // 비교하게 만들 이유가 없다.
    const once = r.first && r.last && r.first === r.last;
    return `<tr class="${stale ? "stale" : ""}">
      <td class="mn">${esc(r.machine || "?")}</td>
      <td class="mo">${esc(r.os || "?")}</td>
      <td class="ma">@${esc(r.account || "?")}</td>
      <td class="mw">${esc(shortWhen(r.first))}</td>
      <td class="mw">${once ? `<span class="mone">한 번뿐</span>`
                            : esc(shortWhen(r.last))}
        <span class="mel">${esc(fmtElapsed(r.last))}</span></td></tr>`;
  }).join("");
  return `<div class="cfg-h">머신·계정 이력</div>
    <div class="mhwrap"><table class="mhtbl"><thead><tr>
      <th>머신</th><th>운영체제</th><th>계정</th><th>처음</th><th>마지막</th>
    </tr></thead><tbody>${body}</tbody></table></div>`;
}

