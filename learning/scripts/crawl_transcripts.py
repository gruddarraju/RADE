"""
Transcript Crawler for Data Engineering Hub (learn.dataengineeringhub.in)

This script uses Playwright to:
1. Log into the platform with username/password
2. Auto-discover all courses and their lessons
3. Extract transcript text from each lesson's video
4. Save transcripts as organized .txt files under learning/transcripts/

Usage:
    python crawl_transcripts.py --config config.yaml
    python crawl_transcripts.py --config config.yaml --course "RADE Success Blueprint"
"""

import argparse
import re
import time
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import yaml
from playwright.sync_api import sync_playwright, Page, Browser
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the config.yaml file.

    Returns:
        Configuration dictionary with credentials and settings.
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug.

    Args:
        text: Input text to slugify.

    Returns:
        Lowercase, hyphenated, filesystem-safe string.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80]


def login(page: Page, base_url: str, email: str, password: str) -> bool:
    """Log into the Data Engineering Hub platform.

    First tries to use a saved session (from save_session.py).
    Falls back to programmatic login if no session file exists.

    Args:
        page: Playwright page instance.
        base_url: Base URL of the platform.
        email: User's email address.
        password: User's password.

    Returns:
        True if login was successful, False otherwise.
    """
    console.print("[bold blue]Verifying authentication...[/bold blue]")

    # Navigate to a protected page to check if session is valid
    page.goto(f"{base_url}/courses", wait_until="load", timeout=30000)
    time.sleep(3)

    # If we're not redirected to login, session is valid
    if "/login" not in page.url and "/sign_in" not in page.url:
        console.print("[bold green]Session is valid! Already authenticated.[/bold green]")
        return True

    # Session expired or missing — try programmatic login
    console.print("[yellow]Session expired. Attempting programmatic login...[/yellow]")

    login_url = f"{base_url}/login"
    page.goto(login_url, wait_until="load", timeout=30000)
    time.sleep(3)

    # Fill email field
    try:
        page.fill('input#email[name="email"]', email)
    except Exception:
        try:
            page.fill('input[type="email"][name="email"]', email)
        except Exception:
            console.print("[red]Could not find email input field[/red]")
            return False

    # Fill password field
    try:
        page.fill('input#login-password', password)
    except Exception:
        try:
            page.fill('input[type="password"][name="password"]', password)
        except Exception:
            console.print("[red]Could not find password input field[/red]")
            return False

    # Click the LOGIN button
    try:
        page.locator('button:has-text("LOGIN")').click()
    except Exception:
        try:
            page.locator('button.btn.btn-default.btn-block').click()
        except Exception:
            console.print("[red]Could not find login button[/red]")
            return False

    # Wait for navigation after login
    try:
        page.wait_for_load_state("load", timeout=15000)
    except Exception:
        pass
    time.sleep(5)

    # Verify login success
    if "/login" not in page.url:
        console.print("[bold green]Login successful![/bold green]")
        return True
    else:
        console.print("[red]Login failed — CAPTCHA likely blocking.[/red]")
        console.print("[yellow]Run 'python save_session.py' to login manually and save your session.[/yellow]")
        return False


def discover_courses(page: Page, base_url: str) -> list[dict]:
    """Discover all available courses on the platform.

    Handles Zenler's bundle structure where a membership/bundle page
    lists individual sub-courses.

    Args:
        page: Playwright page instance.
        base_url: Base URL of the platform.

    Returns:
        List of dicts with 'name' and 'url' for each course.
    """
    console.print("[bold blue]Discovering courses...[/bold blue]")

    page.goto(f"{base_url}/courses", wait_until="load", timeout=30000)
    time.sleep(5)

    courses = []
    visited_bundles = set()

    # Find all course/bundle links on the courses page
    links = page.locator('a[href*="/courses/"]').all()
    bundle_urls = []

    for link in links:
        try:
            href = link.get_attribute("href")
            if not href or "/courses/" not in href:
                continue
            full_url = href if href.startswith("http") else f"{base_url}{href}"
            # Skip buy/plan links
            if "/buy/" in full_url or "/plan" in full_url:
                continue
            if full_url not in bundle_urls:
                bundle_urls.append(full_url)
        except Exception:
            continue

    # For each bundle/course, check if it contains sub-courses
    for bundle_url in bundle_urls:
        if bundle_url in visited_bundles:
            continue
        visited_bundles.add(bundle_url)

        try:
            page.goto(bundle_url, wait_until="load", timeout=30000)
            time.sleep(3)

            # Check if this page has sub-course links (bundle page)
            sub_links = page.locator('[class*="curriculum"] a[href*="/courses/"], [class*="content"] a[href*="/courses/"]').all()
            sub_courses_found = False

            for sub_link in sub_links:
                try:
                    sub_href = sub_link.get_attribute("href")
                    sub_text = sub_link.inner_text().strip()
                    if not sub_href or not sub_text or "/buy/" in sub_href:
                        continue
                    # Filter out garbage entries (START, RESUME, etc.)
                    if sub_text.upper() in ("START", "RESUME", ""):
                        continue
                    if len(sub_text) < 5:
                        continue

                    sub_url = sub_href if sub_href.startswith("http") else f"{base_url}{sub_href}"
                    if sub_url != bundle_url and not any(c["url"] == sub_url for c in courses):
                        courses.append({"name": sub_text, "url": sub_url})
                        sub_courses_found = True
                except Exception:
                    continue

            # If no sub-courses, this is a standalone course
            if not sub_courses_found:
                title = page.title().replace("RADE™", "").strip()
                # Filter garbage
                if title and len(title) > 5 and title.upper() not in ("START", "RESUME"):
                    if not any(c["url"] == bundle_url for c in courses):
                        courses.append({"name": title, "url": bundle_url})

        except Exception:
            continue

    console.print(f"[green]Found {len(courses)} course(s)[/green]")
    for course in courses:
        console.print(f"  - {course['name']}")

    return courses


def discover_lessons(page: Page, course_url: str) -> list[dict]:
    """Discover all lessons within a course.

    Handles the Zenler platform structure where courses have a /dashboard page
    with curriculum items containing START links.

    Args:
        page: Playwright page instance.
        course_url: URL of the course page.

    Returns:
        List of dicts with 'title', 'url', and 'section' for each lesson.
    """
    # Zenler redirects to /dashboard - go there directly
    dashboard_url = course_url.rstrip("/") + "/dashboard"
    page.goto(dashboard_url, wait_until="load", timeout=30000)
    time.sleep(5)

    lessons = []

    # On Zenler, lessons are links with href containing /contents/
    # The lesson title is in the grandparent element of the START link
    content_links = page.locator('a[href*="/contents/"]').all()

    for link in content_links:
        try:
            href = link.get_attribute("href")
            if not href:
                continue

            full_url = href if href.startswith("http") else f"https://learn.dataengineeringhub.in{href}"

            # Get lesson title from grandparent element
            grandparent = link.locator("../..")
            title_text = grandparent.inner_text().strip()

            # Remove "START" and clean up the title
            title = title_text.replace("START", "").replace("\n", " ").strip()
            # Remove trailing/leading whitespace and multiple spaces
            title = re.sub(r"\s+", " ", title).strip()

            if title and full_url not in [l["url"] for l in lessons]:
                lessons.append({
                    "title": title,
                    "url": full_url,
                    "section": "General",
                })
        except Exception:
            continue

    console.print(f"[green]Found {len(lessons)} lesson(s)[/green]")
    return lessons


def _download_vtt(page: Page, vtt_url: str, referer: str) -> str:
    """Download a signed Vimeo WebVTT caption resource.

    Args:
        page: Lesson page whose browser context owns the request client.
        vtt_url: Signed Vimeo caption URL.
        referer: Vimeo player URL that exposed the caption track.

    Returns:
        Raw WebVTT content.

    Raises:
        RuntimeError: If Vimeo rejects the request or the response is not VTT.
    """
    response = page.context.request.get(
        vtt_url,
        headers={
            "Accept": "text/vtt,text/plain;q=0.9,*/*;q=0.8",
            "Referer": referer,
        },
        timeout=20000,
    )
    if not response.ok:
        raise RuntimeError(
            f"Vimeo caption request failed with HTTP {response.status}"
        )

    content = response.text()
    if "WEBVTT" not in content:
        raise RuntimeError("Vimeo caption response was not WebVTT content")
    return content


def _extract_from_vimeo_player(
    page: Page,
    player_url: str,
    lesson_url: str,
) -> Optional[tuple[str, str]]:
    """Open a Vimeo player directly and retrieve its complete caption track."""
    observed_vtt_urls: list[str] = []

    def capture_caption_response(response) -> None:
        url = response.url
        if "captions.vimeo.com/captions/" in url or ".vtt" in url.lower():
            observed_vtt_urls.append(url)

    page.on("response", capture_caption_response)
    try:
        page.goto(
            player_url,
            referer=lesson_url,
            wait_until="domcontentloaded",
            timeout=30000,
        )
    except Exception:
        # Vimeo may keep analytics requests open even though the player DOM loaded.
        pass

    deadline = time.monotonic() + 35
    attempted_urls: set[str] = set()
    last_error = ""

    while time.monotonic() < deadline:
        candidates = list(observed_vtt_urls)
        tracks = page.locator("track[src]")
        try:
            for index in range(tracks.count()):
                src = tracks.nth(index).get_attribute("src")
                if src:
                    candidates.append(urljoin(player_url, src))
        except Exception as exc:
            last_error = f"Could not inspect direct Vimeo player: {exc}"

        for vtt_url in candidates:
            if vtt_url in attempted_urls:
                continue
            attempted_urls.add(vtt_url)
            try:
                vtt_content = _download_vtt(page, vtt_url, player_url)
                transcript = parse_vtt_to_text(vtt_content)
                if transcript:
                    return transcript, vtt_content
                last_error = "Downloaded caption track contained no readable cues"
            except Exception as exc:
                last_error = str(exc)

        time.sleep(1)

    if last_error:
        console.print(f"  [dim]{last_error}[/dim]")
    return None


def extract_transcript(page: Page, lesson_url: str) -> Optional[tuple[str, str]]:
    """Extract the complete Vimeo caption track for one lesson.

    Vimeo renders its transcript inside a cross-origin iframe. The parent
    NewZenler page cannot read the visible transcript panel directly, so this
    function polls the Vimeo frame for its hidden ``<track>`` element, then
    downloads the signed WebVTT resource exposed by that element.

    Args:
        page: Fresh Playwright page used only for this lesson.
        lesson_url: URL of the NewZenler lesson page.

    Returns:
        A tuple containing cleaned transcript text and the original WebVTT
        content, or None when the lesson exposes no downloadable caption track.
    """
    observed_vtt_urls: list[tuple[str, str]] = []

    def capture_caption_response(response) -> None:
        """Record caption URLs requested while Vimeo initializes."""
        url = response.url
        if "captions.vimeo.com/captions/" in url or ".vtt" in url.lower():
            observed_vtt_urls.append((url, response.request.headers.get("referer", "")))

    page.on("response", capture_caption_response)
    try:
        page.goto(lesson_url, wait_until="domcontentloaded", timeout=30000)
    except Exception as exc:
        if "/login" in page.url:
            raise RuntimeError("DEH session expired; export fresh cookies") from exc
        console.print(
            "  [dim]Lesson navigation did not become idle; "
            "continuing with the loaded document[/dim]"
        )

    if "/login" in page.url:
        raise RuntimeError("DEH session expired; export fresh cookies")

    # Prefer the exact Vimeo iframe URL. Opening it directly with the lesson as
    # referrer proved more reliable than waiting for NewZenler's nested player
    # frame to finish initializing.
    player_urls: list[str] = []
    iframe_deadline = time.monotonic() + 10
    while time.monotonic() < iframe_deadline and not player_urls:
        try:
            iframes = page.locator('iframe[src*="player.vimeo.com/video/"]')
            for index in range(iframes.count()):
                src = iframes.nth(index).get_attribute("src")
                if src:
                    player_urls.append(urljoin(lesson_url, src))
        except Exception:
            pass

        for frame in page.frames:
            if "player.vimeo.com/video/" in frame.url.lower():
                player_urls.append(frame.url)

        if not player_urls:
            time.sleep(1)

    for player_url in dict.fromkeys(player_urls):
        player_page = page.context.new_page()
        try:
            result = _extract_from_vimeo_player(
                player_page,
                player_url,
                lesson_url,
            )
            if result:
                return result
        finally:
            player_page.close()

    # Retain embedded-frame inspection as a fallback for player variants that
    # do not expose a stable iframe src on the parent lesson page.
    deadline = time.monotonic() + 20
    attempted_urls: set[str] = set()
    found_vimeo_frame = False
    last_error = ""

    while time.monotonic() < deadline:
        candidates = list(observed_vtt_urls)

        for frame in page.frames:
            if "player.vimeo.com/video/" not in frame.url.lower():
                continue

            found_vimeo_frame = True
            try:
                tracks = frame.locator("track[src]")
                for index in range(tracks.count()):
                    src = tracks.nth(index).get_attribute("src")
                    if src:
                        candidates.append((urljoin(frame.url, src), frame.url))
            except Exception as exc:
                last_error = f"Could not inspect Vimeo caption tracks: {exc}"

        for vtt_url, referer in candidates:
            if vtt_url in attempted_urls:
                continue
            attempted_urls.add(vtt_url)

            try:
                vtt_content = _download_vtt(page, vtt_url, referer)
                transcript = parse_vtt_to_text(vtt_content)
                if transcript:
                    return transcript, vtt_content
                last_error = "Downloaded caption track contained no readable cues"
            except Exception as exc:
                last_error = str(exc)

        time.sleep(1)

    if not found_vimeo_frame:
        console.print(f"  [dim]No Vimeo iframe found for {lesson_url}[/dim]")
    elif last_error:
        console.print(f"  [dim]{last_error}[/dim]")
    else:
        console.print("  [dim]Vimeo loaded, but no caption track was exposed[/dim]")
    return None


def parse_vtt_to_text(vtt_content: str) -> str:
    """Convert WebVTT cues into a complete, ordered plain-text transcript.

    Cue blocks are preserved in their original order. Only immediately
    repeated cues are removed; repeated speech later in the lesson is retained.

    Args:
        vtt_content: Raw content of a WebVTT caption file.

    Returns:
        Transcript text with one caption cue per line.
    """
    normalized = vtt_content.replace("\r\n", "\n").replace("\r", "\n")
    cue_blocks = re.split(r"\n{2,}", normalized)
    cues: list[str] = []
    previous_cue = ""

    for block in cue_blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        block_type = lines[0].upper()
        if block_type.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue

        timestamp_index = next(
            (index for index, line in enumerate(lines) if "-->" in line),
            None,
        )
        if timestamp_index is None:
            continue

        cue_text = " ".join(lines[timestamp_index + 1:])
        cue_text = re.sub(r"<[^>]+>", "", cue_text)
        cue_text = re.sub(r"\s+", " ", unescape(cue_text)).strip()

        if cue_text and cue_text != previous_cue:
            cues.append(cue_text)
            previous_cue = cue_text

    return "\n".join(cues)


def find_matching_module_folder(course_name: str, learning_dir: Path) -> Optional[Path]:
    """Find the matching module folder for a course by fuzzy-matching names.

    Searches through all phase folders and their subfolders to find a match
    based on keywords from the course name.

    Args:
        course_name: Name of the course from the platform.
        learning_dir: Root learning/ directory.

    Returns:
        Path to the matching module folder, or None if not found.
    """
    course_slug = slugify(course_name)
    course_words = set(course_slug.split("-")) - {"for", "and", "the", "of", "on", "a", "an", "with", "to", "in"}

    best_match = None
    best_score = 0

    # Walk through all phase directories
    for phase_dir in learning_dir.iterdir():
        if not phase_dir.is_dir() or phase_dir.name in ("scripts", "transcripts", "output"):
            continue

        # Check direct children (modules) and nested children (tracks)
        for folder in phase_dir.rglob("*"):
            if not folder.is_dir():
                continue
            folder_words = set(folder.name.split("-")) - {"for", "and", "the", "of", "on", "a", "an", "with", "to", "in", "01", "02", "03", "04", "05", "06", "07", "08", "09"}

            # Calculate overlap score
            if folder_words and course_words:
                overlap = len(course_words & folder_words)
                score = overlap / max(len(course_words), len(folder_words))
                if score > best_score and score >= 0.3:
                    best_score = score
                    best_match = folder

    return best_match


def save_transcript(
    transcript: str,
    course_name: str,
    lesson_title: str,
    lesson_index: int,
    output_dir: Path,
    learning_dir: Optional[Path] = None,
    raw_vtt: Optional[str] = None,
) -> Path:
    """Save cleaned text and, when available, the original Vimeo VTT.

    Attempts to find the corresponding module folder under learning/.
    Falls back to saving under the output_dir if no match is found.

    Args:
        transcript: Clean transcript text.
        course_name: Name of the course.
        lesson_title: Title of the lesson.
        lesson_index: Numeric index of the lesson.
        output_dir: Fallback output directory for transcripts.
        learning_dir: Root learning/ directory for folder matching.
        raw_vtt: Original WebVTT caption content for lossless preservation.

    Returns:
        Path to the saved plain-text transcript file.
    """
    # Try to find a matching module folder in the learning directory
    target_dir = None
    if learning_dir:
        target_dir = find_matching_module_folder(course_name, learning_dir)

    if target_dir:
        # Save directly into the module folder under a "transcripts" subfolder
        transcript_dir = target_dir / "transcripts"
    else:
        # Fallback: save under output_dir with course slug
        transcript_dir = output_dir / slugify(course_name)

    transcript_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{lesson_index:02d}-{slugify(lesson_title)}.txt"
    filepath = transcript_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Course: {course_name}\n")
        f.write(f"Lesson: {lesson_title}\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(transcript)

    if raw_vtt:
        with open(filepath.with_suffix(".vtt"), "w", encoding="utf-8") as f:
            f.write(raw_vtt)

    return filepath


def crawl_course(
    page: Page,
    course: dict,
    output_dir: Path,
    learning_dir: Optional[Path] = None,
    delay: float = 2.0,
) -> int:
    """Crawl all lessons in a course and extract transcripts.

    Args:
        page: Playwright page instance.
        course: Course dict with 'name' and 'url'.
        output_dir: Fallback output directory for transcripts.
        learning_dir: Root learning/ directory for folder matching.
        delay: Delay between requests in seconds.

    Returns:
        Number of transcripts successfully extracted.
    """
    console.print(f"\n[bold cyan]Processing course: {course['name']}[/bold cyan]")

    lessons = discover_lessons(page, course["url"])
    if not lessons:
        console.print("[yellow]No lessons found for this course[/yellow]")
        return 0

    success_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting transcripts...", total=len(lessons))

        for i, lesson in enumerate(lessons, 1):
            progress.update(task, description=f"[{i}/{len(lessons)}] {lesson['title'][:50]}")

            try:
                # Use a fresh page for each lesson to avoid iframe contamination
                lesson_page = page.context.new_page()
                try:
                    extraction = extract_transcript(lesson_page, lesson["url"])
                finally:
                    lesson_page.close()

                if extraction:
                    transcript, raw_vtt = extraction
                    filepath = save_transcript(
                        transcript=transcript,
                        course_name=course["name"],
                        lesson_title=lesson["title"],
                        lesson_index=i,
                        output_dir=output_dir,
                        learning_dir=learning_dir,
                        raw_vtt=raw_vtt,
                    )
                    console.print(f"  [green]Saved:[/green] {filepath.name}")
                    success_count += 1
                else:
                    console.print(f"  [yellow]No transcript:[/yellow] {lesson['title']}")
            except Exception as e:
                console.print(f"  [red]Error:[/red] {lesson['title']} - {e}")

            time.sleep(delay)
            progress.advance(task)

    return success_count


def main():
    """Main entry point for the transcript crawler."""
    parser = argparse.ArgumentParser(
        description="Crawl and extract video transcripts from Data Engineering Hub"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config.yaml file (default: config.yaml)",
    )
    parser.add_argument(
        "--course",
        type=str,
        default=None,
        help="Filter to a specific course by name (partial match)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: visible)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests in seconds (default: 2.0)",
    )
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        # Try relative to script location
        config_path = Path(__file__).parent / args.config
    if not config_path.exists():
        console.print(f"[red]Config file not found: {args.config}[/red]")
        console.print("Create a config.yaml file. See config.yaml.example for reference.")
        return

    config = load_config(str(config_path))
    credentials = config["credentials"]
    base_url = config.get("base_url", "https://learn.dataengineeringhub.in")
    output_dir = Path(config.get("output_dir", str(Path(__file__).parent.parent / "transcripts")))
    learning_dir = Path(__file__).parent.parent  # learning/ folder

    console.print("[bold]RADE Transcript Crawler[/bold]")
    console.print(f"Platform: {base_url}")
    console.print(f"Output: {output_dir}")
    console.print()

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=args.headless)

        # Load saved session if available
        session_file = Path(__file__).parent / "session_state.json"
        context_kwargs = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if session_file.exists():
            context_kwargs["storage_state"] = str(session_file)
            console.print("[dim]Using saved session from session_state.json[/dim]")

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        try:
            # Step 1: Login
            if not login(page, base_url, credentials["email"], credentials["password"]):
                console.print("[red]Failed to login. Check your credentials.[/red]")
                return

            # Step 2: Discover courses
            courses = discover_courses(page, base_url)
            if not courses:
                console.print("[red]No courses found. The platform structure may have changed.[/red]")
                return

            # Step 3: Filter courses if specified
            if args.course:
                courses = [
                    c for c in courses
                    if args.course.lower() in c["name"].lower()
                ]
                if not courses:
                    console.print(f"[red]No course matching '{args.course}' found[/red]")
                    return

            # Step 4: Crawl each course
            total_transcripts = 0
            for course in courses:
                count = crawl_course(page, course, output_dir, learning_dir=learning_dir, delay=args.delay)
                total_transcripts += count

            console.print(f"\n[bold green]Done! Extracted {total_transcripts} transcript(s)[/bold green]")
            console.print(f"Transcripts saved to: {output_dir}")

        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
