# docs-export

Copies a `Documentation/` folder into Confluence-ready Markdown. It turns
Obsidian wikilinks into readable labels, drops repository source-link lines,
and removes the navigation footer. Input pages are left untouched.

```bash
bash Tools/tools.sh documents docs-export Documentation
bash Tools/tools.sh documents docs-export Documentation --out /tmp/confluence-export
```

The default output is `GitIgnoreConfluenceExport/` beside the input folder.
The command exits with an error when the input contains no Markdown pages.
Review the output before importing it into Confluence; internal wikilink
targets are converted to text, not live Confluence links.
