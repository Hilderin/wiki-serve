# Wiki Search Agent Rules

When using wiki-serve tools:

- Use `wiki_search` for conceptual or fuzzy questions about the project
- Use `wiki_search_exact` for exact terms, ADR numbers, file names, class names
- Use `wiki_read_section` when a search result excerpt is insufficient
- Always cite file path, heading path, and line range
- Do not modify specs/ADRs without first searching for existing content
- Prefer small, targeted searches over large queries
- If the index seems stale, run `wiki_status` then `wiki_reindex` with `changed-only`
