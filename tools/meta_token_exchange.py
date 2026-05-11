"""
Meta Token Exchange Utility
===========================
Converts a short-lived user token from Graph API Explorer into a permanent page token.

The chain: short-lived user token → long-lived user token → permanent page token

Usage:
    python tools/meta_token_exchange.py --user-token <TOKEN> --app-id <APP_ID> --app-secret <SECRET>

You get the short-lived user token from:
    https://developers.facebook.com/tools/explorer/
    - Select your app
    - Click "Generate Access Token"
    - Make sure these permissions are checked:
        pages_manage_posts, pages_read_engagement, pages_show_list,
        instagram_basic, instagram_content_publish
"""

import argparse
import httpx
import sys
import json

GRAPH_API = "https://graph.facebook.com/v21.0"


def exchange_for_long_lived(user_token: str, app_id: str, app_secret: str) -> str:
    """Exchange short-lived user token for long-lived user token (60 days)."""
    r = httpx.get(
        f"{GRAPH_API}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_token,
        },
    )
    data = r.json()
    if "access_token" not in data:
        print(f"FAILED to get long-lived token: {json.dumps(data, indent=2)}")
        sys.exit(1)
    print(f"Long-lived user token obtained (expires in {data.get('expires_in', '?')}s)")
    return data["access_token"]


def get_pages(long_lived_token: str) -> list[dict]:
    """List all pages the user manages."""
    r = httpx.get(
        f"{GRAPH_API}/me/accounts",
        params={"access_token": long_lived_token, "fields": "id,name,access_token"},
    )
    data = r.json()
    if "data" not in data:
        print(f"FAILED to list pages: {json.dumps(data, indent=2)}")
        sys.exit(1)
    return data["data"]


def get_instagram_account(page_id: str, page_token: str) -> dict | None:
    """Get the Instagram business account connected to a Facebook page."""
    r = httpx.get(
        f"{GRAPH_API}/{page_id}",
        params={"access_token": page_token, "fields": "instagram_business_account"},
    )
    data = r.json()
    ig = data.get("instagram_business_account")
    if not ig:
        return None

    # Get username
    r2 = httpx.get(
        f"{GRAPH_API}/{ig['id']}",
        params={"access_token": page_token, "fields": "id,username,name"},
    )
    return r2.json()


def verify_token_is_permanent(page_token: str) -> bool:
    """Check that the token doesn't expire."""
    r = httpx.get(
        f"{GRAPH_API}/debug_token",
        params={"input_token": page_token, "access_token": page_token},
    )
    data = r.json().get("data", {})
    expires = data.get("expires_at", -1)
    if expires == 0:
        print("Token is PERMANENT (expires_at=0)")
        return True
    else:
        print(f"WARNING: Token expires at {expires} — NOT permanent")
        return False


def main():
    parser = argparse.ArgumentParser(description="Exchange Meta short-lived token for permanent page token")
    parser.add_argument("--user-token", required=True, help="Short-lived user token from Graph API Explorer")
    parser.add_argument("--app-id", required=True, help="Meta App ID (from App Settings > Basic)")
    parser.add_argument("--app-secret", required=True, help="Meta App Secret (from App Settings > Basic)")
    parser.add_argument("--json-out", action="store_true", help="Output results as JSON for piping to onboard script")
    args = parser.parse_args()

    print("=" * 60)
    print("META TOKEN EXCHANGE")
    print("=" * 60)

    # Step 1: Exchange for long-lived token
    print("\n[1/4] Exchanging for long-lived user token...")
    ll_token = exchange_for_long_lived(args.user_token, args.app_id, args.app_secret)

    # Step 2: List pages
    print("\n[2/4] Fetching pages you manage...")
    pages = get_pages(ll_token)

    if not pages:
        print("No pages found. Make sure your token has pages_show_list permission.")
        sys.exit(1)

    print(f"Found {len(pages)} page(s):\n")
    for i, page in enumerate(pages):
        print(f"  [{i + 1}] {page['name']} (ID: {page['id']})")

    # Step 3: Select page
    if len(pages) == 1:
        selected = pages[0]
        print(f"\nAuto-selected: {selected['name']}")
    else:
        while True:
            choice = input(f"\nSelect page [1-{len(pages)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(pages):
                selected = pages[int(choice) - 1]
                break
            print("Invalid choice.")

    page_token = selected["access_token"]
    page_id = selected["id"]
    page_name = selected["name"]

    # Step 4: Verify permanence and check Instagram
    print(f"\n[3/4] Verifying token for '{page_name}'...")
    verify_token_is_permanent(page_token)

    print(f"\n[4/4] Checking for connected Instagram account...")
    ig_account = get_instagram_account(page_id, page_token)

    # Output
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Page Name:        {page_name}")
    print(f"Page ID:          {page_id}")
    print(f"Page Token:       {page_token[:20]}...{page_token[-10:]}")

    result = {
        "page_name": page_name,
        "page_id": page_id,
        "page_access_token": page_token,
    }

    if ig_account:
        ig_id = ig_account.get("id", "")
        ig_username = ig_account.get("username", "unknown")
        print(f"Instagram ID:     {ig_id}")
        print(f"Instagram User:   @{ig_username}")
        result["instagram_account_id"] = ig_id
        result["instagram_username"] = ig_username
    else:
        print("Instagram:        NOT CONNECTED")
        print("  → Connect Instagram in Meta Business Suite first,")
        print("    then re-run this tool.")

    print(f"\nFull token (copy this):\n{page_token}")

    if args.json_out:
        print(f"\n__JSON_OUTPUT__:{json.dumps(result)}")

    return result


if __name__ == "__main__":
    main()
