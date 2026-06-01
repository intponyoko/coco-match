# coco-match

Astro + React based lightweight SSG prototype for the approval-style HITL workflow.

## Commands

```bash
bun install
bun run check
bun run build
bun run dev
```

`bun run dev`, `bun run build`, and `bun run check` automatically generate
`data/sample/*.csv` on first run when missing, then export
`public/data/app-data.json`.

The app reads `public/data/app-data.json`, generated from repository-level
`data/sample` CSV files. You can still run `bun run export:data` manually when
you want to refresh the exported browser payload only. The initial demo state
intentionally starts without
downstream planning tables; Theme/Solution, Project/Request, preferences, and
matching results are populated by HITL pipeline API calls and stored only in
browser state/localStorage in this prototype.

## Pages

- `/` - workflow inbox and progress
- `/sales-plan` - executive SalesPlan approval
- `/theme-solutions` - department Theme/Solution approval
- `/project-requests` - department Project Scale/Request approval
- `/project-interest` - individual project interest declaration
- `/matching` - department matching review
- `/pipeline` - admin pipeline execution and debug
- `/audit` - local approval audit log
