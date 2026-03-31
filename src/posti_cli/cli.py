"""Posti CLI — Click-based command interface with REPL."""

import json
import sys

import click

from posti_cli.core.client import PostiAPIError
from posti_cli.core import methods, shipments
from posti_cli.core import pickuppoints, estimate, labelless
from posti_cli.core.client_v2 import PostiV2Client, make_v2_client
from posti_cli.core.pro.auth import make_pro_auth
from posti_cli.core.pro.client import ProClient
from posti_cli.core.pro import shipments as pro_shipments


class CliContext:
    """Shared state passed via Click context."""

    def __init__(
        self,
        json_output: bool,
        url: str | None,
        oauth_client_id: str | None,
        oauth_client_secret: str | None,
        pro_username: str | None = None,
        pro_password: str | None = None,
    ):
        self.json_output = json_output
        self.url = url
        self.oauth_client_id = oauth_client_id
        self.oauth_client_secret = oauth_client_secret
        self.pro_username = pro_username
        self.pro_password = pro_password
        self._v2_client = None
        self._shipping_v2_client = None
        self._pro_client = None

    @property
    def v2_client(self):
        if self._v2_client is None:
            self._v2_client = make_v2_client(
                oauth_client_id=self.oauth_client_id,
                oauth_client_secret=self.oauth_client_secret,
            )
        return self._v2_client

    @property
    def pro_client(self):
        if self._pro_client is None:
            auth = make_pro_auth(
                username=self.pro_username,
                password=self.pro_password,
            )
            self._pro_client = ProClient(auth)
        return self._pro_client

    @property
    def shipping_v2_client(self):
        """V2 client for the shipping API (different base URL than 2025-04 API)."""
        if self._shipping_v2_client is None:
            if not self.url:
                raise PostiAPIError(
                    "POSTI_URL not set. Provide --url or set the env var."
                )
            # Reuse the same OAuth session — both APIs accept the same token scope
            self._shipping_v2_client = PostiV2Client(
                url=self.url.rstrip("/"),
                oauth=self.v2_client.oauth,
            )
        return self._shipping_v2_client


pass_ctx = click.make_pass_decorator(CliContext, ensure=True)


def _output(ctx: CliContext, data) -> None:
    """Print data as JSON. Used by v2 commands that have no table format."""
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
@click.option("--url", envvar="POSTI_URL", help="Posti shipping API URL.")
@click.option("--oauth-client-id", envvar="POSTI_OAUTH_CLIENT_ID", help="OAuth client ID.")
@click.option("--oauth-client-secret", envvar="POSTI_OAUTH_CLIENT_SECRET", help="OAuth client secret.")
@click.option("--pro-username", envvar="POSTI_PRO_USERNAME", help="OmaPosti Pro username.")
@click.option("--pro-password", envvar="POSTI_PRO_PASSWORD", help="OmaPosti Pro password.")
@click.pass_context
def cli(ctx, json_output, url, oauth_client_id, oauth_client_secret, pro_username, pro_password):
    """Posti CLI — command-line interface to Posti API."""
    ctx.obj = CliContext(
        json_output=json_output,
        url=url,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        pro_username=pro_username,
        pro_password=pro_password,
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
        "pro shipment list [--query TEXT]": "List shipments (Pro GraphQL)",
        "pro shipment get TRACKING_ID": "Get shipment detail with dimensions",
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
    result = shipments.create_shipment(ctx.shipping_v2_client, data)

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
# pro (GraphQL API)
# ---------------------------------------------------------------------------


@cli.group(name="pro")
def pro_cmd():
    """OmaPosti Pro operations (GraphQL API)."""


@pro_cmd.group(name="shipment")
def pro_shipment_cmd():
    """Pro shipment operations."""


@pro_shipment_cmd.command("list")
@click.option("--first", default=50, help="Number of results.")
@click.option("--offset", default=0, help="Pagination offset.")
@click.option("--query", "query_term", default=None, help="Search term.")
@click.option("--starred", is_flag=True, help="Show only starred shipments.")
@pass_ctx
def pro_shipment_list(ctx, first, offset, query_term, starred):
    """List shipments from OmaPosti Pro."""
    result = pro_shipments.list_shipments(
        ctx.pro_client,
        first=first,
        offset=offset,
        query_term=query_term,
        starred=starred,
    )

    def _status_text(item):
        descs = item.get("status", {}).get("description", [])
        for d in descs:
            if d.get("lang") == "en":
                return d["value"]
        return item.get("status", {}).get("code", "")

    def _product_name(item):
        names = item.get("product", {}).get("name", {})
        return names.get("en") or names.get("fi") or item.get("product", {}).get("code", "")

    items = result["items"]
    if ctx.json_output:
        _output(ctx, result)
        return

    from posti_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("posti")
    rows = [
        [
            (d.get("savedDateTime") or "")[:10],
            (d.get("trackingNumbers") or [""])[0],
            _product_name(d),
            d.get("receiver", {}).get("name", ""),
            d.get("receiver", {}).get("country", ""),
            _status_text(d),
        ]
        for d in items
    ]
    skin.table(["Date", "Tracking", "Product", "Receiver", "Country", "Status"], rows)
    total = result.get("totalFound", 0)
    more = result.get("moreResults", False)
    skin.hint(f"\n  Showing {len(items)} of {total}"
              + (" (more available)" if more else ""))


@pro_shipment_cmd.command("get")
@click.argument("tracking_id")
@pass_ctx
def pro_shipment_get(ctx, tracking_id):
    """Get full shipment detail with dimensions and tracking."""
    result = pro_shipments.get_shipment(ctx.pro_client, tracking_id)

    if ctx.json_output:
        _output(ctx, result)
        return

    from posti_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("posti")

    # Header
    tracking = (result.get("trackingNumbers") or ["?"])[0]
    product = result.get("product", {})
    product_names = product.get("localNames", [])
    product_name = next(
        (n["value"] for n in product_names if n.get("lang") == "en"),
        product.get("code", ""),
    )
    status_descs = result.get("status", {}).get("description", [])
    status_text = next(
        (d["value"] for d in status_descs if d.get("lang") == "en"),
        result.get("status", {}).get("code", ""),
    )
    click.echo(f"\n  {tracking}  {product_name}  [{status_text}]")
    click.echo(f"  Created: {result.get('createdAt', '?')}")

    # Dimensions (fields may be None for unmeasured shipments)
    w = result.get("weight") or {}
    h = result.get("height") or {}
    ln = result.get("length") or {}
    wd = result.get("width") or {}
    vol = result.get("volume") or {}
    if any(x.get("value") is not None for x in [w, h, ln, wd]):
        click.echo(f"\n  Dimensions: {ln.get('value', '?')} x {wd.get('value', '?')} x {h.get('value', '?')} cm")
        click.echo(f"  Weight: {w.get('value', '?')} kg")
        if vol.get("value"):
            click.echo(f"  Volume: {vol['value']} m\u00b3")

    # Sender / Receiver
    for label, addr in [("Sender", result.get("sender", {})),
                        ("Receiver", result.get("receiver", {}))]:
        name = addr.get("name", "?")
        street = addr.get("street", "")
        city = addr.get("city", "")
        postcode = addr.get("postCode", "")
        country = addr.get("countryCode", "")
        click.echo(f"\n  {label}: {name}")
        if street:
            click.echo(f"    {street}")
        if city or postcode:
            click.echo(f"    {postcode} {city} {country}".strip())

    # References
    refs = result.get("references", {})
    order_nums = refs.get("orderNumber", [])
    if order_nums:
        click.echo(f"\n  Order: {', '.join(order_nums)}")

    # Events
    events = result.get("events", [])
    if events:
        click.echo(f"\n  Tracking events ({len(events)}):")
        for ev in events:
            ts = (ev.get("timeStamp") or "")[:16].replace("T", " ")
            names = ev.get("eventShortName", [])
            name = next(
                (n["value"] for n in names if n.get("lang") == "en"),
                ev.get("eventCode", ""),
            )
            city = ev.get("city") or ""
            country = ev.get("countryCode") or ""
            loc = f"{city}, {country}" if city else country
            click.echo(f"    {ts}  {name}  ({loc})")

    click.echo()


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
