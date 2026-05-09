"""
Helpers to enforce configured role allowlist.
"""

from typing import Iterable, List, Optional


def _normalize(value: str) -> str:
    return " ".join((value or "").lower().split())


def extract_allowed_role_from_query(query: str, permitted_roles: Iterable[str]) -> Optional[str]:
    normalized_query = _normalize(query)
    if not normalized_query:
        return None

    for role in permitted_roles:
        role_normalized = _normalize(role)
        if role_normalized and role_normalized in normalized_query:
            return role
    return None


def filter_allowed_roles(roles: Iterable[str], permitted_roles: Iterable[str]) -> List[str]:
    allowed_by_normalized = {_normalize(role): role for role in permitted_roles if _normalize(role)}
    filtered: List[str] = []

    for role in roles:
        match = allowed_by_normalized.get(_normalize(role))
        if match and match not in filtered:
            filtered.append(match)
    return filtered

