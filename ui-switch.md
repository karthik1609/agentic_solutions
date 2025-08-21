### Switch Between Forked and Upstream Magentic-UI

Use these commands to swap the Magentic-UI dependency between your fork and the upstream PyPI release. Commands assume you are in the project root and using `uv`.

### Prerequisites
- `uv` is installed and this project was set up with `uv sync`.

### Switch to your forked Magentic-UI
```bash
uv remove magentic-ui
uv add "magentic-ui @ git+https://github.com/karthik1609/magentic-ui.git" --rev 59f0ce4 
# uv add "magentic-ui @ git+https://github.com/karthik1609/magentic-ui.git" --rev 5e53323
uv lock
uv sync
```

### Revert to upstream (PyPI) Magentic-UI
```bash
uv remove magentic-ui
uv add magentic-ui
uv lock
uv sync
```

If you are using the fork to serve a custom frontend, ensure the built UI assets are packaged under:
```
<venv>/site-packages/magentic_ui/backend/web/ui/
```
so that `index.html` is available at runtime.

to change to flavoured magentic

uv remove magentic-ui
uv add "magentic-ui @ git+https://github.com/karthik1609/magentic-ui.git" --rev 6e09881
uv lock
uv sync

to revert

uv remove magentic-ui
uv add magentic-ui
uv lock
uv sync