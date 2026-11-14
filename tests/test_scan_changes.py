from test_build_catalog import load_builder, run_builder


def test_scan_change_comparison_and_scope_safety(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    def skill(name):
        folder = root / name
        folder.mkdir()
        (folder / "SKILL.md").write_text("---\nname: " + name + "\ndescription: Local example\n---\n# Example\n", encoding="utf-8")
    skill("first")
    out = tmp_path / "catalog"
    first = run_builder(root, out)
    assert not first["index_changes"]["comparable"]
    skill("second")
    second = run_builder(root, out, refresh=True)
    changes = second["index_changes"]
    assert changes["comparable"] and [i["name"] for i in changes["added"]] == ["second"]
    assert not changes["removed"]
    (root / "first" / "SKILL.md").unlink()
    third = run_builder(root, out, refresh=True)
    assert [i["name"] for i in third["index_changes"]["removed"]] == ["first"]
    assert "不再索引不等于源文件已删除" in (out / "index.html").read_text(encoding="utf-8")
    module = load_builder()
    assert not module.index_changes(third, [], {"different":"scope"})["comparable"]


def test_collection_root_readme_is_not_a_child_skills_repository(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    (root / "README.md").write_text("Install with https://github.com/vercel-labs/skills", encoding="utf-8")
    for name in ["independent-a", "independent-b"]:
        folder = root / name
        folder.mkdir()
        (folder / "SKILL.md").write_text("---\nname: " + name + "\ndescription: Independent local tool\n---\n", encoding="utf-8")
    catalog = run_builder(root, tmp_path / "out")
    assert len(catalog["families"]) == 2
    assert all(not item.get("github", {}).get("url") for item in catalog["items"])
    module = load_builder()
    own = root / "independent-a" / "README.md"
    own.write_text("Repository: https://github.com/example/real-source", encoding="utf-8")
    assert module.github_from_nearby_metadata(own.with_name("SKILL.md"), root) == "https://github.com/example/real-source"
