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

```bash
git clone <repository-url>
cd quic-connection-migration-tester
uv sync
```

## Usage

### Basic Usage

```bash
uv run main.py https://www.google.com
```

### Advanced Options

```bash
# Enable verbose logging for detailed diagnostics
uv run main.py https://cloudflare.com --verbose

# Disable certificate verification
uv run main.py https://test-server.com --no-verify
```

### Command Line Arguments

- `url`: Target HTTPS URL to test (required)
- `--verbose, -v`: Enable verbose logging for detailed output
- `--no-verify`: Disable TLS certificate verification

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
