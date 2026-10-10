// Check each ticket's frontmatter: the required fields with known values, and
// byte-identical after Obsidian's own parse and rewrite (yaml.stringify with
// the options processFrontMatter passes), so a card drag changes only the
// line it means to.
const fs = require("fs");
const path = require("path");
const YAML = require("yaml");

const STATUSES = ["backlog", "next", "doing", "review", "done"];
const PRIORITIES = ["high", "normal", "low"];
const problems = [];

for (const file of process.argv.slice(2)) {
  const text = fs.readFileSync(file, "utf8");
  const m = text.match(/^---\n([\s\S]*?)---\n/);
  if (!m) {
    problems.push(`${file}: no frontmatter`);
    continue;
  }
  let fm;
  try {
    fm = YAML.parse(m[1]);
  } catch (e) {
    problems.push(`${file}: ${e.message}`);
    continue;
  }
  const rewritten = YAML.stringify(fm, null, { nullStr: "", lineWidth: 0, aliasDuplicateObjects: false });
  if (rewritten !== m[1]) problems.push(`${file}: Obsidian would rewrite the frontmatter as:\n${rewritten}`);
  if (typeof fm.title !== "string" || !fm.title) problems.push(`${file}: title is missing`);
  if (!STATUSES.includes(fm.status)) problems.push(`${file}: status must be one of ${STATUSES.join(", ")}`);
  if (!PRIORITIES.includes(fm.priority)) problems.push(`${file}: priority must be one of ${PRIORITIES.join(", ")}`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fm.created)) problems.push(`${file}: created must be YYYY-MM-DD`);
  for (const slug of fm.blocked_by ?? []) {
    if (!fs.existsSync(path.join(path.dirname(file), `${slug}.md`))) problems.push(`${file}: blocked_by names no ticket ${slug}`);
  }
}
for (const p of problems) console.log(p);
process.exit(problems.length ? 1 : 0);
