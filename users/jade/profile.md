---
name: jade
role: admin
display: Jade Kwon
registered: 2026-08-29T15:54:20+09:00
registered_on: eek-p620
os_accounts: ["jade"]
emails: ["jade@elementenergy.com"]
github: jade-jimi
github_org: jade-jimi
---

## Notes
- 2026-08-29T16:18:59+09:00 config agent_cli=t3-codex (by jade)
- 2026-08-29T16:25:52+09:00 updated emails(1), github, github_org (by jade)
- 2026-08-29T22:08:55+09:00 config pref_home_credentials=For Bitbucket/Jira release work, use the authorized credential source in Jade home (currently /home/jade/.bitbucket_creds). Never copy secret values into repositories, work orders, reports, logs, chat, or remote hosts; reference only the path and capability. Production merges remain Jade-only. (by jade)
- 2026-08-31T10:06:49+09:00 config pref_deep_details_model=Deep details should default to a lower-cost model: Codex gpt-5.6-terra with medium reasoning or Claude Fable with medium effort. Escalate to a stronger model only when the first pass records missing evidence or high-risk ambiguity. Save the question, repo, branch, provider/model, evidence time, result, and report path. (by jade)
- 2026-08-31T10:07:25+09:00 config pref_deep_details_model=Deep details default to Codex gpt-5.6-terra with medium reasoning when Codex is selected. When Claude is selected, use Claude Opus (the configured Opus model) with medium effort, not Fable. Save the question, repo, branch, provider/model, evidence time, result, and report path. Escalation from Codex Terra to a stronger model requires a recorded evidence gap or high-risk ambiguity. (by jade)
- 2026-08-31T10:08:40+09:00 config pref_deep_details_model=Deep details default to Codex gpt-5.6-terra with medium reasoning when Codex is selected. When Claude is selected, use claude-fable-5 with medium effort; in Jade current T3 stack Fable 5 is the default top Claude choice. Save the question, repo, branch, provider/model, evidence time, result, and report path. Escalate only when the first pass records an evidence gap or high-risk ambiguity. (by jade)
- 2026-08-31T10:18:36+09:00 config pref_deep_details_model=Deep details default to cheaper models: Codex gpt-5.6-terra medium; Claude claude-sonnet-5 medium. Use claude-fable-5 only for explicit escalation on contradictory evidence or high-risk decisions. Always save question/repo/branch/provider/model/evidence time/result/report path. (by jade)
- 2026-08-31T10:19:10+09:00 config pref_deep_details_provider=Default Deep details provider is Codex (gpt-5.6-terra medium). Claude Sonnet 5 medium is an optional fallback; never auto-start either provider merely by opening ticket details. (by jade)
- 2026-08-31T22:08:10+09:00 config pref_presentation_output=Default completed-work presentations to PowerPoint (.pptx) plus HTML companion; always use /home/jade/EE the.thmx actual slide master/layouts. (by jade)
- 2026-08-31T22:09:10+09:00 config pref_presentation_visuals=Completed-work presentations should include evidence-backed plots, diagrams, timelines, screenshots, or before/after graphics appropriate to the work; never invent numbers or decorative charts. (by jade)
