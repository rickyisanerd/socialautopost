# Client Onboarding Runbook

Step-by-step process for adding a new business client to SocialAutoPost.
Tested and documented from the New Beginning Autos Care onboarding.

---

## Prerequisites

Before starting, you need from the client:
- Business name, address, phone, website
- What services they offer
- Their brand colors (hex codes — pull from their website/logo)
- Access to their Facebook Business Page (admin role)
- Instagram business account connected to that Facebook Page

From you:
- Meta Developer App (already created: App ID and App Secret from App Settings > Basic)
- Anthropic API key (already set in Railway env vars)
- Access to the Railway deployment

---

## Step 1: Meta Developer Portal Setup (15-30 min)

This is the hardest part. Everything else is fast.

### 1a. Add the client's Facebook Page to your Meta App

1. Go to https://developers.facebook.com/apps/
2. Select your app
3. Go to App Settings > Advanced
4. The client's Facebook Page needs to be connected to your app

### 1b. Get permissions in Graph API Explorer

1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app from the dropdown
3. Click "Generate Access Token"
4. **CRITICAL**: Check these permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `pages_show_list`
   - `instagram_basic`
   - `instagram_content_publish`
5. Click "Generate Access Token" — this gives you a SHORT-LIVED user token
6. **CRITICAL**: Change the "User or Page" dropdown from "User Token" to the client's page name
   - This is the step most people miss
   - The dropdown is right next to the token field

### 1c. Exchange for permanent token

Run the token exchange tool:

```
python tools/meta_token_exchange.py \
  --user-token "PASTE_SHORT_LIVED_TOKEN" \
  --app-id "YOUR_APP_ID" \
  --app-secret "YOUR_APP_SECRET"
```

This outputs:
- Page ID
- Permanent page access token (expires_at=0)
- Instagram Business Account ID (if connected)

**Save all three values — you need them in Step 2.**

### 1d. Instagram-specific setup (if needed)

If Instagram account ID doesn't appear:

1. Go to Meta Business Suite (business.facebook.com)
2. Settings > Accounts > Instagram accounts
3. Connect the client's Instagram business account
4. Go back to your Meta Developer App
5. App Roles > Roles > Add Instagram Testers
6. Add the client's Instagram username
7. The client must accept the tester invitation:
   Instagram app > Settings > Account > App and Websites > Tester Invitations
8. Re-run `meta_token_exchange.py` with a fresh short-lived token

---

## Step 2: Onboard in SocialAutoPost (5 min)

### Option A: Interactive CLI (recommended)

```
python tools/onboard_client.py
```

Follow the prompts. It will:
- Create the business record
- Add platform credentials
- Verify credentials work
- Optionally fire a test post

### Option B: Via deployed dashboard

1. Go to https://web-production-23e8a.up.railway.app/dashboard
2. Click "Add Business"
3. Fill out the form
4. On the business detail page, add platform credentials:
   - Facebook: `{"page_id": "...", "access_token": "..."}`
   - Instagram: `{"ig_account_id": "...", "access_token": "..."}`

### Option C: Via API (for scripting)

```python
import requests, json
BASE = "https://web-production-23e8a.up.railway.app"

# Create business
requests.post(f"{BASE}/api/businesses", data={
    "name": "Business Name",
    "description": "What they do",
    "industry": "Their Industry",
    "location": "City, State",
    "services": "service1, service2",
    "brand_color_primary": "#1a3a5c",
    "brand_color_secondary": "#f5a623",
    "tone": "friendly and professional",
    "target_audience": "Their customers",
    "posting_days": "tuesday,friday",
    "posting_time": "10:00",
    "timezone": "America/Chicago",
}, allow_redirects=False)

# Add Facebook (business_id = 1, adjust as needed)
requests.post(f"{BASE}/api/businesses/1/platforms", data={
    "platform": "facebook",
    "credentials_json": json.dumps({
        "page_id": "PAGE_ID_HERE",
        "access_token": "TOKEN_HERE",
    }),
}, allow_redirects=False)

# Add Instagram
requests.post(f"{BASE}/api/businesses/1/platforms", data={
    "platform": "instagram",
    "credentials_json": json.dumps({
        "ig_account_id": "IG_ACCOUNT_ID_HERE",
        "access_token": "TOKEN_HERE",  # Same token as Facebook
    }),
}, allow_redirects=False)
```

---

## Step 3: Verify (2 min)

```
python tools/verify_platforms.py --business-id <ID>
```

Or trigger a test post:
```
POST https://web-production-23e8a.up.railway.app/api/businesses/<ID>/post-now
```

Check the dashboard to confirm delivery status for each platform.

---

## Step 4: Done

The scheduler handles everything from here:
- Posts automatically on the configured days/times
- Generates unique content each time via Claude API
- Creates branded images with the business's colors
- Posts to all connected platforms

---

## Troubleshooting

### "Insufficient Developer Role" (Instagram)
The Instagram account needs to be added as a Tester in your Meta App.
App Dashboard > App Roles > Roles > Add Instagram Testers.

### Token stops working
Meta can invalidate tokens if:
- App permissions change
- User changes their Facebook password
- The app's access is removed from the page

Fix: Re-run `meta_token_exchange.py` with a fresh short-lived token and update the credential in the dashboard.

### Instagram post fails with "image URL" error
Instagram requires publicly accessible image URLs. The app serves images from `/static/images/`. Make sure:
- The `BASE_URL` env var is set to the public Railway URL
- The Railway deployment is running

### "Media ID is not available" (Instagram)
Race condition — the image container wasn't ready. Usually resolves on retry. If persistent, the image might not be accessible from Meta's servers.

### Facebook shows wrong page
The Page ID in Graph API Explorer URL might differ from the actual API Page ID. Use the `/me/accounts` endpoint to get the real page IDs:
```
GET https://graph.facebook.com/v21.0/me/accounts?access_token=TOKEN
```

---

## Platform Status

| Platform   | Status     | Notes |
|-----------|------------|-------|
| Facebook  | WORKING    | Permanent page token via Graph API |
| Instagram | WORKING    | Same token as Facebook, needs public image URLs |
| X/Twitter | NOT SET UP | Needs developer account at developer.x.com |
| LinkedIn  | NOT SET UP | Needs Marketing Developer Platform approval |
| TikTok    | BLOCKED    | Content Posting API requires partner access, cannot automate |

---

## Client Checklist Template

Copy this for each new client:

```
Client: _______________
Date onboarded: _______________
Onboarded by: _______________

[ ] Got business info (name, address, services, brand colors)
[ ] Got admin access to their Facebook Page
[ ] Confirmed Instagram business account connected to Page
[ ] Generated short-lived token in Graph API Explorer
    - [ ] pages_manage_posts
    - [ ] pages_read_engagement  
    - [ ] pages_show_list
    - [ ] instagram_basic
    - [ ] instagram_content_publish
[ ] Exchanged for permanent page token (expires_at=0)
[ ] Got Page ID: _______________
[ ] Got Instagram Account ID: _______________
[ ] Created business in SocialAutoPost (ID: ___)
[ ] Added Facebook credentials
[ ] Added Instagram credentials
[ ] Verified Facebook credential works
[ ] Verified Instagram credential works
[ ] Fired test post — confirmed on Facebook
[ ] Fired test post — confirmed on Instagram
[ ] Scheduler confirmed running
```
