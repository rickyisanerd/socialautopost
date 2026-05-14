"""US holiday calendar for seasonal content generation.

Returns upcoming holidays so the AI can generate themed posts
with special offers, seasonal messaging, and holiday CTAs.
"""

from datetime import date, timedelta


def _easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of a weekday in a given month.
    weekday: 0=Monday ... 6=Sunday.  n: 1-based (1=first, -1=last)."""
    if n > 0:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        d = first + timedelta(days=offset + 7 * (n - 1))
    else:
        # Last occurrence
        if month == 12:
            last = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)
        offset = (last.weekday() - weekday) % 7
        d = last - timedelta(days=offset)
    return d


def get_holidays(year: int) -> list[dict]:
    """Return all US holidays for a given year with marketing context."""
    easter = _easter(year)

    return [
        {
            "name": "New Year's Day",
            "date": date(year, 1, 1),
            "theme": "new beginnings, fresh start, New Year specials",
            "promo_angle": "Start the year right — kick off with a special deal",
        },
        {
            "name": "Martin Luther King Jr. Day",
            "date": _nth_weekday(year, 1, 0, 3),  # 3rd Monday of January
            "theme": "community, service, honoring legacy",
            "promo_angle": "Serving our community with pride",
        },
        {
            "name": "Valentine's Day",
            "date": date(year, 2, 14),
            "theme": "love, appreciation, treat yourself or someone special",
            "promo_angle": "Show some love — Valentine's special deals",
        },
        {
            "name": "Presidents' Day",
            "date": _nth_weekday(year, 2, 0, 3),  # 3rd Monday of February
            "theme": "patriotic, President's Day sale tradition",
            "promo_angle": "Presidents' Day savings you can count on",
        },
        {
            "name": "St. Patrick's Day",
            "date": date(year, 3, 17),
            "theme": "lucky deals, green, Irish spirit",
            "promo_angle": "Your lucky day — special St. Patrick's deals",
        },
        {
            "name": "Easter",
            "date": easter,
            "theme": "spring renewal, family, Easter specials",
            "promo_angle": "Spring into savings this Easter",
        },
        {
            "name": "Cinco de Mayo",
            "date": date(year, 5, 5),
            "theme": "celebration, festive, cultural appreciation",
            "promo_angle": "Celebrate Cinco de Mayo with special offers",
        },
        {
            "name": "Mother's Day",
            "date": _nth_weekday(year, 5, 6, 2),  # 2nd Sunday of May
            "theme": "appreciation, gift-giving, treating mom",
            "promo_angle": "Make Mom's day — special deals for Mother's Day",
        },
        {
            "name": "Memorial Day",
            "date": _nth_weekday(year, 5, 0, -1),  # Last Monday of May
            "theme": "remembrance, patriotic, summer kickoff, sales",
            "promo_angle": "Memorial Day specials — honoring those who served",
        },
        {
            "name": "Juneteenth",
            "date": date(year, 6, 19),
            "theme": "freedom, celebration, community",
            "promo_angle": "Celebrating freedom and community this Juneteenth",
        },
        {
            "name": "Father's Day",
            "date": _nth_weekday(year, 6, 6, 3),  # 3rd Sunday of June
            "theme": "appreciation, gift-giving, treating dad",
            "promo_angle": "Celebrate Dad — Father's Day specials",
        },
        {
            "name": "Independence Day",
            "date": date(year, 7, 4),
            "theme": "patriotic, fireworks, summer celebration, 4th of July deals",
            "promo_angle": "4th of July blowout — celebrate with savings",
        },
        {
            "name": "Labor Day",
            "date": _nth_weekday(year, 9, 0, 1),  # 1st Monday of September
            "theme": "end of summer, hardworking Americans, Labor Day sale",
            "promo_angle": "Labor Day deals — because hard work deserves a reward",
        },
        {
            "name": "Halloween",
            "date": date(year, 10, 31),
            "theme": "spooky deals, costumes, scary-good savings, fall fun",
            "promo_angle": "Scary-good deals this Halloween",
        },
        {
            "name": "Veterans Day",
            "date": date(year, 11, 11),
            "theme": "honoring veterans, military appreciation, service",
            "promo_angle": "Thank you for your service — Veterans Day specials",
        },
        {
            "name": "Thanksgiving",
            "date": _nth_weekday(year, 11, 3, 4),  # 4th Thursday of November
            "theme": "gratitude, family, giving thanks, pre-Black Friday",
            "promo_angle": "Grateful for our customers — Thanksgiving specials",
        },
        {
            "name": "Black Friday",
            "date": _nth_weekday(year, 11, 3, 4) + timedelta(days=1),  # Day after Thanksgiving
            "theme": "biggest deals of the year, limited time, doorbuster savings",
            "promo_angle": "Black Friday blowout — our biggest deals of the year",
        },
        {
            "name": "Small Business Saturday",
            "date": _nth_weekday(year, 11, 3, 4) + timedelta(days=2),  # Saturday after Thanksgiving
            "theme": "shop local, support small business, community",
            "promo_angle": "Support local — Small Business Saturday deals",
        },
        {
            "name": "Christmas",
            "date": date(year, 12, 25),
            "theme": "holiday cheer, gift-giving, year-end deals, festive",
            "promo_angle": "Merry Christmas — holiday specials for you",
        },
        {
            "name": "New Year's Eve",
            "date": date(year, 12, 31),
            "theme": "year-end celebration, countdown, last chance deals",
            "promo_angle": "Ring in the New Year with last-chance savings",
        },
    ]


def get_upcoming_holiday(days_ahead: int = 7) -> dict | None:
    """Check if there's a holiday within the next `days_ahead` days.

    Returns the closest upcoming holiday dict, or None if nothing is near.
    Checks both current year and next year (for late December → January).
    """
    today = date.today()
    window = today + timedelta(days=days_ahead)

    # Check holidays for this year and next (handles Dec 28 → Jan 1 edge case)
    candidates = get_holidays(today.year) + get_holidays(today.year + 1)

    upcoming = [
        h for h in candidates
        if today <= h["date"] <= window
    ]

    if not upcoming:
        return None

    # Return the closest one
    upcoming.sort(key=lambda h: h["date"])
    return upcoming[0]
