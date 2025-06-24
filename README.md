# QUIC Connection Migration Tester

A Python tool for testing HTTP/3 websites' support for QUIC connection migration by analyzing connection parameters and simulating network changes.

## Overview

QUIC Connection Migration Tester is a specialized diagnostic tool that helps determine whether an HTTP/3 server properly supports connection migration as defined in [RFC 9000](https://datatracker.ietf.org/doc/html/rfc9000). Connection migration is a key feature of QUIC that allows connections to survive network path changes, such as NAT rebinding or switching from Wi-Fi to cellular networks.

## Features

- **Connection ID Management Testing**: Validates server's ability to provide multiple connection IDs
- **Network Change Simulation**: Simulates network interface changes by modifying local port bindings
- **Transport Parameter Analysis**: Examines QUIC transport parameters related to migration
- **Path Validation Testing**: Checks for proper PATH_CHALLENGE/PATH_RESPONSE exchanges
- **RFC 9000 Compliance Checking**: Verifies adherence to QUIC connection migration standards
- **Detailed Logging**: Provides comprehensive diagnostic output for troubleshooting

## Installation

### Prerequisites

- Python 3.13 or higher
- [uv](https://docs.astral.sh/uv/)

### Install from source

```bash
git clone https://github.com/stackia/quic-migration-tester
cd quic-migration-tester
uv sync
```

### Install as package

```bash
# Install from local directory
uv pip install .

# Or build and install wheel
uv build
uv pip install dist/quic_migration_tester-*.whl
```

## Usage

### Basic Usage

```bash
# Run directly with uv
uv run quic-migration-tester https://http3check.net

# Or if installed as package
quic-migration-tester https://http3check.net
```

### Advanced Options

```bash
# Enable verbose logging for detailed diagnostics
uv run quic-migration-tester https://cloudflare.com --verbose

# Disable certificate verification
uv run quic-migration-tester https://test-server.com --no-verify
```

### Command Line Arguments

- `url`: Target HTTPS URL to test (required)
- `--version`: Show program version and exit
- `--verbose, -v`: Enable verbose logging for detailed output
- `--no-verify`: Disable TLS certificate verification
- `--help, -h`: Show help message and exit

## Development

### Setup development environment

```bash
# Install with development dependencies
uv sync --dev

# Run code formatting
uv run black .
uv run isort .

# Run type checking
uv run mypy .

# Run linting
uv run flake8 .
```

### Building

```bash
# Build source and wheel distributions
uv build

# The built packages will be in the dist/ directory
ls dist/
# quic_migration_tester-0.1.0.tar.gz
# quic_migration_tester-0.1.0-py3-none-any.whl
```

## How It Works

The tester performs a three-phase connection migration test:

### Phase 1: Initial Connection Establishment

- Establishes QUIC connection with the target server
- Analyzes transport parameters (`active_connection_id_limit`, `disable_active_migration`, etc.)
- Collects available connection IDs from the server

### Phase 2: Network Change Simulation

- Simulates network interface change by creating a new local socket binding
- Triggers connection ID change using `change_connection_id()`
- Monitors for PATH_CHALLENGE frames from the server

### Phase 3: Connection Validation

- Verifies connection remains functional after migration
- Confirms connection state remains CONNECTED
- Performs final connectivity test using ping
