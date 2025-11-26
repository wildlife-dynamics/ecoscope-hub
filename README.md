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

>[!TIP]
>When to use `pixi shell`:
>- First time setup or testing the environment
>- When you want an isolated shell session with the environment
>- When you want a clean exit from the environment (just type `exit`)

#### Option B: Shell Hook (for existing shell)
```bash
eval "$(pixi shell-hook)"
```

This activates the environment in your current shell session without starting a new shell.

>[!TIP]
>When to use `pixi shell-hook`:
>- When you want to maintain the existing environment setup, e.g. environment variables, shell aliases, function or other customization that would be lost in a new shell

>[!TIP]
>Setting up a shell function for easier activation:
>You can add a bash function to your `~/.bashrc`, `~/.bash_profile`, or `~/.zshrc` to make activation easier. With the `--manifest-path` option, you can specify which environment to activate:
>```bash
> function pixi_activate() {
>    # default to current directory if no path is given
>    local manifest_path="${1:-.}"
>    eval "$(pixi shell-hook --manifest-path $manifest_path)"
>}
>```
>After adding this function to your shell configuration file, restart your terminal or source the file. You can then activate the environment by running:
>```bash
># Activate environment in current directory
>pixi_activate
>
># Or activate with a specific manifest path
>pixi_activate <path_to_env_setup>
>```

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

>[!NOTE]
>Remove any duplicate package definitions from the `[dependencies]` section to avoid conflicts.

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

### Activation Script

The environment includes an activation script (`dev/activate.sh`) that runs automatically when you activate the environment. It performs:

1. Graphviz plugin registration (`dot -c`)
2. Playwright browser installation

## Useful Commands for Development

>[!NOTE]
> After initializing the pixi environment as described above, navigate to your task library or workflow directory to run the commands below. Avoid running pixi commands from there, as they would use the local pixi environment configuration and slow down the development process

### Working with Task Libraries

Navigate to your task library repository before running these commands.

**Build your task library:**

Builds the conda package for distribution.

```bash
./publish/build.sh
```

**Type check your code:**

Runs mypy type checker on the package and tests.

```bash
cd src/<package_name>
mypy --package <package_name> --package tests --no-incremental
```

**Run tests:**

Executes the test suite for your task library.

```bash
pytest
```

### Working with Workflows

Navigate to your workflow repository before running these commands.

**Initialize graphviz (if needed):**

Ensures the dot executable is available for workflow visualization.

```bash
dot -c
```

**Compile workflow without installation:**

Compiles a workflow specification without installing dependencies. Useful for quick iterations during development.

```bash
ecoscope-workflows compile --spec <path_to_spec.yaml> --clobber --no-install
```

Options:
- `--spec`: Path to your workflow specification file
- `--clobber`: Overwrite existing compiled workflow
- `--no-install`: Skip dependency installation (faster for testing)

**Run the compiled workflow:**

Executes the workflow with specified configuration and execution mode.

```bash
cd ecoscope-workflows-<workflow_id>
python -m ecoscope_workflows_<workflow_id>.cli run \
  --config-file <path_to_param.yaml> \
  --execution-mode sequential \
  --no-mock-io
```

Options:
- `--config-file`: Path to your parameter configuration file
- `--execution-mode`: Choose between `sequential` or `async` execution. Always use `sequential` for now.
- `--no-mock-io` or `--mock-io`: Use mock I/O for testing without real data

## Troubleshooting

#### Environment Changes Not Taking Effect, Environment Conflicts or Task Not Found

If your environment changes aren't being applied, try cleaning up the cache manually:

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

## Development Tips

1. **Keep `pixi-base.toml` unchanged**: This is the base configuration. Make all customizations in `pixi.toml`
2. **Use version ranges**: For development, use version ranges like `">=0.18.0,<0.19.0"` to get updates within a major version
3. **Editable packages**: Use `editable = true` for packages you're actively developing
4. **Platform-specific solves**: Limit platforms to speed up dependency resolution
