# raisin_seed

This is a meta-package for syncing `raisin` development environments.

Seed files capture the exact git state of every repository inside `raisin_master/src`. Use them to freeze your workspace and recreate it later.

## Snapshot the current workspace

```
cd /home/chh-railab/raisin_master/src/_raisin_seed
python3 make_seed.py [seed_name]
```

- `seed_name` is optional; defaults to `repositories`.
- Output YAML lives in `_raisin_seed/config/seeds/<seed_name>.yaml`.
- The script prints pending changes and asks for confirmation before writing.

## Recreate the workspace

```
cd /home/chh-railab/raisin_master/src/_raisin_seed
python3 plant_seed.py [seed_name]
```

- Reads the matching YAML in `_raisin_seed/config/seeds`.
- Shows the actions it will take; press `y` to proceed.
- Each repo is cloned or fast-forwarded to the recorded branch/commit and hard reset to ensure reproducibility.

Keep the seed files under version control so teammates can bootstrap their environments with confidence.

## Snapshot VS Code + shell settings

```
cd /home/chh-railab/raisin_master/src/_raisin_seed
bash copy_settings.sh
```

- Saves `.vscode/c_cpp_properties.json`, `.vscode/settings.json`, and the `_raisin_seed` block from `~/.bashrc` into `_raisin_seed/config/settings/`.
- Fails fast if expected files are missing, so you know your snapshot is complete.

## Apply saved settings on a new machine

```
cd /home/chh-railab/raisin_master/src/_raisin_seed
bash paste_settings.sh
```

- Restores the VS Code configuration files and updates `~/.bashrc` with the stored snippet (any previous `_raisin_seed` block is replaced).
- Combine this with `plant_seed.py` to fully recreate both repositories and editor/shell configuration.