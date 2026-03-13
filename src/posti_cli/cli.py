"""Posti CLI — Click-based command interface with REPL."""

import json
import sys

import click

from posti_cli.core.client import PostiAPIError, make_client
from posti_cli.core import methods, shipments
from posti_cli.core import pickuppoints, estimate, labelless
from posti_cli.core.client_v2 import make_v2_client


class CliContext:
    """Shared state passed via Click context."""

    def __init__(
        self,
        json_output: bool,
        url: str | None,
        api_key: str | None,
        customer_number: str | None,
        oauth_client_id: str | None,
        oauth_client_secret: str | None,
    ):
        self.json_output = json_output
        self.url = url
        self.api_key = api_key
        self.customer_number = customer_number
        self.oauth_client_id = oauth_client_id
        self.oauth_client_secret = oauth_client_secret
        self._client = None
        self._v2_client = None

    @property
    def client(self):
        if self._client is None:
            self._client = make_client(
                url=self.url,
                api_key=self.api_key,
                customer_number=self.customer_number,
            )
        return self._client

    @property
    def v2_client(self):
        if self._v2_client is None:
            self._v2_client = make_v2_client(
                oauth_client_id=self.oauth_client_id,
                oauth_client_secret=self.oauth_client_secret,
            )
        return self._v2_client


pass_ctx = click.make_pass_decorator(CliContext, ensure=True)


def _output(ctx: CliContext, data) -> None:
    """Print data as JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


def _output_list(ctx: CliContext, data: list[dict], headers: list[str], row_fn) -> None:
    """Print a list as JSON or table."""
    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    from posti_cli.utils.repl_skin import ReplSkin

    skin = ReplSkin("posti")
    rows = [row_fn(d) for d in data]
    skin.table(headers, rows)
    skin.hint(f"\n  {len(data)} result(s)")


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--url", envvar="POSTI_URL", help="Posti API URL.")
@click.option("--api-key", envvar="POSTI_API_KEY", help="Posti API key.")
@click.option("--customer-number", envvar="POSTI_CUSTOMER_NUMBER", help="Posti customer number.")
@click.option("--oauth-client-id", envvar="POSTI_OAUTH_CLIENT_ID", help="OAuth client ID for 2025-04 API.")
@click.option("--oauth-client-secret", envvar="POSTI_OAUTH_CLIENT_SECRET", help="OAuth client secret for 2025-04 API.")
@click.pass_context
def cli(ctx, json_output, url, api_key, customer_number, oauth_client_id, oauth_client_secret):
    """Posti CLI — command-line interface to Posti OmaPosti Pro API."""
    ctx.obj = CliContext(
        json_output=json_output,
        url=url,
        api_key=api_key,
        customer_number=customer_number,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
    )

    if ctx.invoked_subcommand is None:
        _run_repl(ctx.obj)


def _run_repl(ctx: CliContext) -> None:
    """Interactive REPL mode."""
    from posti_cli.utils.repl_skin import ReplSkin

    skin = ReplSkin("posti")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    commands = {
        "methods list": "List shipping methods (hardcoded)",
        "shipment create -d JSON": "Create shipment",
        "pickuppoints search -d JSON": "Search pickup points",
        "pickuppoints list COUNTRY": "List pickup points for country",
        "pickuppoints get COUNTRY ID": "Get pickup point details",
        "estimate -d JSON": "Estimate delivery time",
        "labelless create -d JSON": "Create labelless sending code",
        "labelless get TRACKING_NUMBER": "Get sending code by tracking number",
        "labelless get-by-code CODE": "Get shipment by sending code",
        "help": "Show this help",
        "quit / exit": "Exit the REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if line == "help":
            skin.help(commands)
            continue

        args = _split_args(line)
        if ctx.json_output:
            args = ["--json"] + args

        try:
            cli.main(args=args, standalone_mode=False, obj=ctx)
        except SystemExit:
            pass
        except PostiAPIError as e:
            skin.error(str(e))
        except click.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Unexpected error: {e}")


def _split_args(line: str) -> list[str]:
    """Split a REPL input line respecting quoted strings."""
    import shlex

    try:
        return shlex.split(line)
    except ValueError:
        return line.split()


# ---------------------------------------------------------------------------
# methods
# ---------------------------------------------------------------------------


@cli.group(name="methods")
def methods_cmd():
    """Shipping method operations."""


@methods_cmd.command("list")
@pass_ctx
def methods_list(ctx):
    """List available Posti shipping methods."""
    data = methods.list_methods()
    _output_list(
        ctx,
        data,
        ["Code", "Name", "Delivery"],
        lambda d: [
            d.get("code", ""),
            d.get("name", ""),
            d.get("deliveryType", ""),
        ],
    )


# ---------------------------------------------------------------------------
# shipment
# ---------------------------------------------------------------------------


@cli.group(name="shipment")
def shipment_cmd():
    """Shipment operations."""


@shipment_cmd.command("create")
@click.option("--data", "-d", required=True, help="JSON shipment data.")
@click.option("--output-dir", default=None, help="Directory to save label PDFs.")
@pass_ctx
def shipment_create(ctx, data, output_dir):
    """Create a shipment."""
    data = json.loads(data)
    result = shipments.create_shipment(ctx.client, data)

    if output_dir and isinstance(result, list):
        saved = shipments.save_pdfs(result, output_dir)
        for path in saved:
            click.echo(f"Saved: {path}", err=True)

    _output(ctx, result)


# ---------------------------------------------------------------------------
# pickuppoints (2025-04 API)
# ---------------------------------------------------------------------------


@cli.group(name="pickuppoints")
def pickuppoints_cmd():
    """Pickup point operations (2025-04 API)."""


@pickuppoints_cmd.command("search")
@click.option("--data", "-d", required=True, help="JSON search criteria.")
@click.option("--language", "-l", default=None, help="Response language (fi, sv, en, et, lv, lt).")
@pass_ctx
def pickuppoints_search(ctx, data, language):
    """Search pickup points by address, postcode, or coordinates."""
    data = json.loads(data)
    result = pickuppoints.search_pickuppoints(ctx.v2_client, data, language=language)
    _output(ctx, result)


@pickuppoints_cmd.command("list")
@click.argument("country")
@click.option("--language", "-l", default=None, help="Response language (fi, sv, en, et, lv, lt).")
@pass_ctx
def pickuppoints_list(ctx, country, language):
    """List all pickup points for a country."""
    result = pickuppoints.list_pickuppoints(ctx.v2_client, country, language=language)
    _output(ctx, result)


@pickuppoints_cmd.command("get")
@click.argument("country")
@click.argument("point_id")
@click.option("--language", "-l", default=None, help="Response language (fi, sv, en, et, lv, lt).")
@pass_ctx
def pickuppoints_get(ctx, country, point_id, language):
    """Get a single pickup point by ID."""
    result = pickuppoints.get_pickuppoint(ctx.v2_client, country, point_id, language=language)
    _output(ctx, result)


# ---------------------------------------------------------------------------
# estimate (2025-04 API)
# ---------------------------------------------------------------------------


@cli.command(name="estimate")
@click.option("--data", "-d", required=True, help="JSON estimation request.")
@pass_ctx
def estimate_cmd(ctx, data):
    """Estimate delivery time between origin and destination."""
    data = json.loads(data)
    result = estimate.estimate_delivery(ctx.v2_client, data)
    _output(ctx, result)


# ---------------------------------------------------------------------------
# labelless (2025-04 API)
# ---------------------------------------------------------------------------


@cli.group(name="labelless")
def labelless_cmd():
    """Labelless sending operations (2025-04 API)."""


@labelless_cmd.command("create")
@click.option("--data", "-d", required=True, help="JSON request with trackingNumber.")
@pass_ctx
def labelless_create(ctx, data):
    """Create a sending code for a shipment."""
    data = json.loads(data)
    result = labelless.create_sending_code(ctx.v2_client, data)
    _output(ctx, result)


@labelless_cmd.command("get")
@click.argument("tracking_number")
@pass_ctx
def labelless_get(ctx, tracking_number):
    """Get sending code by tracking number."""
    result = labelless.get_by_tracking_number(ctx.v2_client, tracking_number)
    _output(ctx, result)


@labelless_cmd.command("get-by-code")
@click.argument("code")
@pass_ctx
def labelless_get_by_code(ctx, code):
    """Get shipment details by sending code."""
    result = labelless.get_by_sending_code(ctx.v2_client, code)
    _output(ctx, result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    try:
        cli(standalone_mode=True)
    except PostiAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
