# posti-cli

Command-line interface to Posti OmaPosti Pro API. Designed for use by Claude Code agents in the Hat Labs ops workspace.

## Installation

```bash
uv pip install -e .
```

## Configuration

Set environment variables (or pass as CLI options):

```bash
# OAuth credentials (required for all API operations)
export POSTI_OAUTH_CLIENT_ID=your-client-id
export POSTI_OAUTH_CLIENT_SECRET=your-client-secret

# Shipping API base URL (for shipment creation)
export POSTI_URL=https://gateway.posti.fi/shippingapi/api

# Optional: override 2025-04 API base URL (pickup points, estimates, labelless)
# export POSTI_V2_URL=https://gateway.posti.fi/2025-04
```

## Usage

```bash
# List shipping methods (hardcoded, no API call)
posti-cli --json methods list

# Create a shipment with label PDFs (v2 API, OAuth auth)
posti-cli --json shipment create -d '{"printConfig": {"target1Media": "thermo-225"}, "shipment": {"service": {"id": "PO2103"}, ...}}'
posti-cli --json shipment create -d @shipment.json --output-dir ./labels

# Search pickup points (2025-04 API)
posti-cli --json pickuppoints search -d '{"searchCriteria":{"location":{"postcode":"00100","countryCode":"FI"}}}'
posti-cli --json pickuppoints list FI
posti-cli --json pickuppoints get FI 001003230

# Estimate delivery time (2025-04 API)
posti-cli --json estimate -d '{"estimate":{"time":"2026-03-14T10:00:00Z","origin":{"countryCode":"FI","postcode":"00100"},"destination":{"countryCode":"FI","postcode":"20100"},"product":{"code":"2103"}}}'

# Labelless sending codes (2025-04 API)
posti-cli --json labelless create -d '{"searchCriteria":{"trackingNumber":"JJFI..."}}'
posti-cli --json labelless get JJFI...
posti-cli --json labelless get-by-code CODE

# Interactive REPL
posti-cli
```

All commands support `--json` for machine-readable output. All API commands require OAuth credentials (`POSTI_OAUTH_CLIENT_ID`/`POSTI_OAUTH_CLIENT_SECRET`). Shipment creation also requires `POSTI_URL`.
