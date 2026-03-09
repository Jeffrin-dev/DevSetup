# DevSetup Plugin Directory

Plugins are loaded from `~/.devsetup/plugins/` at runtime.

## Plugin Rules (Architecture Rule 7)

- Plugins **cannot** modify core DevSetup modules.
- Plugins **can only** register new tools or environments.
- Plugin failures **must not** crash DevSetup.
- Each plugin is a Python module exposing a `register(registry)` function.

## Example Plugin

```python
# ~/.devsetup/plugins/my_tool.py

def register(registry):
    from devsetup.installers.base import BaseInstaller

    class MyToolInstaller(BaseInstaller):
        tool_name = "mytool"

        def detect(self):
            import shutil
            return shutil.which("mytool") is not None

        def install(self):
            pass  # OS-specific logic goes here

        def version(self):
            return "1.0.0"

    registry["mytool"] = MyToolInstaller
```
