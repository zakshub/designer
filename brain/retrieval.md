# Retrieval and skills

Use retrieve QUERY --domain DOMAIN --platform PLATFORM with optional --audience and --limit.

The engine validates the graph, filters current approved knowledge and dependencies, matches domain/platform (and audience if supplied), then ranks by query-token overlap, confidence and stable ID. No matches returns an empty list.

Results contain the claim, context, revision, confidence rationale, trust, limitations, supporting/counterevidence, source provenance and approved conflicts. Conflicts include both claims and their current status. Stale conflicts remain historical dissent.

use-skill ID returns current instructions, knowledge, evidence, sources and conflicts. It does not execute external tools. A skill becomes stale when supporting knowledge changes.

Expiry is checked on every query, even before a sweep. Reading never raises confidence. Lexical retrieval is deliberately inspectable; semantic recall must be evaluated on a real corpus before adoption.
