# mermaid-preview

Compatibility command for rendering local Mermaid `.mmd` files to one static
HTML page. It forwards to `doc-review serve --static`; use `doc-review`
directly for live review and comments.

```bash
python3 Tools/mermaid-preview/mermaid_preview.py diagram.mmd
python3 Tools/mermaid-preview/mermaid_preview.py one.mmd two.mmd --output /tmp/preview.html
```

By default the page is `_mermaid_preview.html` beside the first input file.
`--open` asks the operating system to open the result. The output contains a
tab for each input diagram. This command does not change source diagrams.
