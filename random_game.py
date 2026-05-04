# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///

import argparse
import random
import re
import sys
import time

import requests

SEARCH_URL = "https://store.steampowered.com/search/results/"
APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://store.steampowered.com/search/?category1=998",
}

MATURE_COOKIES = {
    "birthtime": "568022401",
    "mature_content": "1",
    "wants_mature_content": "1",
}

NSFW_TAG_IDS = "5611,12095"

RATE_LIMIT_RETRY_AFTER = 60

STEAM_CATEGORIES = {
    "singleplayer": 4182,
    "indie": 492,
    "action": 19,
    "casual": 597,
    "adventure": 21,
    "2d": 3871,
    "3d": 4191,
    "simulation": 599,
    "strategy": 9,
    "rpg": 122,
}


def get_total_count(*, mode: str = "normal", category: int | None = None) -> int:
    params = {
        "query": "",
        "start": 0,
        "count": 1,
        "category1": 998,
        "infinite": 1,
    }
    cookies = MATURE_COOKIES if mode != "normal" else {}
    if mode == "nsfw":
        params["ignore_preferences"] = "1"
    elif mode == "nsfw_only":
        params["ignore_preferences"] = "1"
        params["tags"] = NSFW_TAG_IDS
    if category:
        if "tags" in params:
            params["tags"] += f",{category}"
        else:
            params["tags"] = category
    resp = steam_get(SEARCH_URL, params=params, headers=HEADERS, cookies=cookies)
    resp.raise_for_status()
    return resp.json()["total_count"]


def steam_get(url: str, **kwargs) -> requests.Response:
    for attempt in range(5):
        resp = requests.get(url, timeout=15, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", RATE_LIMIT_RETRY_AFTER))
            print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        return resp
    return resp


GAME_TYPES = {"game", "episode"}

SKIP_NAME_PATTERNS = ("demo", "playtest", "prologue", "beta", "alpha", "prototype", "teaser")

APP_RE = re.compile(r'<a\s+href="https://store\.steampowered\.com/app/(\d+)/[^"]*"[^>]*data-ds-appid="(\d+)"')
NAME_RE = re.compile(r'class="title">([^<]+)</span>')


def fetch_all_nsfw_apps(category: int | None = None) -> list[dict]:
    all_games = []
    start = 0
    while True:
        games = fetch_search_page(start, mode="nsfw_only", category=category)
        if not games:
            break
        all_games.extend(games)
        if len(games) < 100:
            break
        start += 100
        time.sleep(0.5)
    return all_games


def fetch_search_page(start: int, count: int = 100, *, mode: str = "normal", category: int | None = None) -> list[dict]:
    params = {
        "query": "",
        "start": start,
        "count": count,
        "category1": 998,
        "infinite": 1,
    }
    cookies = MATURE_COOKIES if mode != "normal" else {}
    if mode == "nsfw":
        params["ignore_preferences"] = "1"
    elif mode == "nsfw_only":
        params["ignore_preferences"] = "1"
        params["tags"] = NSFW_TAG_IDS
    if category:
        if "tags" in params:
            params["tags"] += f",{category}"
        else:
            params["tags"] = category

    try:
        resp = steam_get(SEARCH_URL, params=params, headers=HEADERS, cookies=cookies)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return []
        html = data.get("results_html", "")
        if not html or "No results" in html:
            return []
        app_ids = APP_RE.findall(html)
        names = NAME_RE.findall(html)
        games = []
        for i, (path_id, ds_id) in enumerate(app_ids):
            appid = int(ds_id)
            name = names[i].strip() if i < len(names) else f"App {appid}"
            games.append({"appid": appid, "name": name})
        return games
    except requests.RequestException as e:
        print(f"  Search request failed: {e}", file=sys.stderr)
        return []


def check_app_details(appid: int, *, mode: str = "normal") -> dict | str:
    cookies = MATURE_COOKIES if mode != "normal" else {}
    try:
        resp = steam_get(
            APP_DETAILS_URL,
            params={"appids": appid, "cc": "us", "l": "english"},
            headers=HEADERS,
            cookies=cookies,
        )
        resp.raise_for_status()
        data = resp.json()
        entry = data.get(str(appid), {})
        if not entry.get("success"):
            return "unavailable/delisted"
        app_data = entry["data"]
        app_type = app_data.get("type", "").lower()
        if app_type not in GAME_TYPES:
            return f"not a game (type={app_type!r})"
        if app_data.get("release_date", {}).get("coming_soon", False):
            return "unreleased"
        name_lower = app_data.get("name", "").lower()
        for p in SKIP_NAME_PATTERNS:
            if p in name_lower:
                return f"matches skip pattern {p!r}"
        platforms = app_data.get("platforms", {})
        if not platforms.get("windows") and not platforms.get("mac") and not platforms.get("linux"):
            return "no platforms listed"
        return app_data
    except requests.RequestException:
        return "request failed"


def pick_random_game(*, mode: str = "normal", category: int | None = None) -> dict:
    attempts = 0
    max_attempts = 30

    if mode == "nsfw_only":
        print("Fetching all NSFW games...")
        pool = fetch_all_nsfw_apps(category=category)
        if not pool:
            print("No NSFW games found.")
            sys.exit(1)
        print(f"  Found {len(pool)} NSFW-tagged games")
        random.shuffle(pool)
        for game in pool:
            attempts += 1
            appid = game["appid"]
            name = game["name"]
            print(f"  [{attempts}] Checking: {name} (id={appid})...", end=" ", flush=True)
            result = check_app_details(appid, mode=mode)
            if isinstance(result, dict):
                print("OK!")
                return result
            print(f"skipped ({result})")
            time.sleep(1.5)
        print("\nNo valid NSFW game found.")
        sys.exit(1)

    max_start = (get_total_count(mode=mode, category=category) // 100) * 100
    print("Searching for a random game...")

    for _ in range(max_attempts):
        attempts += 1
        start = random.randint(0, max_start // 100) * 100
        print(f"  [{attempts}] Fetching search page at offset {start}...", end=" ", flush=True)

        games = fetch_search_page(start, mode=mode, category=category)
        if not games:
            print("no results, trying another page")
            time.sleep(0.5)
            continue

        print(f"found {len(games)} apps")

        game = random.choice(games)
        appid = game["appid"]
        name = game["name"]
        print(f"    Checking: {name} (id={appid})...", end=" ", flush=True)

        result = check_app_details(appid, mode=mode)
        if isinstance(result, dict):
            print("OK!")
            return result
        print(f"skipped ({result})")
        time.sleep(1.5)

    print(f"\nNo valid game found after {max_attempts} attempts.")
    sys.exit(1)


def display_game(game: dict) -> None:
    name = game.get("name", "Unknown")
    appid = game.get("steam_appid", "?")
    developers = game.get("developers", [])
    publishers = game.get("publishers", [])
    release_date = game.get("release_date", {}).get("date", "Unknown")
    price = game.get("price_overview", {})
    if price:
        price_str = price.get("final_formatted", "Free")
        if price.get("discount_percent"):
            price_str += f" ({price['discount_percent']}% off)"
    else:
        price_str = "Free"

    genres = [g["description"] for g in game.get("genres", [])]
    url = f"https://store.steampowered.com/app/{appid}/"

    print("\n" + "=" * 60)
    print(f"  {name}")
    print("=" * 60)
    print(f"  App ID:       {appid}")
    if developers:
        print(f"  Developer(s): {', '.join(developers)}")
    if publishers:
        print(f"  Publisher(s): {', '.join(publishers)}")
    print(f"  Release date: {release_date}")
    print(f"  Price:        {price_str}")
    if genres:
        print(f"  Genre(s):     {', '.join(genres)}")
    print(f"  URL:          {url}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pick a random Steam game")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--nsfw", action="store_true", help="Include NSFW games in results")
    group.add_argument("--nsfw-only", action="store_true", help="Only pick NSFW games")
    parser.add_argument("--category", type=str, choices=STEAM_CATEGORIES.keys(), help="Pick games by category")
    args = parser.parse_args()

    if args.nsfw_only:
        mode = "nsfw_only"
    elif args.nsfw:
        mode = "nsfw"
    else:
        mode = "normal"

    game = pick_random_game(mode=mode, category=STEAM_CATEGORIES.get(args.category))
    display_game(game)


if __name__ == "__main__":
    main()
