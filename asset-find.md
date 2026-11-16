---
title: asset-find
status: next
priority: normal
created: 2026-11-16
---

Asking the asset graph for one asset of a type takes four lines everywhere it's done: `assemble(...)`, filter by `isinstance`, raise if empty, take `[0]`. It's written out four times in `workflows/gatk_data_preprocessing.py` and `workflows/scrna_clustering.py` (read 2026-11-16), and again in the tutorials. A classmethod beside `Asset.store` (ticket [[lean-task-bodies]]) says it in one:

```python
ref = await Reference.find(build="GRCh38")
r2 = await R2.find(sample_id=sample_id, required=False)
```

It's also the line to lead with when showing someone a workflow.

## Plan

- [ ] `Asset.find(required=True, **filters)`: `assemble(asset=cls._asset_key, **filters)`, the newest match, raising `ValueError` naming the type and the filters when there's none and it's required. To settle: whether more than one match is an error or newest-wins, as the workflows do today.
- [ ] `Asset.find_all(**filters) -> list[Self]` for the typed list.
- [ ] The workflows, the Workflows tutorial and `docs/guides/writing-a-workflow.md` use them. `assemble()` stays for mixed-type queries.
- [ ] `docs/architecture/types.md` → Assembly.

Related: [[board]], [[lean-task-bodies]], [[sdk-front-door]].
