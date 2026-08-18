#!/usr/bin/env python3
"""Post-scan deduplication and catalog aggregation helpers."""

from __future__ import annotations

import json
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by build_catalog.py for scan deduplication and catalog aggregation."


def normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\\", "/").lower()).strip()


def is_absolute_text(value: Any) -> bool:
    text = str(value or "").strip().replace("\\", "/")
    return bool(re.match(r"^(?:[A-Za-z]:/|//|/)", text))


def public_label(value: Any, include_absolute_paths: bool) -> str:
    text = str(value or "")
    return text if include_absolute_paths or not is_absolute_text(text) else "<absolute path hidden>"


def curation_value(mapping: Any, name: str, relative_path: str, selector: str = "") -> str:
    if not isinstance(mapping, dict):
        return ""
    normalized_name = normalize_for_match(name)
    normalized_path = normalize_for_match(relative_path)
    for key in (selector, relative_path, normalized_path, name, normalized_name):
        if not key:
            continue
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            localized = value.get("zh-CN") or value.get("description") or value.get("value")
            if isinstance(localized, str) and localized.strip():
                return localized.strip()
    return ""


def family_override(mapping: Any, item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    name = normalize_for_match(item.get("name", ""))
    relative = normalize_for_match(item.get("relative_path", ""))
    for key in (item.get("relative_path", ""), relative, item.get("name", ""), name):
        value = mapping.get(key)
        if isinstance(value, dict):
            return value
    return {}


def structural_family_root(item: Dict[str, Any]) -> str:
    parts = Path(str(item.get("relative_path") or "")).parts
    # A root SKILL.md is its own family; nested skills use their first directory.
    return str(item.get("root_basename") or item.get("name") or "skill") if len(parts) <= 1 else str(parts[0])


def family_override_for_structure(mapping: Any, item: Dict[str, Any]) -> Dict[str, Any]:
    """Apply an explicit family id to structurally related paths only.

    A curation entry such as ``tailwind -> ecosystem:hyperframes`` can cover
    the root ``hyperframes`` and its ``hyperframes-*`` siblings.  This is still
    path-derived and never inspects descriptions.
    """
    if not isinstance(mapping, dict):
        return {}
    root_name = normalize_for_match(structural_family_root(item))
    relative = normalize_for_match(item.get("relative_path", ""))
    for key, value in mapping.items():
        if not isinstance(value, dict):
            continue
        family_id = str(value.get("id") or value.get("family") or "").strip()
        if not family_id:
            continue
        slug = normalize_for_match(family_id.rsplit(":", 1)[-1])
        if not slug:
            continue
        if root_name == slug or root_name.startswith(slug + "-"):
            # Do not let an unrelated root-level entry inherit a sibling's
            # family merely because its name happens to share a token.
            selector = normalize_for_match(str(key))
            if selector and (selector in relative or root_name == slug or root_name.startswith(slug + "-")):
                return value
    return {}


def direct_skill_folder(item: Dict[str, Any]) -> str:
    """Return the direct folder name for a root-level ``SKILL.md`` item."""
    parts = Path(str(item.get("relative_path") or "")).parts
    if len(parts) != 2 or parts[-1].casefold() != "skill.md":
        return ""
    folder = normalize_for_match(parts[0])
    name = normalize_for_match(str(item.get("name") or ""))
    return folder if folder and folder == name else ""


def github_key(item: Dict[str, Any]) -> str:
    github = item.get("github")
    url = github.get("url") if isinstance(github, dict) else ""
    value = normalize_for_match(str(url or "")).rstrip("/")
    return re.sub(r"\.git$", "", value)


def deduplication_key(item: Dict[str, Any]) -> str:
    repository = github_key(item)
    name = normalize_for_match(str(item.get("name") or ""))
    kind = normalize_for_match(str(item.get("kind") or "skill")) or "skill"
    if not repository or not name:
        return ""
    if kind == "plugin":
        plugin_id = normalize_for_match(str(item.get("plugin_id") or ""))
        if not plugin_id:
            return ""
        return f"{kind}:{plugin_id}:{repository}:{name}"
    return f"{kind}:{repository}:{name}"


def deduplication_preference(item: Dict[str, Any]) -> Tuple[int, float, str, str, str]:
    return (
        0 if item.get("description_source") == "curation" else 1,
        -float(item.get("confidence", 0.0)),
        normalize_for_match(str(item.get("source") or "")),
        normalize_for_match(str(item.get("relative_path") or "")),
        str(item.get("id") or ""),
    )


def _json_unique(values: Iterable[Any]) -> List[Any]:
    encoded: Dict[str, Any] = {}
    for value in values:
        try:
            key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            key = str(value)
        encoded.setdefault(key, value)
    return [encoded[key] for key in sorted(encoded)]


def deduplicate_scan_records(
    items: List[Dict[str, Any]],
    raw_plugins: List[Dict[str, Any]],
    image_contexts: List[Tuple[Dict[str, Any], Path, Dict[str, Any], str, str, str, str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Tuple[Dict[str, Any], Path, Dict[str, Any], str, str, str, str, str]]]:
    """Collapse repository-backed copies before any remote image request.

    Repository and Skill name are the identity evidence. ``kind`` remains part
    of that identity so a plugin member cannot absorb an independent Skill.
    The primary record keeps all observed locations and repository evidence;
    plugin membership IDs are rewritten through the same alias map.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        key = deduplication_key(item) or f"item:{item.get('id') or len(groups)}"
        groups.setdefault(key, []).append(item)

    aliases: Dict[str, str] = {}
    deduplicated: List[Dict[str, Any]] = []
    for key, members in groups.items():
        primary = sorted(members, key=deduplication_preference)[0]
        primary_id = str(primary.get("id") or "")
        if not primary_id:
            continue
        for member in members:
            member_id = str(member.get("id") or "")
            if member_id:
                aliases[member_id] = primary_id

        location_evidence = _json_unique(
            evidence
            for member in members
            for evidence in (member.get("location_evidence") or [])
        )
        locations = sorted({
            str(location)
            for member in members
            for location in (member.get("locations") or [])
            if str(location)
        })
        github_evidence = _json_unique(
            evidence
            for member in members
            for evidence in (member.get("github_evidence") or [])
        )
        category_evidence = _json_unique(
            evidence
            for member in members
            for evidence in (member.get("category_evidence") or [])
        )
        primary["locations"] = locations
        primary["location_evidence"] = location_evidence
        if github_evidence:
            primary["github_evidence"] = github_evidence
        if category_evidence:
            primary["category_evidence"] = category_evidence
        if len(members) > 1:
            primary["deduplication"] = {
                "key": key,
                "repository": github_key(primary),
                "copy_count": len(members),
                "location_evidence": location_evidence,
            }
        deduplicated.append(primary)

    rewritten_plugins: List[Dict[str, Any]] = []
    for plugin in raw_plugins:
        skill_ids: List[str] = []
        for skill_id in plugin.get("skills", []):
            canonical_id = aliases.get(str(skill_id), str(skill_id))
            if canonical_id not in skill_ids:
                skill_ids.append(canonical_id)
        plugin["skills"] = skill_ids
        if skill_ids:
            rewritten_plugins.append(plugin)

    contexts_by_id: Dict[str, List[Tuple[Dict[str, Any], Path, Dict[str, Any], str, str, str, str, str]]] = {}
    for context in image_contexts:
        item_id = str(context[0].get("id") or "")
        canonical_id = aliases.get(item_id, item_id)
        contexts_by_id.setdefault(canonical_id, []).append(context)

    deduplicated_contexts: List[Tuple[Dict[str, Any], Path, Dict[str, Any], str, str, str, str, str]] = []
    for item in deduplicated:
        item_id = str(item.get("id") or "")
        contexts = contexts_by_id.get(item_id, [])
        if contexts:
            primary_context = next((context for context in contexts if context[0] is item), contexts[0])
            deduplicated_contexts.append(primary_context)

    return deduplicated, rewritten_plugins, deduplicated_contexts


def rooted_sibling_families(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Infer families installed as sibling root folders, conservatively.

    A prefix is considered a family only when a same-named root Skill exists and
    at least two sibling root Skills use that prefix. This catches repositories
    installed as ``research``, ``research-deep`` and ``research-report`` while
    avoiding loose prefix or description-based merges. Conflicting observed
    GitHub repositories are kept separate.
    """
    structural_buckets: Dict[Tuple[str, ...], Dict[str, List[Dict[str, Any]]]] = {}
    repository_buckets: Dict[Tuple[str, ...], Dict[str, List[Dict[str, Any]]]] = {}
    for item in items:
        if item.get("kind") != "skill":
            continue
        folder = direct_skill_folder(item)
        if not folder:
            continue
        repository = github_key(item)
        structural_key = (
            "root",
            normalize_for_match(str(item.get("source") or "skill")),
            normalize_for_match(str(item.get("root_basename") or "")),
        )
        structural_buckets.setdefault(structural_key, {}).setdefault(folder, []).append(item)
        if repository:
            repository_key = ("github", repository)
            repository_buckets.setdefault(repository_key, {}).setdefault(folder, []).append(item)

    inferred: Dict[str, Dict[str, Any]] = {}
    assigned: set[str] = set()
    for bucket_key, bucket in [*repository_buckets.items(), *structural_buckets.items()]:
        for parent_name in sorted(bucket, key=lambda value: (-len(value), value)):
            parents = bucket[parent_name]
            if len(parents) != 1:
                continue
            parent = parents[0]
            parent_id = str(parent.get("id") or "")
            if not parent_id or parent_id in assigned:
                continue
            children: List[Dict[str, Any]] = []
            prefix = parent_name + "-"
            for child_name, candidates in bucket.items():
                if not child_name.startswith(prefix) or len(candidates) != 1:
                    continue
                child = candidates[0]
                child_id = str(child.get("id") or "")
                if child_id and child_id not in assigned:
                    children.append(child)
            if len(children) < 2:
                continue

            members = [parent, *children]
            observed_repositories = {github_key(member) for member in members if github_key(member)}
            parent_repository = github_key(parent)
            if len(observed_repositories) > 1:
                if not parent_repository:
                    continue
                members = [member for member in members if not github_key(member) or github_key(member) == parent_repository]
                if len(members) < 3:
                    continue

            source = normalize_for_match(str(parent.get("source") or "skill")) or "skill"
            if bucket_key[0] == "github":
                family_id = f"family:github:{bucket_key[1]}:{parent_name}"
                family_evidence = {"type": "github-repository", "repository": bucket_key[1]}
            else:
                family_id = f"family:{source}:{parent_name}"
                family_evidence = {"type": "structural-sibling", "source": source}
            family = {
                "id": family_id,
                "name": str(parent.get("name") or parent_name),
                "category": str(parent.get("category") or "other"),
                "evidence": family_evidence,
            }
            for member in members:
                member_id = str(member.get("id") or "")
                if member_id:
                    inferred[member_id] = family
                    assigned.add(member_id)
    return inferred


def contained_skill_families(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group nested SKILL.md files under a real top-level entry point.

    Packages such as Tavily and CloudBase ship one root ``SKILL.md`` plus
    routed skills under ``skills/`` or ``references/``. The root entry point
    is structural proof of ownership; a shared directory name alone is not.
    """
    parents: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in items:
        if item.get("kind") != "skill":
            continue
        folder = direct_skill_folder(item)
        root_id = str(item.get("root_id") or "")
        if folder and root_id:
            parents[(root_id, folder)] = item

    inferred: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if item.get("kind") != "skill":
            continue
        parts = Path(str(item.get("relative_path") or "")).parts
        # The root entry itself is not evidence of a contained family. Only a
        # SKILL.md below that entry (for example tavily/skills/.../SKILL.md)
        # proves that this package owns routed child skills.
        if len(parts) <= 2:
            continue
        key = (str(item.get("root_id") or ""), normalize_for_match(parts[0]))
        parent = parents.get(key)
        if not parent:
            continue
        parent_id = str(parent.get("id") or "")
        item_id = str(item.get("id") or "")
        if not parent_id or not item_id:
            continue
        source = normalize_for_match(str(parent.get("source") or "skill")) or "skill"
        family = {
            "id": f"family:{source}:{key[0]}:{key[1]}",
            "name": str(parent.get("name") or key[1]),
            "category": str(parent.get("category") or "other"),
            "evidence": {
                "type": "contained-skill",
                "entry_point": str(parent.get("relative_path") or ""),
            },
        }
        inferred[parent_id] = family
        inferred[item_id] = family
    return inferred


@lru_cache(maxsize=512)
def _product_affiliation_patterns(product: str) -> Tuple[re.Pattern[str], ...]:
    """Compile each product's four explicit-affiliation rules once per run."""
    slug = normalize_for_match(product)
    if len(re.sub(r"[^a-z0-9]", "", slug)) < 6:
        return ()
    escaped = re.escape(slug)
    expressions = (
        rf"\b(?:for|inside|within|through|into|owned by)\s+(?:an?\s+)?{escaped}\b",
        rf"\b{escaped}\s+(?:project|projects|composition|compositions|runtime|adapter|workflow|skill|slideshow|video|deck|render|framework|cli)\b",
        rf"(?:^|\s)/{escaped}(?:\b|$)",
        rf"\bnpx\s+{escaped}\b",
    )
    return tuple(re.compile(expression, flags=re.IGNORECASE) for expression in expressions)


def _product_affiliation(description: str, product: str) -> bool:
    """Return true only for explicit owner/routing language."""
    normalized = normalize_for_match(description)
    return any(pattern.search(normalized) for pattern in _product_affiliation_patterns(product))


def product_affiliation_families(
    items: List[Dict[str, Any]],
    inferred: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Attach standalone domain skills to an explicitly named local product.

    This handles packages such as HyperFrames whose adapters and workflows are
    installed as sibling directories without relying on loose keyword matches.
    Ambiguous references are deliberately left as singletons.
    """
    parents = [
        item for item in items
        if item.get("kind") == "skill" and direct_skill_folder(item)
    ]
    result = dict(inferred)
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in result or item.get("kind") != "skill":
            continue
        description = str(item.get("source_description") or "")
        matches = [
            parent for parent in parents
            if parent.get("id") != item_id
            and _product_affiliation(description, str(parent.get("name") or ""))
        ]
        if len(matches) != 1:
            continue
        parent = matches[0]
        parent_id = str(parent.get("id") or "")
        family = result.get(parent_id)
        if not family:
            source = normalize_for_match(str(parent.get("source") or "skill")) or "skill"
            slug = normalize_for_match(str(parent.get("name") or "skill"))
            family = {
                "id": f"family:{source}:product:{slug}",
                "name": str(parent.get("name") or slug),
                "category": str(parent.get("category") or "other"),
                "evidence": {"type": "explicit-product-affiliation", "product": slug},
            }
            result[parent_id] = family
        result[item_id] = family
    return result


def family_identity(
    item: Dict[str, Any],
    config: Dict[str, Any],
    inferred: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[str, str, str]:
    mapping = config.get("curation", {}).get("family_overrides")
    override = (
        family_override(mapping, item)
        or family_override_for_structure(mapping, item)
        or (inferred or {}).get(str(item.get("id") or ""), {})
    )
    if override:
        family_id = str(override.get("id") or override.get("family") or item["name"])
        family_name = str(override.get("name") or family_id)
        category = str(override.get("category") or item["category"])
        return family_id, family_name, category
    # A family is an evidence-backed aggregate, not a synonym for the first
    # directory in a scanned path.  Keep unmatched records as singleton
    # families so container paths such as ``skills/alpha/SKILL.md`` cannot
    # turn the container name into a fabricated parent Skill.
    source = normalize_for_match(item.get("source", "skill")) or "skill"
    item_id = normalize_for_match(str(item.get("id") or item.get("name") or "skill"))
    family_name = str(item.get("name") or "skill")
    return f"family:{source}:singleton:{item_id}", family_name, str(item["category"])


def best_image_member(members: List[Dict[str, Any]], primary: Dict[str, Any]) -> Dict[str, Any]:
    status_rank = {
        "curated-local": 5,
        "github-repository": 4,
        "github-social-preview": 3,
        "verified-local": 2,
    }

    primary_repository = github_key(primary)

    def rank(item: Dict[str, Any]) -> Tuple[int, int, int, int, float, str]:
        image = item.get("image") if isinstance(item.get("image"), dict) else {}
        status = str(image.get("status") or "")
        evidence_rank = status_rank.get(status, 1 if not image.get("missing_evidence", True) else 0)
        image_repository = github_key({"github": {"url": image.get("repository")}})
        return (
            0 if status == "curated-local" else 1,
            0 if primary_repository and image_repository == primary_repository else 1,
            -evidence_rank,
            0 if item.get("id") == primary.get("id") else 1,
            -float(item.get("confidence", 0.0)),
            str(item.get("name") or "").casefold(),
        )

    return sorted(members, key=rank)[0]


def aggregate_github(primary: Dict[str, Any], image_member: Dict[str, Any], members: List[Dict[str, Any]]) -> Dict[str, Any]:
    for item in (primary, image_member, *members):
        github = item.get("github") if isinstance(item.get("github"), dict) else {}
        if github.get("url"):
            return github
    return {}


def assign_families(items: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    inferred = rooted_sibling_families(items)
    inferred.update(contained_skill_families(items))
    inferred = product_affiliation_families(items, inferred)
    for item in items:
        if item["kind"] != "skill":
            continue
        family_id, family_name, family_category = family_identity(item, config, inferred)
        item["family_id"] = family_id
        item["family_name"] = family_name
        item["family_category"] = family_category
        buckets.setdefault(family_id, []).append(item)

    families: List[Dict[str, Any]] = []
    for family_id, members in buckets.items():
        members.sort(key=lambda item: (
            0 if str(item["relative_path"]).casefold().endswith("/skill.md") else 1,
            len(Path(str(item["relative_path"])).parts),
            str(item["name"]).casefold(),
        ))
        expected_name = normalize_for_match(str(members[0].get("family_name") or ""))
        primary = sorted(
            members,
            key=lambda item: (
                0 if normalize_for_match(str(item.get("name") or "")) == expected_name else 1,
                0 if str(item["relative_path"]).casefold().endswith("/skill.md") else 1,
                len(Path(str(item["relative_path"])).parts),
                str(item["name"]).casefold(),
            ),
        )[0]
        for member in members:
            member["family_size"] = len(members)
            member["is_family_primary"] = member["id"] == primary["id"]
        category = str(primary.get("family_category") or primary["category"])
        image_member = best_image_member(members, primary)
        families.append({
            "id": family_id,
            "name": str(primary.get("family_name") or primary["name"]),
            "category": category,
            "description": primary["description"],
            "description_source": primary.get("description_source", "source"),
            "source": primary.get("source", "unknown"),
            "image": image_member["image"],
            "image_source_member_id": image_member["id"],
            "github": aggregate_github(primary, image_member, members),
            "invocation": primary["invocation"],
            "category_evidence": primary.get("category_evidence", []),
            "category_candidates": primary.get("category_candidates", []),
            "category_winner_margin": primary.get("category_winner_margin", 0),
            "category_tie_reason": primary.get("category_tie_reason", "unknown"),
            "confidence": primary.get("confidence", 0),
            "low_confidence": primary.get("low_confidence", False),
            "primary_id": primary["id"],
            "skill_ids": [member["id"] for member in members],
            "locations": sorted({
                str(location)
                for member in members
                for location in (member.get("locations") or [member["relative_path"]])
                if str(location)
            }),
            "family_evidence": primary.get("deduplication") or primary.get("category_evidence", []),
        })
    return sorted(families, key=lambda family: str(family["name"]).casefold())


def merge_plugins(raw_plugins: List[Dict[str, Any]], items: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_id = {item["id"]: item for item in items}
    buckets: Dict[str, Dict[str, Any]] = {}
    repository_groups: Dict[str, set[str]] = {}
    curation = config.get("curation", {})
    for plugin in raw_plugins:
        base_key = normalize_for_match(f"{plugin.get('provider') or 'unknown'}:{plugin['name']}")
        repository_key = normalize_for_match(str(plugin.get("_repository_key") or ""))
        key = f"{base_key}:{repository_key or '<missing>'}"
        repository_groups.setdefault(base_key, set()).add(repository_key or "<missing>")
        bucket = buckets.setdefault(key, {
            "id": f"plugin:{base_key}",
            "name": plugin["name"],
            "provider": plugin.get("provider") or "unknown",
            "provider_source": plugin.get("provider_source") or "unknown",
            "provider_evidence": plugin.get("provider_evidence") or {"type": "unknown"},
            "_repository_key": repository_key,
            "providers": [],
            "versions": [],
            "locations": [],
            "paths": [],
            "skill_ids": [],
        })
        for field, target in (("provider", "providers"), ("version", "versions"), ("location", "locations"), ("path", "paths")):
            value = plugin.get(field)
            if value and value not in bucket[target]:
                bucket[target].append(value)
        for skill_id in plugin.get("skills", []):
            if skill_id not in bucket["skill_ids"]:
                bucket["skill_ids"].append(skill_id)

    result: List[Dict[str, Any]] = []
    for plugin in buckets.values():
        base_key = normalize_for_match(f"{plugin.get('provider') or 'unknown'}:{plugin['name']}")
        repository_key = str(plugin.get("_repository_key") or "")
        if len(repository_groups.get(base_key, set())) > 1:
            suffix_source = repository_key or "missing-repository"
            plugin_id = f"plugin:{base_key}:{hashlib.sha1(suffix_source.encode('utf-8')).hexdigest()[:10]}"
        else:
            plugin_id = f"plugin:{base_key}"
        skills = [by_id[skill_id] for skill_id in plugin["skill_ids"] if skill_id in by_id]
        if not skills:
            continue
        for skill in skills:
            skill["plugin_id"] = plugin_id
        counts: Dict[str, int] = {}
        confidence_by_category: Dict[str, float] = {}
        for skill in skills:
            counts[skill["category"]] = counts.get(skill["category"], 0) + 1
            confidence_by_category[skill["category"]] = confidence_by_category.get(skill["category"], 0.0) + float(skill.get("confidence", 0.0))
        tie_break = [str(value) for value in (config.get("category_tie_break") or [])]
        category = sorted(
            counts,
            key=lambda value: (-counts[value], -confidence_by_category[value], tie_break.index(value) if value in tie_break else len(tie_break), value),
        )[0]
        candidate_rows = [
            {
                "category": value,
                "count": counts[value],
                "confidence_sum": round(confidence_by_category[value], 3),
                "evidence": [
                    json.loads(encoded)
                    for encoded in sorted({
                        json.dumps(evidence, ensure_ascii=False, sort_keys=True)
                        for skill in skills if skill["category"] == value
                        for evidence in skill.get("category_evidence", [])
                    })
                ],
            }
            for value in sorted(
                counts,
                key=lambda value: (
                    -counts[value],
                    -confidence_by_category[value],
                    tie_break.index(value) if value in tie_break else len(tie_break),
                    value,
                ),
            )
        ]
        best_count = counts[category]
        second_count = sorted(counts.values(), reverse=True)[1] if len(counts) > 1 else 0
        plugin_margin = best_count - second_count
        plugin_low_confidence = len(counts) > 1 and plugin_margin <= 1
        explicit = curation_value(curation.get("description_overrides"), str(plugin["name"]), str(plugin["name"]))
        primary = sorted(skills, key=lambda skill: (-float(skill["confidence"]), str(skill["name"]).casefold()))[0]
        description = explicit or primary["description"]
        image_member = best_image_member(skills, primary)
        github = aggregate_github(primary, image_member, skills)
        image = image_member["image"]
        plugin.update({
            "id": plugin_id,
            "category": category,
            "description": description,
            "description_source": "curation" if explicit else primary.get("description_source", "source"),
            "image": image,
            "image_source_member_id": image_member["id"],
            "github": github,
            "invocation": f"在你的 Agent 中直接说明任务；插件 {plugin['name']} 会路由到它携带的技能。",
            "category_candidates": candidate_rows,
            "category_evidence": [{"type": "plugin-member-category", "value": value, "count": counts[value]} for value in sorted(counts)],
            "category_winner_margin": plugin_margin,
            "category_tie_reason": "small-margin" if plugin_low_confidence else "member-majority",
            "confidence": round(sum(float(skill.get("confidence", 0.0)) for skill in skills) / len(skills), 3),
            "low_confidence": plugin_low_confidence or any(bool(skill.get("low_confidence")) for skill in skills),
        })
        plugin["providers"].sort(key=str.casefold)
        plugin["versions"].sort(key=str.casefold)
        plugin["locations"].sort(key=str.casefold)
        if plugin.get("paths"):
            plugin["paths"].sort(key=str.casefold)
        else:
            plugin.pop("paths", None)
        plugin.pop("_repository_key", None)
        result.append(plugin)
    return sorted(result, key=lambda plugin: (str(plugin["name"]).casefold(), str(plugin.get("provider") or "").casefold()))


def coverage(items: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    rows = []
    for category_id, metadata in categories.items():
        members = [item for item in items if item["category"] == category_id]
        confidence = sum(float(item["confidence"]) for item in members) / len(members) if members else 0.0
        rows.append({
            "id": category_id,
            "label": str(metadata.get("label") or category_id) if isinstance(metadata, dict) else category_id,
            "count": len(members),
            "covered": bool(members),
            "image_count": sum(1 for item in members if not item["image"].get("missing_evidence", True)),
            "average_confidence": round(confidence, 3),
        })
    covered_count = sum(1 for row in rows if row["covered"])
    category_count = len(rows)
    return {
        "schema_version": "1.0",
        "categories": rows,
        "covered_count": covered_count,
        "category_count": category_count,
        "coverage_ratio": round(covered_count / category_count, 3) if category_count else 1.0,
        "uncovered": [row["id"] for row in rows if not row["covered"]],
    }


def image_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    statuses: Dict[str, int] = {}
    missing_evidence_count = 0
    for item in items:
        image = item.get("image", {}) if isinstance(item.get("image"), dict) else {}
        status = str(image.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        if bool(image.get("missing_evidence", True)):
            missing_evidence_count += 1
    return {
        "status_counts": dict(sorted(statuses.items())),
        "verified_count": len(items) - missing_evidence_count,
        "missing_evidence_count": missing_evidence_count,
    }


def description_enrichment(items: List[Dict[str, Any]], locale: str) -> Dict[str, Any]:
    pending = []
    for item in items:
        review = item.get("description_review") if isinstance(item.get("description_review"), dict) else {}
        if not review.get("needed"):
            continue
        github = item.get("github") if isinstance(item.get("github"), dict) else {}
        pending.append(
            {
                "id": item.get("id"),
                "curation_key": item.get("id"),
                "name": item.get("name"),
                "source": item.get("source"),
                "relative_path": item.get("relative_path"),
                "current_description": item.get("description"),
                "reasons": review.get("reasons", []),
                "github_url": github.get("url", ""),
            }
        )
    return {
        "schema_version": "1.1",
        "locale": locale,
        "pending_count": len(pending),
        "execution_owner": "invoking-agent",
        "builder_generates_copy": False,
        "completion_rule": (
            "The invoking Agent must write evidence-backed Chinese descriptions to catalog-curation.json, "
            "rerun with --refresh --require-complete-descriptions, and must not report success while exit code 3 remains."
        ),
        "batch_protocol": {
            "script": "scripts/description_queue.py",
            "default_batch_size": 12,
            "prepare": "description_queue.py next",
            "apply": "description_queue.py apply",
            "resume_state": "catalog-curation.json",
        },
        "items": pending,
    }
