"""
Validates authentication integration by testing Supabase and Keycloak
authentication methods with a temporary API server instance.

This script demonstrates that the ReLIFE Service API template supports different authentication methods:
- Supabase email/password authentication
- Keycloak user authentication (Resource Owner Password Grant)
- Keycloak client credentials authentication (Client Credentials Grant)
"""

import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

import httpx
import uvicorn
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from supabase import create_client
from supabase.client import ClientOptions

from relife_financial.app import app

# Configuration constants
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SERVER_STARTUP_MAX_ATTEMPTS = 10
SERVER_STARTUP_RETRY_DELAY = 0.5
SERVER_HEALTH_CHECK_TIMEOUT = 5.0
SERVER_SHUTDOWN_TIMEOUT = 5.0
API_REQUEST_TIMEOUT = 30.0
ADMIN_ROLE_NAME = "relife_admin"


def load_environment() -> Dict[str, str]:
    """Load and validate required environment variables.

    Returns:
        Dictionary containing validated environment variables.

    Raises:
        SystemExit: If required environment variables are missing.
    """

    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "KEYCLOAK_CLIENT_ID",
        "KEYCLOAK_CLIENT_SECRET",
        "KEYCLOAK_REALM_URL",
    ]

    missing_vars = []
    config = {}

    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            config[var] = value

    if missing_vars:
        console = Console()
        console.print(
            f"[red]ERROR: Missing environment variables: {', '.join(missing_vars)}[/red]"
        )
        console.print(
            "[blue]Please set these environment variables before running the script.[/blue]"
        )
        sys.exit(1)

    return config


def prompt_credentials(
    email: str | None = None, password: str | None = None
) -> tuple[str, str]:
    """Prompt user for authentication credentials.

    Args:
        email: Pre-filled email address (optional).

    Returns:
        Tuple of (email, password).
    """

    console = Console()
    console.print()
    console.print("[bold blue]Authentication Required[/bold blue]")

    if not email:
        email = Prompt.ask("Email", console=console)
    else:
        console.print(f"Email: [bold cyan]{email}[/bold cyan]")

    if password is None:
        password = Prompt.ask("Password", password=True, console=console)

    console.print()

    return email, password


def get_keycloak_token_endpoint(keycloak_realm_url: str) -> str:
    """Construct token endpoint URL from Keycloak realm URL.

    Args:
        keycloak_realm_url: Base URL of the Keycloak realm.

    Returns:
        Token endpoint URL.
    """

    return f"{keycloak_realm_url.rstrip('/')}/protocol/openid-connect/token"


def show_info_panel():
    """Display information about script functionality."""

    console = Console()

    info_md = """
**This script validates authentication integration:**

1. **Authenticate** via Supabase (email/password) or Keycloak (user/client credentials)
2. **Start** temporary API server
3. **Verify** `/whoami` endpoint 
4. **Display** user information and roles
5. **Shutdown** server after verification

**Authentication Methods:**
- `supabase`: Email/password via Supabase
- `keycloak-user`: Username/password via Keycloak (Resource Owner Password Grant)
- `keycloak-client`: Client credentials via Keycloak (Client Credentials Grant)

**Troubleshooting:**
- If `keycloak-user` fails, try `keycloak-client` first to verify basic client setup
- Check that your Keycloak client has "Direct Access Grants" enabled for Resource Owner Password Grant
"""

    panel = Panel(
        Markdown(info_md),
        border_style="yellow",
        padding=(1, 2),
        title="Authentication Integration Validator",
    )

    console.print(panel)


async def authenticate_supabase(
    email: str, password: str, config: Dict[str, str]
) -> str:
    """Authenticate with Supabase using email/password.

    Args:
        email: User email address.
        password: User password.
        config: Environment configuration dictionary.

    Returns:
        Supabase access token.

    Raises:
        Exception: If authentication fails.
    """

    console = Console()
    console.print(f"[blue]Authenticating with Supabase: {email}[/blue]")

    try:
        client = create_client(
            config["SUPABASE_URL"],
            config["SUPABASE_KEY"],
            options=ClientOptions(),
        )

        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if response.user and response.session:
            console.print("[green]Supabase authentication successful[/green]")
            return response.session.access_token
        else:
            raise Exception("No session returned from Supabase")

    except Exception as e:
        console.print(f"[red]Supabase authentication failed: {e}[/red]")
        raise


async def authenticate_keycloak_user(
    email: str, password: str, config: Dict[str, str]
) -> str:
    """Authenticate with Keycloak using Resource Owner Password Grant.

    Args:
        email: User email/username.
        password: User password.
        config: Environment configuration dictionary.

    Returns:
        Keycloak access token.

    Raises:
        Exception: If authentication fails.
    """

    console = Console()
    console.print(f"[blue]Authenticating Keycloak user: {email}[/blue]")

    try:
        # Construct token endpoint from realm URL
        keycloak_realm_url = config["KEYCLOAK_REALM_URL"]
        token_url = get_keycloak_token_endpoint(keycloak_realm_url)
        console.print(f"[blue]Using token endpoint: {token_url}[/blue]")

        # Prepare token request data for Resource Owner Password Grant
        data = {
            "grant_type": "password",
            "client_id": config["KEYCLOAK_CLIENT_ID"],
            "client_secret": config["KEYCLOAK_CLIENT_SECRET"],
            "username": email,
            "password": password,
        }

        # Debug: show request details (without sensitive data)
        debug_data = {
            k: v if k != "password" and k != "client_secret" else "***"
            for k, v in data.items()
        }

        console.print(f"[blue]Request data: {debug_data}[/blue]")

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data["access_token"]

            console.print("[green]Keycloak user authentication successful[/green]")
            return access_token

    except httpx.HTTPStatusError as e:
        console.print(
            f"[red]HTTP {e.response.status_code}: {e.response.reason_phrase}[/red]"
        )

        error_detail = "Invalid credentials or configuration"
        try:
            error_response = e.response.json()
            console.print(f"[yellow]Keycloak error response: {error_response}[/yellow]")

            if "error_description" in error_response:
                error_detail = error_response["error_description"]
            elif "error" in error_response:
                error_detail = f"{error_response['error']}: {error_response.get('error_description', 'No description provided')}"
        except Exception as parse_error:
            console.print(
                f"[yellow]Could not parse error response: {parse_error}[/yellow]"
            )

            console.print(f"[yellow]Raw response: {e.response.text}[/yellow]")

        console.print(f"[red]Keycloak user authentication failed: {error_detail}[/red]")
        raise Exception(error_detail)
    except Exception as e:
        console.print(f"[red]Keycloak user authentication failed: {e}[/red]")
        raise


async def authenticate_keycloak_client(config: Dict[str, str]) -> str:
    """Authenticate with Keycloak using client credentials flow.

    Args:
        config: Environment configuration dictionary.

    Returns:
        Keycloak access token.

    Raises:
        Exception: If authentication fails.
    """

    console = Console()
    console.print("[blue]Authenticating with Keycloak client credentials[/blue]")

    try:
        # Construct token endpoint from realm URL
        keycloak_realm_url = config["KEYCLOAK_REALM_URL"]
        token_url = get_keycloak_token_endpoint(keycloak_realm_url)
        console.print(f"[blue]Using token endpoint: {token_url}[/blue]")

        # Prepare token request data for Client Credentials Grant
        data = {
            "grant_type": "client_credentials",
            "client_id": config["KEYCLOAK_CLIENT_ID"],
            "client_secret": config["KEYCLOAK_CLIENT_SECRET"],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data["access_token"]

            console.print("[green]Keycloak client authentication successful[/green]")
            return access_token

    except Exception as e:
        console.print(f"[red]Keycloak client authentication failed: {e}[/red]")
        raise


async def get_auth_token(
    auth_method: str, email: str, password: str, config: Dict[str, str]
) -> str:
    """Get authentication token using the specified method.

    Args:
        auth_method: Authentication method ('supabase', 'keycloak-user', 'keycloak-client').
        email: User email (required for supabase and keycloak-user).
        password: User password (required for supabase and keycloak-user).
        config: Environment configuration dictionary.

    Returns:
        Access token for the specified authentication method.

    Raises:
        ValueError: If authentication method is unsupported.
        Exception: If authentication fails.
    """

    if auth_method == "supabase":
        return await authenticate_supabase(email, password, config)
    elif auth_method == "keycloak-user":
        return await authenticate_keycloak_user(email, password, config)
    elif auth_method == "keycloak-client":
        return await authenticate_keycloak_client(config)
    else:
        raise ValueError(f"Unsupported authentication method: {auth_method}")


@asynccontextmanager
async def run_api_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Context-manager that launches a FastAPI server in-process.

    Args:
        host: Bind address.
        port: TCP port.

    Yields:
        str: Base URL (e.g. "http://127.0.0.1:8000") while the server is
        running.
    """

    console = Console()

    # Configure server
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="error",
        access_log=False,
    )

    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    try:
        # Wait for server to start
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Starting server...", total=None)

            for attempt in range(SERVER_STARTUP_MAX_ATTEMPTS):
                await asyncio.sleep(SERVER_STARTUP_RETRY_DELAY)
                try:
                    async with httpx.AsyncClient(
                        timeout=SERVER_HEALTH_CHECK_TIMEOUT
                    ) as client:
                        response = await client.get(f"http://{host}:{port}/docs")
                        if response.status_code in [200, 404]:
                            progress.update(task, description="Server ready")
                            break
                except Exception:
                    if attempt == SERVER_STARTUP_MAX_ATTEMPTS - 1:
                        progress.update(task, description="Server failed")
                        console.print("[red]Server failed to start[/red]")
                        raise

        console.print(f"[green]Server running on http://{host}:{port}[/green]")
        yield f"http://{host}:{port}"

    finally:
        # Shutdown server
        server.should_exit = True
        try:
            await asyncio.wait_for(server_task, timeout=SERVER_SHUTDOWN_TIMEOUT)
        except asyncio.TimeoutError:
            console.print("[yellow]Server shutdown timed out[/yellow]")


async def verify_whoami_endpoint(base_url: str, auth_token: str):
    """Call `/whoami` and pretty-print the response.

    All HTTP responses are logged to the console; errors do **not** propagate as
    exceptions so that the caller can continue and report a friendly message.
    """

    console = Console()
    console.print(f"[blue]Verifying {base_url}/whoami[/blue]")

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=API_REQUEST_TIMEOUT) as client:
            response = await client.get(f"{base_url}/whoami", headers=headers)
            console.print(f"[blue]Response: {response.status_code}[/blue]")

            if response.status_code == 200:
                data = response.json()
                console.print("[green]Authentication verified[/green]")
                display_user_info(data)
            else:
                console.print(f"[red]Request failed: {response.status_code}[/red]")
                console.print(f"[yellow]{response.text}[/yellow]")

    except httpx.TimeoutException:
        console.print("[red]Request timed out[/red]")
    except Exception as e:
        console.print(f"[red]Request failed: {e}[/red]")


def display_user_info(data: Dict[str, Any]):
    """Display user information in a formatted table.

    Args:
        data: User data returned from /whoami endpoint.
    """

    console = Console()
    table = Table(title="User Information", show_header=True, header_style="bold blue")
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    # Basic user info
    user_info = data.get("user", {})
    table.add_row("User ID", user_info.get("id", "N/A"))
    table.add_row("Email", user_info.get("email", "N/A"))
    table.add_row("Authentication Method", data.get("authentication_method", "N/A"))

    # User metadata
    user_metadata = user_info.get("user_metadata", {})
    if user_metadata:
        metadata_text = ""
        for key, value in user_metadata.items():
            metadata_text += f"{key}: {value}\n"
        table.add_row("User Metadata", metadata_text.strip())

    # Keycloak roles
    roles = data.get("keycloak_roles", [])
    if roles:
        roles_text = f"{len(roles)} roles:"
        for role in roles:
            roles_text += f"\n• {role.get('name', 'Unknown')}"
            if role.get("description"):
                roles_text += f": {role['description']}"
    else:
        roles_text = "None"
    table.add_row("Keycloak Roles", roles_text)

    # Admin status
    has_admin = any(role.get("name") == ADMIN_ROLE_NAME for role in roles)
    admin_text = Text("Yes" if has_admin else "No")
    admin_text.stylize("green" if has_admin else "red")
    table.add_row("Admin Role", admin_text)

    console.print(table)


def validate_arguments(args) -> None:
    """Validate CLI arguments with minimal duplication.

    Ensures that interactive-only parameters are supplied when running in a
    non-interactive context. Because the script can fall back to prompting, the
    only hard requirement is that *email* is supplied for user-credential flows
    **when --password is also provided**; this prevents a mismatch that would
    still require prompting.
    """

    console = Console()

    if (
        args.auth_method in ["supabase", "keycloak-user"]
        and args.password
        and not args.email
    ):
        console.print(
            f"[red]ERROR: --email must accompany --password for {args.auth_method} authentication[/red]"
        )
        sys.exit(1)


async def main():
    """Main script function."""

    parser = argparse.ArgumentParser(
        description="Validate authentication integration with Supabase and Keycloak"
    )

    parser.add_argument(
        "--auth-method",
        choices=["supabase", "keycloak-user", "keycloak-client"],
        default="keycloak-client",
        help="Authentication method to use (default: keycloak-client)",
    )

    parser.add_argument(
        "--email",
        help="User email (required for supabase and keycloak-user; if omitted you will be prompted)",
    )

    parser.add_argument(
        "--password",
        help="User password (optional). If omitted and required, an interactive prompt will be shown.",
    )

    parser.add_argument("--host", default=DEFAULT_HOST, help="Server host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Server port")
    args = parser.parse_args()

    console = Console()

    # Validate arguments
    validate_arguments(args)

    # Show info panel
    show_info_panel()

    # Load environment
    config = load_environment()
    console.print(f"[green]Environment loaded[/green]")

    # Get authentication credentials if needed (interactive fallback)
    email, password = args.email, args.password

    if args.auth_method in ["supabase", "keycloak-user"]:
        if email is None or password is None:
            email, password = prompt_credentials(email, password)

    # Get authentication token
    try:
        auth_token = await get_auth_token(args.auth_method, email, password, config)
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        sys.exit(1)

    # Start server and verify API
    console.print(f"[blue]Starting server on {args.host}:{args.port}[/blue]")

    try:
        async with run_api_server(args.host, args.port) as server_url:
            await verify_whoami_endpoint(server_url, auth_token)
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")
        sys.exit(1)

    console.print("[blue]Verification complete[/blue]")


def cli():
    """CLI entry point."""

    asyncio.run(main())


if __name__ == "__main__":
    cli()
