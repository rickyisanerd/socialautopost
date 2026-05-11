"""
Remote Client Deployment
=========================
Onboards a new client to the LIVE Railway deployment via API calls.
Use this instead of onboard_client.py when you want to add a client
to production without touching the local database.

Usage:
    python tools/deploy_client.py
    python tools/deploy_client.py --base-url https://your-app.up.railway.app
"""

import argparse
import json
import requests
import httpx


DEFAULT_BASE_URL = "https://web-production-23e8a.up.railway.app"
GRAPH_API = "https://graph.facebook.com/v21.0"


def ask(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    while True:
        val = input(f"  {prompt}: ").strip()
        if val:
            return val
        print("    (required)")


def ask_optional(prompt: str) -> str:
    return input(f"  {prompt} (Enter to skip): ").strip()


def ask_yn(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    val = input(f"  {prompt} {suffix}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def verify_facebook_remote(page_id: str, token: str) -> bool:
    r = httpx.get(f"{GRAPH_API}/{page_id}", params={"access_token": token})
    if r.status_code == 200:
        name = r.json().get("name", "unknown")
        print(f"    Facebook: VERIFIED (Page: {name})")
        return True
    print(f"    Facebook: FAILED — {r.json().get('error', {}).get('message', r.text)}")
    return False


def verify_instagram_remote(ig_id: str, token: str) -> bool:
    r = httpx.get(
        f"{GRAPH_API}/{ig_id}",
        params={"access_token": token, "fields": "id,username"},
    )
    if r.status_code == 200:
        username = r.json().get("username", "unknown")
        print(f"    Instagram: VERIFIED (@{username})")
        return True
    print(f"    Instagram: FAILED — {r.json().get('error', {}).get('message', r.text)}")
    return False


def create_business(base_url: str, data: dict) -> int | None:
    """Create business via API. Returns business ID or None."""
    r = requests.post(f"{base_url}/api/businesses", data=data, allow_redirects=False)
    if r.status_code == 303:
        # Extract ID from redirect Location header
        loc = r.headers.get("location", "")
        # /dashboard/business/5 → 5
        parts = loc.rstrip("/").split("/")
        try:
            return int(parts[-1])
        except (ValueError, IndexError):
            pass
    # Fallback: try to figure out ID from dashboard
    print(f"    Created (status {r.status_code}), checking dashboard...")
    html = requests.get(f"{base_url}/dashboard").text
    import re
    ids = [int(m) for m in re.findall(r'business/(\d+)', html)]
    return max(ids) if ids else None


def add_platform(base_url: str, biz_id: int, platform: str, creds: dict) -> bool:
    r = requests.post(
        f"{base_url}/api/businesses/{biz_id}/platforms",
        data={"platform": platform, "credentials_json": json.dumps(creds)},
        allow_redirects=False,
    )
    return r.status_code == 303


def main():
    parser = argparse.ArgumentParser(description="Deploy a new client to production")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Railway app URL")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print("=" * 60)
    print("SOCIALAUTOPOST — REMOTE CLIENT DEPLOYMENT")
    print(f"Target: {base}")
    print("=" * 60)

    # Verify app is reachable
    try:
        r = requests.get(f"{base}/dashboard", timeout=10)
        if r.status_code != 200:
            print(f"WARNING: Dashboard returned {r.status_code}")
    except Exception as e:
        print(f"CANNOT REACH APP: {e}")
        print("Is the Railway deployment running?")
        return

    # ─── Business Info ───────────────────────────────────────
    print("\n--- BUSINESS INFORMATION ---\n")
    biz_data = {
        "name": ask("Business name"),
        "description": ask("Short description"),
        "industry": ask("Industry"),
        "location": ask("Address/city"),
        "phone": ask_optional("Phone"),
        "website_url": ask_optional("Website URL"),
        "services": ask("Services (comma-separated)"),
        "target_audience": ask("Target audience"),
        "tone": ask("Brand tone", "friendly and professional"),
        "brand_color_primary": ask("Primary color (hex)", "#1a73e8"),
        "brand_color_secondary": ask("Secondary color (hex)", "#ffffff"),
        "posting_days": ask("Posting days", "tuesday,friday"),
        "posting_time": ask("Posting time", "10:00"),
        "timezone": ask("Timezone", "America/Chicago"),
    }

    print("\nCreating business on production...")
    biz_id = create_business(base, biz_data)
    if not biz_id:
        print("FAILED to create business. Check the app logs.")
        return
    print(f"Business created: ID={biz_id}")

    # ─── Platforms ───────────────────────────────────────────
    print("\n--- PLATFORM CREDENTIALS ---\n")
    platforms_added = []

    # Facebook
    print("[Facebook]")
    fb_token = ask_optional("Page Access Token")
    if fb_token:
        fb_page_id = ask("Page ID")
        verify_facebook_remote(fb_page_id, fb_token)
        if add_platform(base, biz_id, "facebook", {"page_id": fb_page_id, "access_token": fb_token}):
            platforms_added.append("facebook")
            print("    Added Facebook.\n")
        else:
            print("    FAILED to add Facebook.\n")
    else:
        print("    Skipped.\n")

    # Instagram
    print("[Instagram]")
    ig_token = ask_optional("Access Token (same as Facebook)")
    if ig_token:
        ig_id = ask("Instagram Business Account ID")
        verify_instagram_remote(ig_id, ig_token)
        if add_platform(base, biz_id, "instagram", {"ig_account_id": ig_id, "access_token": ig_token}):
            platforms_added.append("instagram")
            print("    Added Instagram.\n")
        else:
            print("    FAILED to add Instagram.\n")
    else:
        print("    Skipped.\n")

    # X/Twitter
    print("[X / Twitter]")
    x_key = ask_optional("API Key")
    if x_key:
        x_secret = ask("API Secret")
        x_token = ask("Access Token")
        x_token_secret = ask("Access Token Secret")
        creds = {"api_key": x_key, "api_secret": x_secret, "access_token": x_token, "access_token_secret": x_token_secret}
        if add_platform(base, biz_id, "x", creds):
            platforms_added.append("x")
            print("    Added X/Twitter.\n")
    else:
        print("    Skipped.\n")

    # LinkedIn
    print("[LinkedIn]")
    li_token = ask_optional("Access Token")
    if li_token:
        li_org = ask("Organization ID")
        if add_platform(base, biz_id, "linkedin", {"access_token": li_token, "org_id": li_org}):
            platforms_added.append("linkedin")
            print("    Added LinkedIn.\n")
    else:
        print("    Skipped.\n")

    # ─── Summary + Test ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"Business:   {biz_data['name']} (ID: {biz_id})")
    print(f"Platforms:  {', '.join(platforms_added) if platforms_added else 'NONE'}")
    print(f"Dashboard:  {base}/dashboard/business/{biz_id}")

    if platforms_added and ask_yn("\nFire a test post now?"):
        print("Triggering post cycle...")
        r = requests.post(f"{base}/api/businesses/{biz_id}/post-now", allow_redirects=False)
        if r.status_code == 303:
            print("Post cycle triggered. Check the dashboard for results.")
        else:
            print(f"Unexpected response: {r.status_code}")


if __name__ == "__main__":
    main()
