# publish

Publishes an explicitly reviewed Git change through a resumable CLI. The JSON
request names the checkout, branch, expected HEAD, base branch, exact files,
commit message, PR title, and a Markdown body file. See
`Documentation/17_Publishing.md` for the request format and workflow.

```bash
bash Tools/tools.sh project publish check --request /absolute/request.json
bash Tools/tools.sh project publish status --request /absolute/request.json
bash Tools/tools.sh project publish publish --request /absolute/request.json
```

`check` and `status` inspect prerequisites and progress without publishing.
`publish` validates the request, stages only listed files, commits, pushes,
and creates or updates the PR as needed. It uses Git and GitHub CLI (`gh`),
and records progress so an interrupted run can resume. Review the request and
body file before invoking `publish`; this command changes the repository and
remote PR state.
