"""
Export Cookies from your real browser session.

This approach does NOT open any automated browser. Instead:
1. You login to the platform in your normal Chrome/Edge browser
2. You export ALL cookies (including httpOnly) using DevTools
3. Paste them here and this script converts them to a session file

Usage:
    python export_cookies.py
"""

import json
from pathlib import Path
from rich.console import Console

console = Console()
SESSION_FILE = Path(__file__).parent / "session_state.json"


def main():
    console.print("[bold]RADE Cookie Exporter[/bold]")
    console.print()
    console.print("This will save your browser session without any automation.")
    console.print()
    console.print("[bold cyan]Steps:[/bold cyan]")
    console.print("1. Open [bold]Chrome/Edge[/bold] and log in to https://learn.dataengineeringhub.in")
    console.print("2. Open a course page, press [bold]F12[/bold], and select the [bold]Network[/bold] tab")
    console.print("3. Refresh the page and select a request to learn.dataengineeringhub.in")
    console.print("4. Under [bold]Request Headers[/bold], right-click the full [bold]Cookie[/bold] value and copy it")
    console.print("5. Return here and paste it at the local terminal prompt")
    console.print()
    console.print("[yellow]Do not paste session cookies into chat, email, source files, or Git.[/yellow]")
    console.print("[dim]The Network header is required because JavaScript APIs such as document.cookie[/dim]")
    console.print("[dim]and cookieStore cannot read HttpOnly authentication cookies.[/dim]")
    console.print()

    cookie_input = input("Paste cookies here (JSON array or raw string): ").strip()

    if not cookie_input:
        console.print("[red]No cookies provided. Aborting.[/red]")
        return

    cookies = []

    # Try to parse as JSON first (cookieStore format)
    try:
        raw_cookies = json.loads(cookie_input)
        if isinstance(raw_cookies, list):
            for c in raw_cookies:
                cookie = {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", "learn.dataengineeringhub.in"),
                    "path": c.get("path", "/"),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", True),
                    "sameSite": c.get("sameSite", "Lax"),
                }
                if cookie["name"]:
                    cookies.append(cookie)
            console.print(f"[green]Parsed {len(cookies)} cookies from JSON[/green]")
    except (json.JSONDecodeError, TypeError):
        # Fall back to parsing raw cookie string
        for part in cookie_input.split(";"):
            part = part.strip()
            if "=" in part:
                name, value = part.split("=", 1)
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": "learn.dataengineeringhub.in",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax",
                })
        console.print(f"[green]Parsed {len(cookies)} cookies from raw string[/green]")

    if not cookies:
        console.print("[red]Could not parse any cookies. Check the format.[/red]")
        return

    # Create Playwright-compatible storage state
    storage_state = {
        "cookies": cookies,
        "origins": [
            {
                "origin": "https://learn.dataengineeringhub.in",
                "localStorage": [],
            }
        ],
    }

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2)

    console.print(f"\n[bold green]Saved {len(cookies)} cookies to: {SESSION_FILE}[/bold green]")
    console.print()
    console.print("[dim]Verifying: checking for auth-related cookies...[/dim]")
    auth_names = [c["name"] for c in cookies if any(k in c["name"].lower() for k in ["session", "token", "auth", "xsrf", "laravel"])]
    if auth_names:
        console.print(f"[green]Found auth cookies: {', '.join(auth_names)}[/green]")
    else:
        console.print("[yellow]Warning: No obvious session/auth cookie found.[/yellow]")
        console.print("[yellow]The crawler may not be authenticated. If it fails, try the Network tab method below.[/yellow]")
        console.print()
        console.print("[bold]Alternative: Network tab method[/bold]")
        console.print("1. In DevTools, go to [bold]Network[/bold] tab")
        console.print("2. Navigate to any course page")
        console.print("3. Click any request to learn.dataengineeringhub.in")
        console.print("4. In Headers section, find [bold]Cookie:[/bold] header")
        console.print("5. Copy the FULL value and run this script again")

    console.print()
    console.print("You can now try the crawler:")
    console.print("  python crawl_transcripts.py --config config.yaml")


if __name__ == "__main__":
    main()
