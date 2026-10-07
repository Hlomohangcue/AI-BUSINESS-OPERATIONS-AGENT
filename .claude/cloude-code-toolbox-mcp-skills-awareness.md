# Cloude Code ToolBox — MCP & Skills awareness

_Generated: 2026-10-06T16:45:09.276Z_

## How to use this report

- **Saved copy:** This file is **`.claude/cloude-code-toolbox-mcp-skills-awareness.md`** — refreshed whenever the toolbox runs an MCP & Skills scan (including on workspace open when auto-scan is enabled). It is meant for **Claude Code workspace context** together with `CLAUDE.md` (which gets a shorter replaceable summary when auto-merge is on).
- **MCP:** Lists **configured** servers from Claude Code config (`~/.claude.json` for user scope, `.mcp.json` for project scope). Use `/mcp` in the Claude Code panel to connect servers for your session.
- **Skills:** **On-disk** folders with `SKILL.md`. Claude Code does not auto-load them; attach `SKILL.md` or paths in chat when useful.
- **Task routing:** When the user’s request matches a server’s purpose (e.g. Confluence → Confluence/Atlassian MCP), prefer that **server id** from the tables below.

---

## MCP — workspace

Workspace `mcp.json` _(folder: ai-business-operations-agent)_

- **c:\Users\User\adk-workspace\ai-business-operations-agent\.mcp.json** — _File missing_

_No active workspace servers in mcp.json._

## MCP — user profile

- **C:\Users\User\.claude.json** — _File exists — no servers defined_

_No active user-scoped servers in mcp.json._

## Skills (local `SKILL.md` folders)

### Project-scoped

_None found (or no workspace open)._

### User-scoped

- **agents-sdk** — `C:\Users\User\.copilot\skills\agents-sdk`
  - Build, debug, or review Cloudflare Agents SDK applications using the agents package.

- **basin** — `C:\Users\User\.copilot\skills\basin`
  - Build and troubleshoot Cloudflare Basin analytics workflows with Basin Pipelines, Basin Catalog, and Basin SQL. Use for streaming data into R2 Iceberg tables, managing catalogs, or querying those tables; also use for req

- **cloudflare** — `C:\Users\User\.copilot\skills\cloudflare`
  - Discover and choose Cloudflare products for apps, APIs, AI agents, storage, networking, and security. Use for architecture and product selection, including when the user describes a need without naming a Cloudflare produ

- **cloudflare-email-service** — `C:\Users\User\.copilot\skills\cloudflare-email-service`
  - Implement or troubleshoot Cloudflare Email Sending and Email Routing integrations and their delivery configuration.

- **cloudflare-one** — `C:\Users\User\.copilot\skills\cloudflare-one`
  - Design, configure, troubleshoot, or review Cloudflare One Zero Trust and SASE deployments. Use cloudflare-one-migrations for migration planning from other vendors.

- **cloudflare-one-migrations** — `C:\Users\User\.copilot\skills\cloudflare-one-migrations`
  - Assess and plan migrations from existing VPN, SWG, or SASE platforms to Cloudflare One, including policy mapping, parity gaps, and rollout.

- **durable-objects** — `C:\Users\User\.copilot\skills\durable-objects`
  - Build, debug, or review Cloudflare Durable Objects code for persistent state and coordination.

- **k2** — `C:\Users\User\.copilot\skills\k2`
  - Build and troubleshoot Cloudflare K2 or K2 Streams durable logs. Use for stream setup, producing from Workers or HTTP, configuring retention and inputs, and consuming through subscriptions.

- **nextjs-on-cloudflare** — `C:\Users\User\.copilot\skills\nextjs-on-cloudflare`
  - Build, migrate, and deploy Next.js apps on Cloudflare Workers with vinext. Use when starting a Next.js project on Cloudflare, moving an existing app to Workers, choosing between vinext and OpenNext, or setting up vinext 

- **sandbox-migrate-to-next** — `C:\Users\User\.copilot\skills\sandbox-migrate-to-next`
  - Migrate Cloudflare Sandbox apps from stable @cloudflare/sandbox to @cloudflare/sandbox@next (SDK 1.0 preview). Use sandbox-next for apps already on the preview.

- **sandbox-next** — `C:\Users\User\.copilot\skills\sandbox-next`
  - Build or maintain Cloudflare Sandbox apps on @cloudflare/sandbox@next (SDK 1.0 preview). Use sandbox-migrate-to-next when porting a stable app.

- **sandbox-sdk** — `C:\Users\User\.copilot\skills\sandbox-sdk`
  - Build sandboxed applications for secure code execution. Load when building AI code execution, code interpreters, CI/CD systems, interactive dev environments, or executing untrusted code. Covers Sandbox SDK lifecycle, com

- **sandbox-stable** — `C:\Users\User\.copilot\skills\sandbox-stable`
  - Build or maintain Cloudflare Sandbox apps on the stable @cloudflare/sandbox package. Use sandbox-next for preview apps and sandbox-migrate-to-next for stable-to-preview migrations.

- **turnstile-spin** — `C:\Users\User\.copilot\skills\turnstile-spin`
  - Set up, repair, or migrate to Cloudflare Turnstile bot verification in an existing frontend and backend, including server-side Siteverify.

- **web-perf** — `C:\Users\User\.copilot\skills\web-perf`
  - Audit, diagnose, or optimize website loading and interaction performance, Core Web Vitals, and Lighthouse performance scores.

- **workers-best-practices** — `C:\Users\User\.copilot\skills\workers-best-practices`
  - Cloudflare Workers best practices for production applications. Use when writing, reviewing, or configuring Workers.

- **wrangler** — `C:\Users\User\.copilot\skills\wrangler`
  - Run or troubleshoot Wrangler CLI commands and configure Worker projects for local development, Previews, deployment, and Cloudflare resource management.

---

## Suggested next steps

- **MCP:** Use this extension’s hub **MCP** tab, or `claude mcp list` in the terminal. In Claude Code, use `/mcp` to connect servers for the session.
- **Edit config:** Open `~/.claude.json` (user MCP) or `<workspace>/.mcp.json` (project MCP) via the extension commands.
- **Refresh this report:** run **Intelligence — scan MCP & Skills awareness** again after changing MCP config or adding skills.

_Report from Cloude Code ToolBox extension._
