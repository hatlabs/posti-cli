# posti-cli

Command-line interface to Posti OmaPosti Pro API. Designed for use by Claude Code agents in the Hat Labs ops workspace.

## Installation

```bash
uv pip install -e .
```

## Configuration

Set environment variables (or pass as CLI options):

```bash
# v1 API (shipping labels)
export POSTI_URL=https://gateway.posti.fi/shippingapi/api
export POSTI_API_KEY=your-api-key
export POSTI_CUSTOMER_NUMBER=your-customer-number

# v2 API (2025-04: pickup points, estimates, labelless)
export POSTI_OAUTH_CLIENT_ID=your-client-id
export POSTI_OAUTH_CLIENT_SECRET=your-client-secret
# Optional: override v2 base URL (default: https://gateway.posti.fi/2025-04)
# export POSTI_V2_URL=https://gateway.posti.fi/2025-04
```

## Usage

```bash
# List shipping methods (hardcoded, no API call)
posti-cli --json methods list

# Create a shipment with label PDFs
posti-cli --json shipment create -d '{"pdfConfig": {...}, "shipment": {...}}'
posti-cli --json shipment create -d @shipment.json --output-dir ./labels

# Search pickup points (2025-04 API)
posti-cli --json pickuppoints search -d '{"postcode": "00100", "country": "FI"}'
posti-cli --json pickuppoints list FI
posti-cli --json pickuppoints get FI point-id

# Estimate delivery time (2025-04 API)
posti-cli --json estimate -d '{"originPostcode": "00100", "destinationPostcode": "20100"}'

# Labelless sending codes (2025-04 API)
posti-cli --json labelless create -d '{"trackingNumber": "JJFI..."}'
posti-cli --json labelless get JJFI...
posti-cli --json labelless get-by-code CODE

# Interactive REPL
posti-cli
```

All commands support `--json` for machine-readable output. The v2 commands (pickuppoints, estimate, labelless) require OAuth credentials.
