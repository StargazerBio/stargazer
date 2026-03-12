- upload public assets for quickstart workflow to pinata
- update README with CLI quickstart and bump to alpha status
- interactive workflow for generating a DB from existing data in STARGAZER_LOCAL
- write a separate set of condensed context files for production use instead of dev
- setup a recurring docs sync job so they never go stale
- setup agentic PR process
- figure out how other folks can easily fork/PR
- more robust logging
  - tags per task to demux?
  - 1 logfile per workflow exec?
  - don't flush to stdout/err because it will all get tokenized and go to context
  - env var for log level and bool to log actual tool call output
- integrate marimo as the notebook experience
- need some sort of data-aware caching, Flyte caching is great but breaks down for keyword based workflows


- create stargazer org ✅
- setup GH pages ✅
- find a way to exhaustively link docs to code for agent traversal ✅