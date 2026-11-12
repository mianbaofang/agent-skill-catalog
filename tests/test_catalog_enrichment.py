import argparse
import base64
import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/agent-skill-catalog/scripts'


def load_script(name):
    spec = importlib.util.spec_from_file_location(f'enrichment_{name}', SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def skill(root, name, repo='', description='整理输入资料，按任务要求交付可复查的结构化结果。'):
    folder = root / name
    folder.mkdir(parents=True)
    metadata = f'repository: {repo}\n' if repo else ''
    (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {description}\n{metadata}---\n', encoding='utf-8')
    return folder


def test_local_readme_skips_remote_worker_and_broken_metadata(tmp_path, monkeypatch):
    builder = load_script('build_catalog')
    root = tmp_path / 'skills'
    folder = skill(root, 'local', 'https://github.com/example/local')
    Image.new('RGB', (160, 90), 'green').save(folder / 'actual.png')
    (folder / 'README.md').write_text('![actual](actual.png)', encoding='utf-8')
    config = builder.load_config(builder.DEFAULT_CONFIG)
    config['github_discovery']['enabled'] = False
    calls = []
    monkeypatch.setattr(builder, 'github_preview_image', lambda *args: calls.append(args) or {})
    items, _, _ = builder.scan(config, [{'path': str(root), 'label': 'Skills', 'kind': 'skill'}], False, tmp_path / 'cache')
    assert calls == []
    assert items[0]['image']['source'].startswith('readme:')
    for value in ('missing.png', 'https://example.com/metadata.png'):
        image = builder.choose_image(folder / 'SKILL.md', {'preview_image': value}, 'other', 'local', 'local/SKILL.md', '说明', config, 'https://github.com/example/local', tmp_path / 'cache')
        assert image['status'] == 'verified-local'
    assert calls == []
    assert base64.b64decode(items[0]['image']['value'].split(',', 1)[1]) == (folder / 'actual.png').read_bytes()


def test_missing_local_image_fetches_one_repository_for_different_names(tmp_path, monkeypatch):
    builder = load_script('build_catalog')
    root = tmp_path / 'skills'
    repository = 'https://github.com/example/collection'
    for name in ('alpha', 'beta', 'gamma'):
        skill(root, name, repository)
    skill(root, 'foreign', 'https://github.com/other/collection')
    config = builder.load_config(builder.DEFAULT_CONFIG)
    config['github_discovery']['enabled'] = False
    calls = []
    def preview(repo, *_):
        calls.append(repo)
        return {'status': 'github-repository', 'source': repo, 'repository': repo, 'value': 'data:image/png;base64,AA==', 'missing_evidence': False}
    monkeypatch.setattr(builder, 'github_preview_image', preview)
    items, _, _ = builder.scan(config, [{'path': str(root), 'label': 'Skills', 'kind': 'skill'}], False, tmp_path / 'cache')
    assert sorted(calls) == sorted([repository, 'https://github.com/other/collection'])
    families = builder.assign_families(items, config)
    family = next(f for f in families if len(f['skill_ids']) == 3)
    assert family['name'] == 'collection'
    assert family['family_evidence']['repository'] == repository
    assert {item['name'] for item in items if item['id'] in family['skill_ids']} == {'alpha', 'beta', 'gamma'}
    assert len(families) == 2
    assert all(item['invocation'] for item in items)


def test_readme_prefers_landscape_and_ignores_malformed_url(tmp_path):
    builder = load_script('build_catalog')
    Image.new('RGB', (90, 160), 'red').save(tmp_path / 'portrait.png')
    Image.new('RGB', (160, 90), 'blue').save(tmp_path / 'landscape.png')
    (tmp_path / 'README.md').write_text('<img src="http://["><img src="portrait.png"><img src="landscape.png">', encoding='utf-8')
    image = builder.local_readme_image(tmp_path / 'SKILL.md', 524288)
    assert image['source'].endswith(':landscape.png')


def research_fixture(tmp_path):
    output = tmp_path / 'output'
    output.mkdir()
    item = {'id': 'skill:example', 'name': 'example', 'description': '本地中文说明已经完整。', 'relative_path': 'example/SKILL.md', 'kind': 'skill'}
    (output / 'catalog.json').write_text(json.dumps({'items': [item]}), encoding='utf-8')
    (output / 'description-enrichment.json').write_text(json.dumps({'locale': 'zh-CN', 'items': []}), encoding='utf-8')
    (output / 'catalog-curation.json').write_text(json.dumps({'description_overrides': {}}), encoding='utf-8')
    return output, item


def test_public_research_includes_complete_descriptions_and_resumes(tmp_path):
    queue = load_script('description_queue')
    output, item = research_fixture(tmp_path)
    args = argparse.Namespace(output_dir=str(output), config=None, root=[str(tmp_path)], batch_size=12, no_github_readmes=True, web_research=True, output=None)
    assert queue.prepare_batch(args) == 0
    batch = json.loads((output / 'description-batch.json').read_text(encoding='utf-8'))
    assert batch['batch_count'] == 1
    assert batch['items'][0]['public_search']['enabled'] is True
    assert batch['response_contract']['shape']['web_research'] is True
    source = {'url': 'https://github.com/example/skill', 'title': 'Example Skill', 'retrieved_at': '2026-01-01', 'identity_evidence': '仓库与本地安装来源一致。'}
    responses = output / 'responses.json'
    responses.write_text(json.dumps({'web_research': True, 'items': [{'curation_key': item['id'], 'description': '读取指定的公开来源，整理资料并交付保留出处的中文研究简报，便于逐项复核。', 'sources': [source]}]}), encoding='utf-8')
    assert queue.apply_batch(argparse.Namespace(output_dir=str(output), input=str(responses))) == 0
    curation = json.loads((output / 'catalog-curation.json').read_text(encoding='utf-8'))
    assert curation['description_sources'][item['id']] == [source]
    assert queue.prepare_batch(args) == 0
    assert json.loads((output / 'description-batch.json').read_text(encoding='utf-8'))['batch_count'] == 0


@pytest.mark.parametrize('sources', [[], [{'url': 'javascript:alert(1)', 'title': 'wrong', 'retrieved_at': '2026-01-01', 'identity_evidence': 'wrong'}], [{'url': 'https://example.com/', 'title': 'page', 'retrieved_at': '2026-01-01'}]])
def test_public_research_rejects_missing_or_invalid_provenance(tmp_path, sources):
    queue = load_script('description_queue')
    output, item = research_fixture(tmp_path)
    responses = output / 'responses.json'
    responses.write_text(json.dumps({'web_research': True, 'items': [{'curation_key': item['id'], 'description': '读取公开资料并交付带出处的中文研究简报，适合需要逐项核对证据的资料整理任务。', 'sources': sources}]}), encoding='utf-8')
    before = (output / 'catalog-curation.json').read_bytes()
    with pytest.raises(ValueError):
        queue.apply_batch(argparse.Namespace(output_dir=str(output), input=str(responses)))
    assert (output / 'catalog-curation.json').read_bytes() == before


def test_installer_reference_does_not_replace_clone_source():
    builder = load_script('build_catalog')
    readme = (
        'git clone https://github.com/author/actual-skill.git target\n'
        'The [skills](https://github.com/vercel-labs/skills) CLI installs this repository.'
    )
    assert builder.github_from_skill_text(readme) == 'https://github.com/author/actual-skill'
    assert builder.github_from_skill_text('Source: https://github.com/author/declared\n' + readme) == 'https://github.com/author/declared'


def test_description_sources_survive_rebuild_and_family_aggregation(tmp_path):
    builder = load_script('build_catalog')
    root = tmp_path / 'skills'
    folder = skill(root, 'actual')
    config = builder.load_config(builder.DEFAULT_CONFIG)
    config['github_discovery']['enabled'] = False
    config['image']['github_repository_previews'] = False
    key = builder.stable_id(root, 'actual/SKILL.md')
    source = {'url': 'https://github.com/example/actual', 'title': 'Actual source', 'retrieved_at': '2026-01-01', 'identity_evidence': 'Exact repository match.'}
    curation = tmp_path / 'curation.json'
    curation.write_text(json.dumps({'description_overrides': {key: '读取公开资料并整理为带有出处、可逐项核对的结构化研究结果。'}, 'description_sources': {key: [source]}}), encoding='utf-8')
    builder.load_curation([str(curation)], config)
    items, _, _ = builder.scan(config, [{'path': str(root), 'label': 'Skills', 'kind': 'skill'}], False, tmp_path / 'cache')
    assert items[0]['description_sources'] == [source]
    assert builder.assign_families(items, config)[0]['description_sources'] == [source]
