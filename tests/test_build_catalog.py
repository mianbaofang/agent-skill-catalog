import http.client
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "skills" / "agent-skill-catalog"
SCRIPT = ROOT / "scripts" / "build_catalog.py"
LEGACY_IMPORT_SCRIPT = ROOT / "scripts" / "import_legacy_catalog.py"
SERVER_SCRIPT = ROOT / "scripts" / "serve_catalog.py"
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0dIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def run_builder(root: Path, output: Path, refresh: bool = False, curation: Path | None = None) -> dict:
    command = [sys.executable, str(SCRIPT), "--root", str(root), "--output-dir", str(output)]
    if curation:
        command.extend(["--curation", str(curation)])
    if refresh:
        command.append("--refresh")
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert "Generated" in result.stdout
    return json.loads((output / "catalog.json").read_text(encoding="utf-8"))


def load_builder():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_catalog", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scan_classify_image_and_refresh() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        demo = root / "demo-video"
        demo.mkdir(parents=True)
        (demo / "SKILL.md").write_text(
            "---\nname: demo-video\ndescription: Make a short video with captions.\n---\n# Demo\n",
            encoding="utf-8",
        )
        (demo / "preview.png").write_bytes(TINY_PNG)
        other = root / "plain"
        other.mkdir()
        (other / "SKILL.md").write_text("---\nname: plain\n---\n# Plain\n", encoding="utf-8")
        git_only = root / "git-only"
        (git_only / ".git").mkdir(parents=True)
        (git_only / "SKILL.md").write_text("---\nname: git-only\ndescription: Local repository skill.\n---\n", encoding="utf-8")
        (git_only / ".git" / "config").write_text(
            "[remote \"origin\"]\nurl = git@github.com:example/git-only.git\n",
            encoding="utf-8",
        )
        output = fixture / "catalog"

        first = run_builder(root, output)
        assert first["summary"]["skill_count"] == 3
        demo_item = next(item for item in first["items"] if item["name"] == "demo-video")
        assert demo_item["category"] == "video"
        assert demo_item["image"]["status"] == "verified-local"
        assert demo_item["category_evidence"]
        plain_item = next(item for item in first["items"] if item["name"] == "plain")
        assert plain_item["image"]["status"] == "generated-fallback"
        assert plain_item["image"]["value"].startswith("data:image/svg+xml")
        assert "\"path\"" not in json.dumps(plain_item, ensure_ascii=False)
        git_item = next(item for item in first["items"] if item["name"] == "git-only")
        assert git_item["github"]["url"] == "https://github.com/example/git-only"
        assert git_item["github"]["source"] == "git-config"
        assert (output / "index.html").is_file()
        html = (output / "index.html").read_text(encoding="utf-8")
        assert ".join('\\n')" in html

        second = run_builder(root, output, refresh=True)
        assert second["mode"] == "refresh"
        assert second["previous_generated_at"] == first["generated_at"]


def test_curation_family_plugin_merge_and_output_guards() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        hyperframes = root / "hyperframes"
        (hyperframes / "components").mkdir(parents=True)
        (hyperframes / "SKILL.md").write_text(
            "---\nname: hyperframes\ndescription: Build motion video pages.\n---\n",
            encoding="utf-8",
        )
        (hyperframes / "components" / "SKILL.md").write_text(
            "---\nname: tailwind\ndescription: Component used with HyperFrames.\n---\n",
            encoding="utf-8",
        )
        animation = root / "hyperframes-animation"
        animation.mkdir()
        (animation / "SKILL.md").write_text(
            "---\nname: hyperframes-animation\ndescription: Animate a composition.\n---\n",
            encoding="utf-8",
        )
        git_config = hyperframes / ".git" / "config"
        git_config.parent.mkdir()
        git_config.write_text("[remote \"origin\"]\nurl = git@github.com:example/hyperframes.git\n", encoding="utf-8")
        plugin_root = fixture / "plugins"
        for version in ("1.0.0", "2.0.0"):
            location = plugin_root / "example" / "catalog-plugin" / version / "skills" / "helper"
            location.mkdir(parents=True)
            (location / "SKILL.md").write_text(
                f"---\nname: helper-{version}\ndescription: Search the web.\n---\n",
                encoding="utf-8",
            )
        curation = fixture / "curation.json"
        archived_preview = fixture / "hyperframes-preview.png"
        archived_preview.write_bytes(TINY_PNG)
        curation.write_text(
            json.dumps(
                {
                    "description_overrides": {
                        "hyperframes": "将组件、时间轴和渲染能力整理为视频与动效工作流。"
                    },
                    "github_overrides": {
                        "hyperframes": "https://github.com/example/hyperframes"
                    },
                    "image_overrides": {
                        "hyperframes": str(archived_preview)
                    },
                    "family_overrides": {
                        "tailwind": {"id": "ecosystem:hyperframes", "name": "HyperFrames", "category": "video"}
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = fixture / "catalog"

        command = [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--root",
            str(plugin_root),
            "--config",
            str(ROOT / "references" / "catalog-config.json"),
            "--curation",
            str(curation),
            "--output-dir",
            str(output),
        ]
        # The plugin root requires its own root spec. Use the default config only for categories.
        command = [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(ROOT / "references" / "catalog-config.json"),
            "--root",
            str(root),
            "--root",
            str(plugin_root),
            "--curation",
            str(curation),
            "--output-dir",
            str(output),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        assert "Generated" in result.stdout
        catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
        family = next(entry for entry in catalog["families"] if entry["id"] == "ecosystem:hyperframes")
        assert family["category"] == "video"
        assert len(family["skill_ids"]) == 3
        assert family["description"].startswith("将组件")
        assert family["github"]["url"] == "https://github.com/example/hyperframes"
        assert family["image"]["status"] == "curated-local"

        # CLI roots are standalone Skill roots. Verify plugin merging through scan() with a plugin root spec.
        module = load_builder()
        config = module.load_config(ROOT / "references" / "catalog-config.json")
        legacy = fixture / "legacy-plugin-descriptions.json"
        legacy.write_text(json.dumps({"catalog-plugin": "旧目录的中文插件说明。"}, ensure_ascii=False), encoding="utf-8")
        module.load_curation([str(curation), str(legacy)], config)
        items, raw_plugins, _ = module.scan(
            config,
            [
                {"path": str(root), "label": "Skills", "kind": "skill"},
                {"path": str(plugin_root), "label": "Plugin cache", "kind": "plugin"},
            ],
            False,
        )
        plugins = module.merge_plugins(raw_plugins, items, config)
        assert len(plugins) == 1
        assert plugins[0]["name"] == "catalog-plugin"
        assert len(plugins[0]["skill_ids"]) == 2
        assert plugins[0]["description"] == "旧目录的中文插件说明。"

        failed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), "--output-dir", str(output)],
            capture_output=True,
            text=True,
        )
        assert failed.returncode == 2
        assert "--refresh" in failed.stderr
        inside_root = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), "--output-dir", str(root / "catalog")],
            capture_output=True,
            text=True,
        )
        assert inside_root.returncode == 2
        assert "outside scanned roots" in inside_root.stderr


def test_rooted_sibling_family_inference_is_conservative() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        descriptions = {
            "research": "Research entry point.",
            "research-add-fields": "Add research fields.",
            "research-report": "Write a research report.",
            "conflict": "Parent package.",
            "conflict-one": "First package child.",
            "conflict-two": "Second package child.",
            "agent-browser": "Automate a browser.",
            "agent-reach": "Reach public sources.",
        }
        github = {
            "conflict": "https://github.com/example/conflict",
            "conflict-one": "https://github.com/example/conflict",
            "conflict-two": "https://github.com/other/conflict-two",
        }
        for name, description in descriptions.items():
            skill = root / name
            skill.mkdir(parents=True)
            source = f"metadata: {github[name]}\n" if name in github else ""
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {description}\n{source}---\n",
                encoding="utf-8",
            )

        catalog = run_builder(root, fixture / "catalog")
        research = next(family for family in catalog["families"] if family["name"] == "research")
        assert len(research["skill_ids"]) == 3
        research_items = [item for item in catalog["items"] if item["name"].startswith("research")]
        assert {item["family_id"] for item in research_items} == {research["id"]}
        assert all(item["family_size"] == 3 for item in research_items)

        conflict_items = [item for item in catalog["items"] if item["name"].startswith("conflict")]
        assert all(item["family_size"] == 1 for item in conflict_items)
        assert all(item["family_id"] != research["id"] for item in conflict_items)

        agent_items = [item for item in catalog["items"] if item["name"].startswith("agent-")]
        assert len(agent_items) == 2
        assert all(item["family_size"] == 1 for item in agent_items)


def test_container_directories_do_not_become_inferred_families() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        repository = fixture / "repository"
        for container in ("skills", "plugins", "packages", "extensions"):
            for name in (f"{container}-alpha", f"{container}-beta"):
                skill = repository / container / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: Independent {name} skill.\n---\n",
                    encoding="utf-8",
                )

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(
            config,
            [{"path": str(repository), "label": "Repository", "kind": "skill"}],
            False,
            fixture / "cache",
        )
        families = module.assign_families(items, config)

        assert all(family["name"] not in {"skills", "plugins", "packages", "extensions"} for family in families)
        assert len(families) == len(items) == 8
        assert all(item["family_size"] == 1 for item in items)


def test_repository_root_skill_hides_same_named_packaged_mirror() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        library = fixture / "skills"
        repository = library / "catalog-demo"
        package = repository / "skills" / "catalog-demo"
        package.mkdir(parents=True)
        source = "---\nname: catalog-demo\ndescription: Build a local Skill catalog.\n---\n"
        (repository / "SKILL.md").write_text(source, encoding="utf-8")
        (package / "SKILL.md").write_text(source, encoding="utf-8")

        catalog = run_builder(library, fixture / "output")
        matches = [item for item in catalog["items"] if item["name"] == "catalog-demo"]
        assert len(matches) == 1
        assert matches[0]["relative_path"] == "catalog-demo/SKILL.md"


def test_same_skill_and_repository_is_deduplicated_across_roots_before_images() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        first_root = fixture / "first"
        second_root = fixture / "second"
        for root, description, repository in (
            (first_root, "第一份研究入口。", "https://github.com/Example/Research.git"),
            (second_root, "第二份研究入口。", "https://github.com/example/research"),
        ):
            skill = root / "research"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: research\ndescription: {description}\nmetadata: {repository}\n---\n",
                encoding="utf-8",
            )

        preview_calls: list[str] = []

        def preview(repository: str, *_: object) -> dict:
            preview_calls.append(repository)
            return {
                "status": "github-social-preview",
                "source": "test",
                "value": "data:image/png;base64,dGVzdA==",
                "repository": repository,
                "missing_evidence": False,
            }

        original_preview = module.github_preview_image
        module.github_preview_image = preview
        try:
            config = module.load_config(ROOT / "references" / "catalog-config.json")
            items, raw_plugins, _ = module.scan(
                config,
                [
                    {"path": str(first_root), "label": "First", "kind": "skill"},
                    {"path": str(second_root), "label": "Second", "kind": "skill"},
                ],
                False,
                fixture / "cache",
            )
        finally:
            module.github_preview_image = original_preview

        assert len(items) == 1
        item = items[0]
        assert item["name"] == "research"
        assert {location["source"] for location in item["location_evidence"]} == {"First", "Second"}
        assert {location["relative_path"] for location in item["location_evidence"]} == {"research/SKILL.md"}
        assert item["github_evidence"]
        assert len(preview_calls) == 1
        assert not raw_plugins


def test_same_skill_name_with_conflicting_repositories_is_retained() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        roots = []
        for index, repository in enumerate(
            ("https://github.com/example/research", "https://github.com/other/research")
        ):
            root = fixture / f"root-{index}"
            skill = root / "research"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: research\ndescription: 研究入口。\nmetadata: {repository}\n---\n",
                encoding="utf-8",
            )
            roots.append({"path": str(root), "label": f"Root {index}", "kind": "skill"})

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(config, roots, False, fixture / "cache")
        assert len(items) == 2
        assert {item["github"]["url"] for item in items} == {
            "https://github.com/example/research",
            "https://github.com/other/research",
        }


def test_plugin_members_stay_out_of_independent_families_and_keep_membership_evidence() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        skill_root = fixture / "skills"
        standalone = skill_root / "helper"
        standalone.mkdir(parents=True)
        (standalone / "SKILL.md").write_text(
            "---\nname: helper\ndescription: 独立技能。\nmetadata: https://github.com/example/tool\n---\n",
            encoding="utf-8",
        )

        plugin_root = fixture / "plugins"
        plugin_skill = plugin_root / "provider" / "tool" / "1.0.0" / "skills" / "helper"
        plugin_skill.mkdir(parents=True)
        (plugin_skill / "SKILL.md").write_text(
            "---\nname: helper\ndescription: 插件成员技能。\nmetadata: https://github.com/example/tool\n---\n",
            encoding="utf-8",
        )

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, raw_plugins, _ = module.scan(
            config,
            [
                {"path": str(skill_root), "label": "Skills", "kind": "skill"},
                {"path": str(plugin_root), "label": "Plugins", "kind": "plugin"},
            ],
            False,
            fixture / "cache",
        )
        families = module.assign_families(items, config)
        plugins = module.merge_plugins(raw_plugins, items, config)

        assert {item["kind"] for item in items} == {"skill", "plugin"}
        assert len(families) == 1
        assert all(items_id not in families[0]["skill_ids"] for items_id in [item["id"] for item in items if item["kind"] == "plugin"])
        assert len(plugins) == 1
        plugin = plugins[0]
        assert len(plugin["skill_ids"]) == 1
        plugin_member = next(item for item in items if item["kind"] == "plugin")
        assert plugin["skill_ids"] == [plugin_member["id"]]
        assert plugin["locations"] == ["provider/tool/1.0.0"]
        assert plugin["category_evidence"]
        assert plugin["image_source_member_id"] == plugin_member["id"]


def test_same_repo_skill_name_stays_separate_across_plugins() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        plugin_root = fixture / "plugins"
        repository = "https://github.com/example/shared-skills"
        for plugin_name in ("alpha", "beta"):
            skill = plugin_root / "provider" / plugin_name / "1.0.0" / "skills" / "helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: helper\ndescription: {plugin_name} helper.\nmetadata: {repository}\n---\n",
                encoding="utf-8",
            )

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, raw_plugins, _ = module.scan(
            config,
            [{"path": str(plugin_root), "label": "Plugins", "kind": "plugin"}],
            False,
            fixture / "cache",
        )
        plugins = module.merge_plugins(raw_plugins, items, config)

        assert len(items) == 2
        assert {item["plugin_id"] for item in items} == {
            "plugin:provider:alpha",
            "plugin:provider:beta",
        }
        assert len(plugins) == 2
        assert all(len(plugin["skill_ids"]) == 1 for plugin in plugins)
        assert len({plugin["skill_ids"][0] for plugin in plugins}) == 2


def test_same_provider_plugin_name_with_conflicting_repositories_stays_separate() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        roots = []
        repositories = (
            "https://github.com/example/provider-plugin",
            "https://github.com/other/provider-plugin",
        )
        for index, repository in enumerate(repositories):
            plugin_root = fixture / f"plugins-{index}"
            skill = plugin_root / "provider" / "same-plugin" / "1.0.0" / "skills" / "helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: helper\ndescription: Repository {index} helper.\nmetadata: {repository}\n---\n",
                encoding="utf-8",
            )
            roots.append({"path": str(plugin_root), "label": f"Plugins {index}", "kind": "plugin"})

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, raw_plugins, _ = module.scan(config, roots, False, fixture / "cache")
        plugins = module.merge_plugins(raw_plugins, items, config)

        assert len(items) == 2
        assert len(raw_plugins) == 2
        assert len(plugins) == 2
        assert len({plugin["id"] for plugin in plugins}) == 2
        assert len({plugin["skill_ids"][0] for plugin in plugins}) == 2
        assert len({item["plugin_id"] for item in items}) == 2


def test_same_plugin_member_is_deduplicated_across_scan_roots() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        roots = []
        repository = "https://github.com/example/shared-skills"
        for index in range(2):
            plugin_root = fixture / f"plugins-{index}"
            skill = plugin_root / "provider" / "alpha" / "1.0.0" / "skills" / "helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: helper\ndescription: helper workflow.\nmetadata: {repository}\n---\n",
                encoding="utf-8",
            )
            roots.append({
                "path": str(plugin_root),
                "label": f"Plugins {index}",
                "kind": "plugin",
            })

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, raw_plugins, _ = module.scan(config, roots, False, fixture / "cache")
        plugins = module.merge_plugins(raw_plugins, items, config)

        assert len(items) == 1
        assert items[0]["plugin_id"] == "plugin:provider:alpha"
        assert items[0]["deduplication"]["copy_count"] == 2
        assert len(items[0]["locations"]) == 2
        assert len(plugins) == 1
        assert plugins[0]["skill_ids"] == [items[0]["id"]]


def test_repo_backed_root_families_aggregate_across_scan_roots() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        roots = []
        families = {
            "gsap": "https://github.com/greensock/gsap-skills.git",
            "hyperframes": "https://github.com/heygen-com/hyperframes",
            "research": "https://github.com/example/research-skills",
            "story": "https://github.com/worldwonderer/oh-story-claudecode",
        }
        for index, (parent, repository) in enumerate(families.items()):
            root = fixture / f"root-{index}"
            root.mkdir()
            names = [parent, f"{parent}-core", f"{parent}-report"]
            for name in names[:2]:
                skill = root / name
                skill.mkdir()
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: {name} workflow.\nmetadata: {repository}\n---\n",
                    encoding="utf-8",
                )
            second_root = fixture / f"root-{index}-second"
            child = second_root / names[2]
            child.mkdir(parents=True)
            (child / "SKILL.md").write_text(
                f"---\nname: {names[2]}\ndescription: {names[2]} workflow.\nmetadata: {repository}\n---\n",
                encoding="utf-8",
            )
            roots.extend(
                [
                    {"path": str(root), "label": f"Root {index}", "kind": "skill"},
                    {"path": str(second_root), "label": f"Root {index} second", "kind": "skill"},
                ]
            )

        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(config, roots, False, fixture / "cache")
        result = module.assign_families(items, config)
        by_name = {family["name"]: family for family in result}
        for parent in families:
            assert parent in by_name
            family = by_name[parent]
            assert len(family["skill_ids"]) == 3
            assert len(family["locations"]) == 3


def test_github_preview_uses_readme_image() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        cache = Path(temp)
        image_url = "https://raw.githubusercontent.com/example/catalog/main/preview.png"
        result = module.github_preview_image(
            "https://github.com/example/catalog",
            {},
            cache,
            fetch_readme_urls=lambda *_: [image_url],
            fetch_image=lambda url, _: (TINY_PNG, ".png") if url == image_url else (b"", ""),
        )
        assert result["status"] == "github-repository"
        assert result["source"] == "github-readme"
        assert result["remote_source"] == image_url
        assert result["value"].startswith("data:image/png;base64,")


def test_github_preview_falls_back_to_social_image() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        result = module.github_preview_image(
            "https://github.com/example/catalog",
            {},
            Path(temp),
            fetch_readme_urls=lambda *_: [],
            fetch_image=lambda url, _: (TINY_PNG, ".png") if "opengraph.githubassets.com" in url else (b"", ""),
        )
        assert result["status"] == "github-social-preview"
        assert result["source"] == "github-opengraph"
        assert "opengraph.githubassets.com" in result["remote_source"]


def test_github_preview_reuses_cached_source_type() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        cache = Path(temp)
        repository = "https://github.com/example/catalog"
        first = module.github_preview_image(
            repository,
            {},
            cache,
            fetch_readme_urls=lambda *_: [],
            fetch_image=lambda *_: (TINY_PNG, ".png"),
        )
        assert first["status"] == "github-social-preview"

        def unexpected_fetch(*_):
            raise AssertionError("A fresh cache entry must be reused without network access")

        second = module.github_preview_image(
            repository,
            {},
            cache,
            fetch_readme_urls=unexpected_fetch,
            fetch_image=unexpected_fetch,
        )
        assert second["status"] == "github-social-preview"
        assert second["source"] == "github-cache"


def test_github_preview_ignores_untyped_legacy_cache() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        cache = Path(temp)
        repository = "https://github.com/example/catalog"
        legacy = cache / f"{module.github_cache_key(repository)}.png"
        legacy.write_bytes(TINY_PNG)
        image_url = "https://raw.githubusercontent.com/example/catalog/main/current.png"
        result = module.github_preview_image(
            repository,
            {},
            cache,
            fetch_readme_urls=lambda *_: [image_url],
            fetch_image=lambda url, _: (TINY_PNG, ".png") if url == image_url else (b"", ""),
        )
        assert result["status"] == "github-repository"
        assert result["source"] == "github-readme"
        assert result["remote_source"] == image_url


def test_github_redirect_policy_rejects_non_github_hosts() -> None:
    module = load_builder()
    handler = module.AllowedRedirectHandler({"github.com"})
    request = urllib.request.Request("https://github.com/example/catalog")
    try:
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://example.com/preview.png",
        )
    except urllib.error.HTTPError:
        pass
    else:
        raise AssertionError("A redirect outside the GitHub allowlist must be rejected")


def test_malformed_config_fails() -> None:
    with tempfile.TemporaryDirectory() as temp:
        config = Path(temp) / "broken.json"
        config.write_text("{", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(config), "--output-dir", str(Path(temp) / "catalog")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Cannot read JSON" in result.stderr


def test_folded_frontmatter_description() -> None:
    module = load_builder()
    fields = module.parse_frontmatter("---\nname: folded\ndescription: >-\n  First sentence.\n  Second sentence.\n---\n")
    assert fields["description"] == "First sentence. Second sentence."


def test_gh_install_metadata_and_skill_body_urls_drive_github_previews() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        installed = root / "installed"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text(
            "---\n"
            "name: installed\n"
            "description: 这是通过 GitHub CLI 安装的目录技能，会读取安装器注入的仓库来源并获取预览图。\n"
            "metadata:\n"
            "    github-path: skills/installed\n"
            "    github-repo: https://github.com/example/installed\n"
            "    github-ref: refs/tags/v1.0.0\n"
            "---\n",
            encoding="utf-8",
        )
        body_link = root / "body-link"
        body_link.mkdir()
        (body_link / "SKILL.md").write_text(
            "---\nname: body-link\ndescription: 这个技能在正文中明确给出项目仓库，并用该仓库的公开图片作为目录预览。\n---\n"
            "# Body Link\n\n项目仓库：https://github.com/example/body-link\n",
            encoding="utf-8",
        )
        module.github_preview_image = lambda repository, *_: {
            "status": "github-social-preview",
            "source": "test",
            "value": "data:image/png;base64,dGVzdA==",
            "repository": repository,
            "missing_evidence": False,
        }
        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(
            config,
            [{"path": str(root), "label": "Root 1", "kind": "skill"}],
            False,
            fixture / "cache",
        )
        by_name = {item["name"]: item for item in items}
        assert by_name["installed"]["github"]["url"] == "https://github.com/example/installed"
        assert by_name["installed"]["github"]["source"] == "frontmatter"
        assert by_name["installed"]["image"]["status"] == "github-social-preview"
        assert by_name["body-link"]["github"]["url"] == "https://github.com/example/body-link"
        assert by_name["body-link"]["github"]["source"] == "skill-body"
        assert by_name["body-link"]["image"]["missing_evidence"] is False

        ambiguous = module.github_from_skill_text(
            "See https://github.com/example/dependency-one and https://github.com/example/dependency-two for related tools."
        )
        assert ambiguous == ""


def test_github_sources_are_canonical_repository_roots() -> None:
    builder = load_builder()
    preview = sys.modules["github_preview"]
    assert preview.github_repository("https://github.com/example/repo") == ("example", "repo")
    assert preview.github_repository("https://github.com/example/repo.git") == ("example", "repo")
    for path in ("archive/refs/heads/main.zip", "tree/main/docs", "blob/main/SKILL.md", "issues/1", "pull/2"):
        assert preview.github_repository(f"https://github.com/example/repo/{path}") == ("", "")
    assert builder.github_from_values(["https://github.com/example/repo/tree/main/docs`\n"]) == ""
    assert builder.github_from_values(["https://github.com/example/repo/archive/refs/heads/main.zip"]) == ""
    assert builder.github_from_skill_text(
        "Docs: https://github.com/example/repo/tree/main/docs`\n"
        "Source: https://github.com/example/repo\n"
    ) == "https://github.com/example/repo"


def test_local_git_remote_wins_over_referenced_readme_repository() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        skill = root / "cangjie-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: cangjie-skill\ndescription: 将长内容提炼为可复用的技能流程说明。\n---\n",
            encoding="utf-8",
        )
        (skill / "README.md").write_text(
            "来源仓库：https://github.com/example/referenced-source\n",
            encoding="utf-8",
        )
        (skill / ".git").mkdir()
        (skill / ".git" / "config").write_text(
            '[remote "origin"]\nurl = https://github.com/example/cangjie-skill.git\n',
            encoding="utf-8",
        )
        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(
            config,
            [{"path": str(root), "label": "Root 1", "kind": "skill"}],
            False,
            fixture / "cache",
        )
        assert items[0]["github"] == {
            "url": "https://github.com/example/cangjie-skill",
            "source": "git-config",
            "verification": "observed-local",
        }


def test_gh_install_lock_drives_github_preview_when_frontmatter_has_no_metadata() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / ".agents" / "skills"
        installed = root / "installed-from-lock"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text(
            "---\n"
            "name: installed-from-lock\n"
            "description: 这是一个通过 GitHub CLI 安装但源文件没有注入仓库元数据的技能。\n"
            "---\n",
            encoding="utf-8",
        )
        (root.parent / ".skill-lock.json").write_text(
            json.dumps(
                {
                    "version": 3,
                    "skills": {
                        "installed-from-lock": {
                            "source": "example/installed-from-lock",
                            "sourceType": "github",
                            "sourceUrl": "https://github.com/example/installed-from-lock.git",
                            "skillPath": "skills/installed-from-lock/SKILL.md",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        module.github_preview_image = lambda repository, *_: {
            "status": "github-social-preview",
            "source": "test",
            "value": "data:image/png;base64,dGVzdA==",
            "repository": repository,
            "missing_evidence": False,
        }
        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(
            config,
            [{"path": str(root), "label": "Root 1", "kind": "skill"}],
            False,
            fixture / "cache",
        )
        item = items[0]
        assert item["github"]["url"] == "https://github.com/example/installed-from-lock"
        assert item["github"]["source"] == "install-lock"
        assert item["image"]["status"] == "github-social-preview"


def test_github_readme_partial_response_still_yields_image_candidates() -> None:
    load_builder()
    module = sys.modules["github_preview"]
    globals_ = module.github_readme_image_urls.__globals__
    original = globals_["open_allowed"]

    class PartialResponse:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def geturl(self):
            return "https://github.com/example/catalog"

        def read(self, _):
            raise http.client.IncompleteRead(
                b'<img src="https://raw.githubusercontent.com/example/catalog/main/preview.png">',
                100,
            )

    try:
        globals_["open_allowed"] = lambda *_: PartialResponse()
        urls = module.github_readme_image_urls("https://github.com/example/catalog", {})
    finally:
        globals_["open_allowed"] = original
    assert urls == ["https://raw.githubusercontent.com/example/catalog/main/preview.png"]


def test_family_and_plugin_aggregates_use_best_verified_member_image() -> None:
    module = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        for name, repository in (
            ("research", ""),
            ("research-deep", "https://github.com/example/research"),
            ("research-report", "https://github.com/example/research"),
        ):
            skill = root / name
            skill.mkdir(parents=True)
            metadata = f"metadata: {repository}\n" if repository else ""
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: 处理研究资料并输出可复查的结果说明。\n{metadata}---\n",
                encoding="utf-8",
            )
        module.github_preview_image = lambda repository, *_: {
            "status": "github-social-preview",
            "source": "test",
            "value": "data:image/png;base64,dGVzdA==",
            "repository": repository,
            "missing_evidence": False,
        }
        config = module.load_config(ROOT / "references" / "catalog-config.json")
        items, _, _ = module.scan(
            config,
            [{"path": str(root), "label": "Root 1", "kind": "skill"}],
            False,
            fixture / "family-cache",
        )
        family = next(family for family in module.assign_families(items, config) if family["name"] == "research")
        assert family["primary_id"] == next(item["id"] for item in items if item["name"] == "research")
        assert family["image"]["status"] == "github-social-preview"
        assert family["image_source_member_id"] != family["primary_id"]
        assert family["github"]["url"] == "https://github.com/example/research"

        plugin_root = fixture / "plugins"
        for name, repository in (("primary", ""), ("preview", "https://github.com/example/plugin")):
            skill = plugin_root / "provider" / "tool" / "1.0" / name
            skill.mkdir(parents=True)
            metadata = f"metadata: {repository}\n" if repository else ""
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: 提供插件能力并输出可复查的处理结果。\n{metadata}---\n",
                encoding="utf-8",
            )
        plugin_items, raw_plugins, _ = module.scan(
            config,
            [{"path": str(plugin_root), "label": "Plugins", "kind": "plugin"}],
            False,
            fixture / "plugin-cache",
        )
        by_name = {item["name"]: item for item in plugin_items}
        by_name["primary"]["confidence"] = 1.0
        by_name["preview"]["confidence"] = 0.1
        plugin = module.merge_plugins(raw_plugins, plugin_items, config)[0]
        assert plugin["image"]["status"] == "github-social-preview"
        assert plugin["image_source_member_id"] == by_name["preview"]["id"]
        assert plugin["github"]["url"] == "https://github.com/example/plugin"


def test_description_enrichment_queue_closes_after_curation() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        skill = root / "english"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: english\ndescription: Search public sources and produce a cited research brief.\n---\n",
            encoding="utf-8",
        )
        output = fixture / "output"
        first = run_builder(root, output)
        assert first["summary"]["pending_description_count"] == 1
        queue = json.loads((output / "description-enrichment.json").read_text(encoding="utf-8"))
        assert queue["items"][0]["reasons"] == ["not-zh-CN"]

        curation_path = output / "catalog-curation.json"
        curation = json.loads(curation_path.read_text(encoding="utf-8"))
        curation["description_overrides"]["english/SKILL.md"] = (
            "检索公开来源并整理为带引用的研究简报。适合需要核对事实、保留出处并形成可复查结论的任务。"
        )
        curation_path.write_text("\ufeff" + json.dumps(curation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        second = run_builder(root, output, refresh=True)
        assert second["summary"]["pending_description_count"] == 0
        assert second["items"][0]["description_source"] == "curation"


def test_require_complete_descriptions_blocks_premature_success() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        skill = root / "english"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: english\ndescription: Search public sources and produce a cited research brief.\n---\n",
            encoding="utf-8",
        )
        output = fixture / "output"
        first = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--output-dir",
                str(output),
                "--require-complete-descriptions",
            ],
            capture_output=True,
            text=True,
        )
        assert first.returncode == 3
        assert "pending description" in first.stderr.casefold()
        assert (output / "description-enrichment.json").is_file()

        curation_path = output / "catalog-curation.json"
        curation = json.loads(curation_path.read_text(encoding="utf-8"))
        curation["description_overrides"]["english/SKILL.md"] = (
            "检索公开来源并整理为带引用的研究简报，适合需要核对事实、保留出处并形成可复查结论的任务。"
        )
        curation_path.write_text(json.dumps(curation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        second = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--output-dir",
                str(output),
                "--refresh",
                "--require-complete-descriptions",
            ],
            capture_output=True,
            text=True,
        )
        assert second.returncode == 0


def test_import_legacy_catalog_curation() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        previews = fixture / "skill-previews"
        previews.mkdir()
        preview = previews / "demo.png"
        preview.write_bytes(TINY_PNG)
        legacy = fixture / "catalog-data.js"
        payload = {
            "items": [
                {
                    "name": "demo",
                    "description": "这是已经人工整理的中文说明。",
                    "githubUrl": "https://github.com/example/demo",
                    "preview": {"url": "skill-previews/demo.png"},
                }
            ],
            "plugins": [
                {
                    "name": "demo-plugin",
                    "description": "插件的中文说明。",
                    "skills": [
                        {
                            "name": "child",
                            "description": "子技能的中文说明。",
                            "githubUrl": "https://github.com/sponsors/example",
                        }
                    ],
                }
            ],
        }
        legacy.write_text("window.SKILL_ATLAS_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
        output = fixture / "curation.json"
        subprocess.run(
            [sys.executable, str(LEGACY_IMPORT_SCRIPT), "--legacy-catalog-data", str(legacy), "--output", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        curation = json.loads(output.read_text(encoding="utf-8"))
        assert curation["description_overrides"]["child"] == "子技能的中文说明。"
        assert curation["github_overrides"] == {"demo": "https://github.com/example/demo"}
        assert curation["image_overrides"]["demo"] == str(preview.resolve())


def test_explainable_classification_scoped_override_and_plugin_providers() -> None:
    module = load_builder()
    config = module.load_config(ROOT / "references" / "catalog-config.json")
    category, _, confidence, detail = module.classify("image-video", "", "SKILL.md", {}, config)
    assert category == "video"
    assert detail["tie_reason"] == "exact-tie"
    assert detail["low_confidence"] is True
    assert confidence < 0.5
    assert {candidate["category"] for candidate in detail["candidates"]} >= {"visual", "video"}

    config["category_overrides"] = [
        {"name": "shared", "category": "visual"},
        {"name": "shared", "root": "Team B", "category": "data"},
    ]
    category, evidence, _, detail = module.classify("shared", "video", "SKILL.md", {}, config, root_label="Team B")
    assert category == "data"
    assert detail["tie_reason"] == "explicit-override"
    assert evidence[0]["scope"] == {"root": "Team B", "name": "shared"}

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "plugins"
        for provider in ("openai", "community"):
            location = root / provider / "shared-plugin" / "1.0.0" / "skills" / "helper"
            location.mkdir(parents=True)
            (location / "SKILL.md").write_text(
                "---\nname: helper\ndescription: Search the web.\n---\n",
                encoding="utf-8",
            )
        items, raw_plugins, _ = module.scan(
            config,
            [{"path": str(root), "label": "Plugin cache", "kind": "plugin"}],
            False,
        )
        plugins = module.merge_plugins(raw_plugins, items, config)
        assert {plugin["id"] for plugin in plugins} == {"plugin:openai:shared-plugin", "plugin:community:shared-plugin"}


def test_config_root_refresh_and_privacy_contract() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        skill = root / "search"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: search\ndescription: Search the web.\n---\n",
            encoding="utf-8",
        )
        config = fixture / "catalog-config.json"
        config.write_text(
            json.dumps(
                {
                    "roots": [{"path": str(root), "label": "Skills", "kind": "skill"}],
                    "categories": {"internet_search": {"label": "互联网搜索", "keywords": ["search"]}, "other": {"label": "其他", "keywords": []}},
                    "category_tie_break": ["internet_search", "other"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = fixture / "output"
        subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(config), "--output-dir", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        catalog_text = (output / "catalog.json").read_text(encoding="utf-8")
        assert str(root.resolve()) not in catalog_text

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT), "--config", str(config), "--output-dir", str(output), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            health_url = f"http://127.0.0.1:{port}/api/health"
            for _ in range(30):
                try:
                    with urllib.request.urlopen(health_url, timeout=1) as response:
                        assert response.status == 200
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Catalog server did not start")
            request = urllib.request.Request(f"http://127.0.0.1:{port}/api/refresh", method="POST")
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["ok"] is True
            assert json.loads((output / "catalog.json").read_text(encoding="utf-8"))["mode"] == "refresh"

            upload = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/image",
                data=TINY_PNG,
                method="POST",
                headers={
                    "Content-Type": "image/png",
                    "X-Catalog-Skill-Name": "search",
                    "X-Catalog-Relative-Path": "search/SKILL.md",
                },
            )
            with urllib.request.urlopen(upload, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["ok"] is True
            curation = json.loads((output / "catalog-curation.json").read_text(encoding="utf-8"))
            uploaded_path = Path(curation["image_overrides"]["search/SKILL.md"])
            assert uploaded_path.is_file()
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            assert catalog["families"][0]["image"]["status"] == "curated-local"

            remove = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/image",
                method="DELETE",
                headers={"X-Catalog-Relative-Path": "search/SKILL.md"},
            )
            with urllib.request.urlopen(remove, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["ok"] is True
            curation = json.loads((output / "catalog-curation.json").read_text(encoding="utf-8"))
            assert "search/SKILL.md" not in curation["image_overrides"]
            assert not uploaded_path.exists()
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    test_scan_classify_image_and_refresh()
    test_curation_family_plugin_merge_and_output_guards()
    test_rooted_sibling_family_inference_is_conservative()
    test_repository_root_skill_hides_same_named_packaged_mirror()
    test_github_preview_uses_readme_image()
    test_github_preview_falls_back_to_social_image()
    test_github_preview_reuses_cached_source_type()
    test_github_preview_ignores_untyped_legacy_cache()
    test_github_redirect_policy_rejects_non_github_hosts()
    test_malformed_config_fails()
    test_folded_frontmatter_description()
    test_gh_install_metadata_and_skill_body_urls_drive_github_previews()
    test_gh_install_lock_drives_github_preview_when_frontmatter_has_no_metadata()
    test_github_readme_partial_response_still_yields_image_candidates()
    test_family_and_plugin_aggregates_use_best_verified_member_image()
    test_description_enrichment_queue_closes_after_curation()
    test_require_complete_descriptions_blocks_premature_success()
    test_import_legacy_catalog_curation()
    test_explainable_classification_scoped_override_and_plugin_providers()
    test_config_root_refresh_and_privacy_contract()
    print("ok")
