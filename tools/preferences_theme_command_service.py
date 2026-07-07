from __future__ import annotations

import argparse
import json
import re
import sqlite3
from typing import Any, Callable

from bi_cli_core import now_iso


DEFAULT_USER_PREFERENCES = {
    "requireDeleteNameConfirmation": True,
    "autoSaveDashboardOnSwitch": False,
    "agentCanManageGeneratedAssets": True,
    "agentCanManageManualAssets": False,
    "themeKey": "L1",
}

REQUIRED_THEME_TOKENS = {
    "railTop",
    "railMid",
    "railBottom",
    "railActive",
    "primary",
    "primaryHover",
    "selected",
    "soft",
    "bg",
    "surface",
    "panel",
    "border",
    "text",
    "muted",
}

DEFAULT_THEME_PALETTES = [
    {
        "themeKey": "L1",
        "name": "L1 商务蓝青",
        "mode": "light",
        "sort": 10,
        "tokens": {
            "railTop": "#155F76",
            "railMid": "#1B5063",
            "railBottom": "#1C3846",
            "railActive": "#174B5C",
            "primary": "#116A82",
            "primaryHover": "#15546A",
            "selected": "#E3F6FA",
            "soft": "#F1FBFD",
            "bg": "#F5F8FB",
            "surface": "#FFFFFF",
            "panel": "#F8FAFC",
            "border": "#D7E2EC",
            "text": "#172033",
            "muted": "#5D6B7C",
        },
    },
    {
        "themeKey": "L2",
        "name": "L2 青墨绿",
        "mode": "light",
        "sort": 20,
        "tokens": {
            "railTop": "#1D6B63",
            "railMid": "#20554F",
            "railBottom": "#1D3A38",
            "railActive": "#1B4B45",
            "primary": "#0D7C68",
            "primaryHover": "#0E6355",
            "selected": "#E1F7F0",
            "soft": "#F0FCF8",
            "bg": "#F6F8F7",
            "surface": "#FFFFFF",
            "panel": "#FAFBFA",
            "border": "#D9E5E2",
            "text": "#172033",
            "muted": "#5F6B74",
        },
    },
    {
        "themeKey": "L3",
        "name": "L3 明亮湖蓝",
        "mode": "light",
        "sort": 30,
        "tokens": {
            "railTop": "#087E98",
            "railMid": "#126D83",
            "railBottom": "#1A4350",
            "railActive": "#105D70",
            "primary": "#0B7F9A",
            "primaryHover": "#12677B",
            "selected": "#E2FAFF",
            "soft": "#F0FDFF",
            "bg": "#F5F8FB",
            "surface": "#FFFFFF",
            "panel": "#F8FBFD",
            "border": "#D6E2EC",
            "text": "#172033",
            "muted": "#5F6B7B",
        },
    },
    {
        "themeKey": "D1",
        "name": "D1 深海青",
        "mode": "dark",
        "sort": 40,
        "tokens": {
            "railTop": "#0B4F63",
            "railMid": "#0B3A49",
            "railBottom": "#0A2029",
            "railActive": "#092F3B",
            "primary": "#0B6C76",
            "primaryHover": "#085863",
            "selected": "#123B45",
            "soft": "#0F2B34",
            "bg": "#08141B",
            "surface": "#0D1D26",
            "panel": "#102833",
            "border": "#214350",
            "text": "#EAF4F7",
            "muted": "#9AB0BA",
        },
    },
    {
        "themeKey": "D2",
        "name": "D2 墨绿夜航",
        "mode": "dark",
        "sort": 50,
        "tokens": {
            "railTop": "#125B52",
            "railMid": "#0F403B",
            "railBottom": "#0A2424",
            "railActive": "#0D3733",
            "primary": "#0A6C59",
            "primaryHover": "#075947",
            "selected": "#143D37",
            "soft": "#0F2B29",
            "bg": "#081615",
            "surface": "#0E201F",
            "panel": "#122C2A",
            "border": "#254B47",
            "text": "#EAF7F4",
            "muted": "#9DB7B1",
        },
    },
]


def normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def normalize_user_preferences(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    theme_key = str(payload.get("themeKey", DEFAULT_USER_PREFERENCES["themeKey"]) or "").strip()
    return {
        "requireDeleteNameConfirmation": normalize_bool(payload.get("requireDeleteNameConfirmation"), DEFAULT_USER_PREFERENCES["requireDeleteNameConfirmation"]),
        "autoSaveDashboardOnSwitch": normalize_bool(payload.get("autoSaveDashboardOnSwitch"), DEFAULT_USER_PREFERENCES["autoSaveDashboardOnSwitch"]),
        "agentCanManageGeneratedAssets": normalize_bool(payload.get("agentCanManageGeneratedAssets"), DEFAULT_USER_PREFERENCES["agentCanManageGeneratedAssets"]),
        "agentCanManageManualAssets": normalize_bool(payload.get("agentCanManageManualAssets"), DEFAULT_USER_PREFERENCES["agentCanManageManualAssets"]),
        "themeKey": theme_key or DEFAULT_USER_PREFERENCES["themeKey"],
    }


def normalize_theme_tokens(value: Any) -> dict[str, str]:
    payload = value if isinstance(value, dict) else {}
    tokens: dict[str, str] = {}
    for key in REQUIRED_THEME_TOKENS:
        color = str(payload.get(key, "") or "").strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            tokens[key] = color.upper()
    return tokens


def normalize_theme_palette(value: dict[str, Any]) -> dict[str, Any]:
    theme_key = str(value.get("themeKey") or value.get("theme_key") or "").strip()
    name = str(value.get("name") or theme_key).strip()
    mode = str(value.get("mode") or "light").strip().lower()
    tokens = normalize_theme_tokens(value.get("tokens") or value.get("tokens_json") or {})
    return {
        "themeKey": theme_key,
        "name": name or theme_key,
        "mode": mode if mode in {"light", "dark"} else "light",
        "tokens": tokens,
        "enabled": normalize_bool(value.get("enabled"), True),
        "sort": int(value.get("sort", value.get("sort_order", 0)) or 0),
        "createdBy": str(value.get("createdBy") or value.get("created_by") or "manual"),
    }


def validate_theme_palette_payload(value: dict[str, Any]) -> dict[str, Any]:
    palette = normalize_theme_palette(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", palette["themeKey"]):
        raise ValueError("Theme key must contain only letters, numbers, underscore or dash, length 2-40.")
    if not palette["name"]:
        raise ValueError("Theme name is required.")
    missing = sorted(REQUIRED_THEME_TOKENS - set(palette["tokens"]))
    if missing:
        raise ValueError(f"Theme tokens are incomplete: {', '.join(missing)}")
    return palette


def ensure_default_preferences_and_themes(connection: sqlite3.Connection) -> None:
    timestamp = now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO user_preferences(preference_key, preferences_json, created_at, updated_at)
        VALUES('default', ?, ?, ?)
        """,
        (json.dumps(DEFAULT_USER_PREFERENCES, ensure_ascii=False), timestamp, timestamp),
    )
    for palette in DEFAULT_THEME_PALETTES:
        connection.execute(
            """
            INSERT INTO theme_palettes(theme_key, name, mode, tokens_json, enabled, sort_order, created_by, created_at, updated_at)
            VALUES(?, ?, ?, ?, 1, ?, 'system', ?, ?)
            ON CONFLICT(theme_key) DO UPDATE SET
              name = excluded.name,
              mode = excluded.mode,
              tokens_json = excluded.tokens_json,
              enabled = 1,
              sort_order = excluded.sort_order,
              created_by = 'system',
              updated_at = excluded.updated_at
            WHERE theme_palettes.created_by = 'system'
            """,
            (
                palette["themeKey"],
                palette["name"],
                palette["mode"],
                json.dumps(palette["tokens"], ensure_ascii=False),
                palette["sort"],
                timestamp,
                timestamp,
            ),
        )


def load_user_preferences(connection: sqlite3.Connection) -> dict[str, Any]:
    ensure_default_preferences_and_themes(connection)
    row = connection.execute("SELECT preferences_json FROM user_preferences WHERE preference_key = 'default'").fetchone()
    if not row:
        return normalize_user_preferences({})
    try:
        payload = json.loads(row["preferences_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    return normalize_user_preferences(payload)


def save_user_preferences(connection: sqlite3.Connection, preferences: dict[str, Any]) -> dict[str, Any]:
    ensure_default_preferences_and_themes(connection)
    normalized = normalize_user_preferences(preferences)
    timestamp = now_iso()
    connection.execute(
        """
        INSERT INTO user_preferences(preference_key, preferences_json, created_at, updated_at)
        VALUES('default', ?, ?, ?)
        ON CONFLICT(preference_key) DO UPDATE SET
          preferences_json = excluded.preferences_json,
          updated_at = excluded.updated_at
        """,
        (json.dumps(normalized, ensure_ascii=False), timestamp, timestamp),
    )
    return normalized


def list_theme_palettes(connection: sqlite3.Connection, enabled_only: bool = True) -> list[dict[str, Any]]:
    ensure_default_preferences_and_themes(connection)
    where_sql = "WHERE enabled = 1" if enabled_only else ""
    rows = connection.execute(
        f"""
        SELECT theme_key, name, mode, tokens_json, enabled, sort_order, created_by, created_at, updated_at
        FROM theme_palettes
        {where_sql}
        ORDER BY sort_order, created_at
        """
    ).fetchall()
    palettes = []
    for row in rows:
        try:
            tokens = normalize_theme_tokens(json.loads(row["tokens_json"] or "{}"))
        except json.JSONDecodeError:
            tokens = {}
        if REQUIRED_THEME_TOKENS - set(tokens):
            continue
        palettes.append({
            "themeKey": row["theme_key"],
            "name": row["name"],
            "mode": row["mode"] if row["mode"] in {"light", "dark"} else "light",
            "tokens": tokens,
            "enabled": bool(row["enabled"]),
            "sort": row["sort_order"],
            "createdBy": row["created_by"] or "system",
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        })
    return palettes


def upsert_theme_palette(connection: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    palette = validate_theme_palette_payload(payload)
    row = connection.execute("SELECT created_by, created_at FROM theme_palettes WHERE theme_key = ?", (palette["themeKey"],)).fetchone()
    if row and (row["created_by"] or "system") == "system":
        raise ValueError("Built-in themes cannot be overwritten. Copy it as a custom theme first.")
    timestamp = now_iso()
    sort_order = int(palette.get("sort") or 0)
    if sort_order <= 0:
        sort_row = connection.execute("SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM theme_palettes").fetchone()
        sort_order = int(sort_row["max_sort"] or 0) + 10
    created_at = row["created_at"] if row and row["created_at"] else timestamp
    connection.execute(
        """
        INSERT INTO theme_palettes(theme_key, name, mode, tokens_json, enabled, sort_order, created_by, created_at, updated_at)
        VALUES(?, ?, ?, ?, 1, ?, 'manual', ?, ?)
        ON CONFLICT(theme_key) DO UPDATE SET
          name = excluded.name,
          mode = excluded.mode,
          tokens_json = excluded.tokens_json,
          enabled = 1,
          sort_order = excluded.sort_order,
          updated_at = excluded.updated_at
        """,
        (
            palette["themeKey"],
            palette["name"],
            palette["mode"],
            json.dumps(palette["tokens"], ensure_ascii=False),
            sort_order,
            created_at,
            timestamp,
        ),
    )
    return next(item for item in list_theme_palettes(connection, enabled_only=False) if item["themeKey"] == palette["themeKey"])


def delete_theme_palette(connection: sqlite3.Connection, theme_key: str) -> dict[str, Any]:
    key = str(theme_key or "").strip()
    row = connection.execute("SELECT theme_key, name, created_by FROM theme_palettes WHERE theme_key = ?", (key,)).fetchone()
    if not row:
        raise ValueError("Theme does not exist.")
    if (row["created_by"] or "system") == "system":
        raise ValueError("Built-in themes cannot be deleted.")
    if load_user_preferences(connection).get("themeKey") == key:
        raise ValueError("Switch to another theme before deleting the active theme.")
    connection.execute("UPDATE theme_palettes SET enabled = 0, updated_at = ? WHERE theme_key = ?", (now_iso(), key))
    return {"themeKey": row["theme_key"], "name": row["name"]}


def preferences_payload(connection: sqlite3.Connection) -> dict[str, Any]:
    preferences = load_user_preferences(connection)
    palettes = list_theme_palettes(connection)
    active_theme = next((item for item in palettes if item["themeKey"] == preferences.get("themeKey")), None)
    if not active_theme and palettes:
        preferences["themeKey"] = palettes[0]["themeKey"]
        active_theme = palettes[0]
    return {
        "ok": True,
        "preferences": preferences,
        "themePalettes": palettes,
        "activeTheme": active_theme,
        "source": "workspace user preferences and theme palette model",
    }


def preferences_command(args: argparse.Namespace, *, open_db: Callable[[], Any]) -> dict[str, Any]:
    with open_db() as connection:
        current = load_user_preferences(connection)
        updates: dict[str, Any] = {}
        if getattr(args, "theme_key", None):
            valid_themes = {item["themeKey"] for item in list_theme_palettes(connection)}
            if args.theme_key not in valid_themes:
                raise ValueError(f"Unknown or disabled theme: {args.theme_key}")
            updates["themeKey"] = args.theme_key
        for option, key in [
            ("require_delete_name_confirmation", "requireDeleteNameConfirmation"),
            ("auto_save_dashboard_on_switch", "autoSaveDashboardOnSwitch"),
            ("agent_can_manage_generated_assets", "agentCanManageGeneratedAssets"),
            ("agent_can_manage_manual_assets", "agentCanManageManualAssets"),
        ]:
            value = getattr(args, option, None)
            if value is not None:
                updates[key] = normalize_bool(value)
        if not updates:
            return preferences_payload(connection)
        proposed = normalize_user_preferences({**current, **updates})
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": current,
                "proposed": proposed,
                    "evidence": ["user-preferences", "workspace-sandbox", "confirmation-required"],
            }
        saved = save_user_preferences(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "preferences": saved}


def theme_palettes_command(args: argparse.Namespace, *, open_db: Callable[[], Any]) -> dict[str, Any]:
    action = str(args.action or "list")
    with open_db() as connection:
        if action == "list":
            return preferences_payload(connection)
        if action == "delete":
            if not args.theme_key:
                raise ValueError("--theme-key is required for delete.")
            if not args.yes:
                row = connection.execute(
                    "SELECT theme_key, name, created_by FROM theme_palettes WHERE theme_key = ?",
                    (args.theme_key,),
                ).fetchone()
                if not row:
                    raise ValueError("Theme does not exist.")
                return {
                    "ok": True,
                    "dryRun": True,
                    "requiresConfirmation": True,
                    "operation": "delete-theme",
                    "theme": dict(row),
                    "message": "Only custom themes can be disabled; built-in themes are protected.",
                }
            deleted = delete_theme_palette(connection, args.theme_key)
            connection.commit()
            return {"ok": True, "confirmed": True, "deletedThemePalette": deleted, **preferences_payload(connection)}
        if action not in {"save", "upsert"}:
            raise ValueError(f"Unsupported theme action: {action}")
        if not args.tokens_json:
            raise ValueError("--tokens-json is required for save.")
        try:
            tokens = json.loads(args.tokens_json)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid --tokens-json: {error}") from error
        payload = {
            "themeKey": args.theme_key,
            "name": args.name,
            "mode": args.mode,
            "tokens": tokens,
            "sort": args.sort,
        }
        proposed = validate_theme_palette_payload(payload)
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "operation": "save-theme",
                "proposedThemePalette": proposed,
                "evidence": ["b-theme-palette", "validated-theme-tokens", "confirmation-required"],
            }
        saved = upsert_theme_palette(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "savedThemePalette": saved, **preferences_payload(connection)}
