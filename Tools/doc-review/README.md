# doc-review

The public CLI controls the local review servers. Document comments, rendering,
and PR note exchange run through the review UI or agent workflows.

```bash
bash Tools/tools.sh documents doc-review preview start --project .
bash Tools/tools.sh documents doc-review preview status --project .
bash Tools/tools.sh documents doc-review preview list
bash Tools/tools.sh documents doc-review preview stop --project .
bash Tools/tools.sh documents doc-review servers --json
bash Tools/tools.sh documents doc-review stop --port 8765
```

`preview` manages persistent project feature previews. `servers` lists live
standalone review servers, and `stop` stops a standalone review server. The
underlying review tool remains available by direct path to skills and the UI;
see `Documentation/12_DocReview.md` for its review model.
