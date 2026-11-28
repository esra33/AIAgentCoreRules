# deimagify

Caches an agent-written Markdown description of an image or PDF by SHA-256 of
the file bytes. The agent reads and describes the source; this tool only stores
and retrieves that description. Identical bytes share a cache entry even when
the file moves. Changed bytes produce a cache miss.

```bash
bash Tools/tools.sh documents deimagify check path/to/image.png
bash Tools/tools.sh documents deimagify store path/to/image.png --from description.md
bash Tools/tools.sh documents deimagify store path/to/image.png --from -
bash Tools/tools.sh documents deimagify list
bash Tools/tools.sh documents deimagify forget path/to/image.png
```

The cache is `~/.claude/deimagify-cache/`: `<hash>.md` descriptions and an
`index.json` for listing. Mermaid code fences are also extracted to
`<hash>.mmd` for preview. `forget` removes the entry for the file's current
content hash. No source image or PDF is modified.
