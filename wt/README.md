# wt - Ecoscope Workflow Management CLI

CLI tool for creating and managing ecoscope workflow repositories with automated setup for collaborators and branch protection.

## Features

- 🚀 **Create repositories from template** - Uses `wildlife-dynamics/wt-template`
- 👥 **Automatic collaborator management** - Add team members with specific roles
- 🔒 **Branch protection rules** - Automatically applies organization-wide protection rules
- 🎨 **Beautiful interactive UI** - Rich terminal experience with progress indicators
- 🔐 **Secure authentication** - Token storage with automatic expiration handling

## Installation

### Option 1: Install in existing pixi environment

Add to your `environment-setup/pixi.toml`:

```toml
[pypi-dependencies]
wt = { path = "../wt", editable = true }
```

Then install:

```bash
cd environment-setup
pixi install
```

### Option 2: Standalone installation

```bash
cd wt
pixi install
pixi run wt --help
```

## Authentication

The CLI supports multiple authentication methods (in priority order):

1. **Environment variable**: `GITHUB_TOKEN` or `GH_TOKEN`
2. **Interactive prompt**: CLI will ask for token and store it securely

### Creating a GitHub Token

1. Go to https://github.com/settings/tokens/new
2. Select scopes:
   - `repo` - Full control of private repositories
   - `admin:org` - Full control of organizations (if creating org repos)
3. Generate token and copy it

## Usage

### Create Repository (Interactive Mode)

```bash
wt create
```

Interactive mode will guide you through:
1. Repository name (must start with `wt-`)
2. Description
3. Public/Private visibility
4. Organization (or personal account)
5. Additional collaborators (you're added as admin by default)

### Create Repository (Non-Interactive Mode)

```bash
# Basic creation
wt create --name wt-my-workflow --description "My workflow"

# With organization
wt create --name wt-my-workflow --org wildlife-dynamics

# Public repository
wt create --name wt-my-workflow --public

# With collaborators
wt create --name wt-my-workflow --collaborators "alice:write,bob:read"

# Preview without creating
wt create --name wt-my-workflow --dry-run
```

### Command Options

```bash
wt create [OPTIONS]

Options:
  --name, -n TEXT              Repository name (must start with 'wt-')
  --description, -d TEXT       Short description of the workflow
  --private / --public         Repository visibility (default: private)
  --org, -o TEXT              Organization name (leave empty for personal)
  --collaborators, -c TEXT     Comma-separated: 'user1:role1,user2:role2'
  --skip-collaborators        Skip adding collaborators
  --dry-run                   Preview without executing
  --help                      Show this message and exit
```

### Collaborator Roles

- **read** - Read-only access
- **write** - Read + Write access
- **admin** - Full admin access
- **maintain** - Manage without admin privileges
- **triage** - Manage issues and PRs

## What Gets Created

When you run `wt create`, the CLI will:

### 1. Create Repository
- Creates from `wildlife-dynamics/wt-template`
- Sets description and visibility
- Creates in organization or personal account

### 2. Add Collaborators
- Automatically adds you as admin
- Adds any specified collaborators with their roles
- Skips repository owner (can't be added as collaborator)

### 3. Apply Branch Protection (Organizations Only)
- Fetches rules from: [ecoscope_main_branch_rules.json](https://github.com/wildlife-dynamics/ecoscope-hub/blob/main/repo-setup/ecoscope_main_branch_rules.json)
- Applies repository ruleset with:
  - Prevent deletion
  - Require linear history
  - Require pull request approval
  - Require status checks to pass
- **Note**: Personal repositories require GitHub Pro for rulesets

## Example Workflows

### Create Personal Repository

```bash
wt create --name wt-test-workflow --description "Test workflow"
```

Creates a private repository in your personal account.

### Create Organization Repository

```bash
wt create \
  --name wt-elephant-tracking \
  --description "Elephant movement analysis" \
  --org wildlife-dynamics \
  --collaborators "researcher1:write,researcher2:read"
```

Creates a private repository in the organization with collaborators and branch protection.

### Preview Before Creating

```bash
wt create --name wt-my-workflow --dry-run
```

Shows a summary of what will be created without making any changes.

## Troubleshooting

### Authentication Failed

If you get "Bad credentials" error:
- Your token may be expired or invalid
- The CLI will automatically prompt for a new token
- Generate a new token at https://github.com/settings/tokens/new

### Repository Already Exists

Repository names must be unique. Choose a different name or delete the existing repository.

### Insufficient Permissions

- To create organization repositories, you need admin permission in that organization
- To add collaborators, you need admin permission on the repository
- Branch protection rules require appropriate permissions

### Branch Protection Not Applied

- Branch protection rulesets require GitHub Pro for personal accounts
- Organization repositories can use rulesets for free
- For personal repos, manually add branch protection in Settings → Branches
