# Tools

These tools are for refreshing the public KIM Skill from local private material.

## `public_safe_wechat_stats.py`

Streams JSON/JSONL chat exports and emits aggregate-only statistics:

- message counts and time windows
- self-authored text counts
- style ratios
- anonymous chat rank/count tables
- curated domain and signal counts
- optional post-cutoff summary

It never writes raw message text, chat IDs, sender IDs, account IDs, or automatically extracted n-grams.

Example:

```powershell
python .\tools\public_safe_wechat_stats.py `
  --input "..\Data\wechat-export-full" `
  --output ".\ZH\references\research\summary.generated.json" `
  --self-id "<local-self-id>" `
  --post-cutoff "2026-06-20T23:47:17"
```

If the input is already filtered to only your own messages, use `--assume-all-self` instead of `--self-id`.

Before committing generated output, run a local privacy scan for account IDs, room IDs, private names, and any raw-message field names over the Markdown content.
