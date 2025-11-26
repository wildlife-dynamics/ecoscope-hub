# Ecoscope Hub

This repository provides a set of tools for development on ecoscope workflows.


## Development Environment Setup

### Prerequisites: Install Pixi

Install pixi package manager by following the instructions at https://pixi.sh/latest/installation/

**macOS/Linux:**
```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

After installation, restart your terminal or source your shell configuration.

### Create Your Development Configuration

Copy the base configuration to create your personal development setup:

```bash
cd environment-setup
cp pixi-base.toml pixi.toml
```

This allows you to customize dependencies, versions, and platforms without affecting the base configuration. Note that pixi.toml and pixi.lock in this folder are not tracked by git and will NOT affect global settings

### Initialize the Environment

Activate the pixi environment using one of these methods:

#### Option A: Interactive Shell
```bash
pixi shell
```

This starts a new shell with the environment activated. The activation script will:
- Register graphviz plugins (required for workflow visualization)
- Install playwright chromium browser (required for testing)

*Tips: When to use `pixi shell`:*
- First time setup or testing the environment
- When you want an isolated shell session with the environment
- When you want a clean exit from the environment (just type `exit`)

#### Option B: Shell Hook (for existing shell)
```bash
eval "$(pixi shell-hook)"
```

This activates the environment in your current shell session without starting a new shell.

*Tips: When to use `pixi shell-hook`:*
- When you want to maintain the existing environment setup, e.g. environment variables, shell aliases, function or other customization that would be lost in a new shell

*Tips: Setting up a shell function for easier activation:*

You can add a bash function to your `~/.bashrc`, `~/.bash_profile`, or `~/.zshrc` to make activation easier. With the `--manifest-path` option, you can specify which environment to activate:

**For Bash/Zsh:**
```bash
function pixi_activate() {
    # default to current directory if no path is given
    local manifest_path="${1:-.}"
    eval "$(pixi shell-hook --manifest-path $manifest_path)"
}
```

After adding this function to your shell configuration file, restart your terminal or source the file. You can then activate the environment by running:

```bash
# Activate environment in current directory
pixi_activate

# Or activate with a specific manifest path
pixi_activate <path_to_env_setup>
```

### Customize Your Development Environment

Edit `pixi.toml` to customize your setup:


#### Adjust Platform Support

By default, the environment supports multiple platforms. To speed up solves, comment out platforms you don't need:

```toml
platforms = [
    # "linux-64",      # Uncomment if needed
    "osx-arm64",
    # "osx-64",      # Uncomment if needed
    # "win-64",      # Uncomment if needed
]
```

#### Change Package Versions

The ecoscope-workflows SDK evolves rapidly. The most common configuration changes involve updating the core version and task library versions. These can be found in the `[dependencies]` section under the `# Task libraries` comment.

**Update to a specific version:**

```toml
# Bump to a newer version range
ecoscope-workflows-core = ">=0.19.0,<0.20.0"
```

**Use a local editable package for development:**

When actively developing a package, you can make it editable:

```toml
[pypi-dependencies]
ecoscope-workflows-ext-custom = { path = "/path/to/local/package", editable = true }
```

**Important:** Remove any duplicate package definitions from the `[dependencies]` section to avoid conflicts.

**Use a local build of a package:**

For testing locally built packages before publishing:

1. Uncomment the local channel in the `[project]` section:

```toml
channels = [
    # Uncomment the following lines to use local channels for development
    "file:///tmp/ecoscope-workflows/release/artifacts/",
    "file:///tmp/ecoscope-workflows-custom/release/artifacts/",
    "https://repo.prefix.dev/ecoscope-workflows/",
    "https://repo.prefix.dev/ecoscope-workflows-custom/",
    "conda-forge",
]
```

2. Specify the local channel in the dependency definition:

```toml
# Task libraries: use local build
ecoscope-workflows-ext-custom = { version = "*", channel = "file:///tmp/ecoscope-workflows-custom/release/artifacts/" }
```

#### Update the Environment

After modifying `pixi.toml`, reinstall the environment in the current directory:

```bash
# Update using your custom configuration
pixi install

# Check if the package version is updated correctly
pixi list
```

## Activation Script

The environment includes an activation script (`dev/activate.sh`) that runs automatically when you activate the environment. It performs:

1. Graphviz plugin registration (`dot -c`)
2. Playwright browser installation

### Troubleshooting

#### Environment Changes Not Taking Effect

If your configuration changes aren't being applied, try cleaning up the cache manually:

```bash
rm -rf .pixi
rm -rf pixi.lock
pixi cache clean
```

Then reinstall the environment with:

```bash
pixi install
```


#### Graphviz "Format not recognized" Error

If you see: `Format: 'png' not recognized. Perhaps 'dot -c' needs to be run`

Solution:
```bash
dot -c
```

The activation script should handle this automatically, but you can run it manually if needed.

#### Playwright Browser Issues

If playwright tests fail with browser errors:

```bash
playwright install --with-deps chromium
```

#### Environment Conflicts

If you encounter dependency conflicts:

1. Check your `pixi.toml` for version constraints
2. Try removing the lock file and reinstalling:
   ```bash
   rm pixi.lock
   pixi install
   ```

## Development Tips

1. **Keep `pixi-base.toml` unchanged**: This is the base configuration. Make all customizations in `pixi.toml`
2. **Use version ranges**: For development, use version ranges like `">=0.18.0,<0.19.0"` to get updates within a major version
3. **Editable packages**: Use `editable = true` for packages you're actively developing
4. **Platform-specific solves**: Limit platforms to speed up dependency resolution
