import base64
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/agent-skill-catalog/scripts/build_catalog.py'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')


@pytest.fixture
def builder():
    spec = importlib.util.spec_from_file_location('readme_preview_builder', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_html_readme_image_is_local_evidence(builder, tmp_path):
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'hero.png').write_bytes(PNG)
    (tmp_path / 'README.md').write_text('<img src="https://img.shields.io/badge/example"><img src="assets/hero.png">', encoding='utf-8')
    result = builder.local_readme_image(tmp_path / 'SKILL.md', 524288)
    assert result['status'] == 'verified-local'
    assert result['source'] == 'readme:README.md:assets/hero.png'
    assert base64.b64decode(result['value'].split(',', 1)[1]) == PNG


def test_markdown_image_with_encoded_name(builder, tmp_path):
    (tmp_path / 'real cover.png').write_bytes(PNG)
    (tmp_path / 'README.md').write_text('![Preview](real%20cover.png)', encoding='utf-8')
    result = builder.local_readme_image(tmp_path / 'SKILL.md', 524288)
    assert result['source'] == 'readme:README.md:real cover.png'


def test_readme_cannot_import_parent_or_absolute_paths(builder, tmp_path):
    skill = tmp_path / 'skill'
    skill.mkdir()
    (tmp_path / 'private.png').write_bytes(PNG)
    (skill / 'README.md').write_text('![x](../private.png) ![x](file:///private.png) <img src="/private.png">', encoding='utf-8')
    assert builder.local_readme_image(skill / 'SKILL.md', 524288) == {}


def test_large_or_invalid_image_does_not_hide_later_evidence(builder, tmp_path):
    (tmp_path / 'too-big.png').write_bytes(PNG + b'x' * 1000)
    (tmp_path / 'invalid.png').write_text('not an image', encoding='utf-8')
    (tmp_path / 'valid.png').write_bytes(PNG)
    (tmp_path / 'README.md').write_text('![x](too-big.png) ![x](invalid.png) ![x](valid.png)', encoding='utf-8')
    result = builder.local_readme_image(tmp_path / 'SKILL.md', 200)
    assert result['source'].endswith(':valid.png')


def test_animated_gif_bytes_are_preserved(builder, tmp_path):
    from PIL import Image
    frames = [Image.new('RGB', (8, 8), color) for color in ['red', 'blue']]
    image = tmp_path / 'demo.gif'
    frames[0].save(image, save_all=True, append_images=frames[1:], duration=100, loop=0)
    (tmp_path / 'README.md').write_text('<img src="demo.gif">', encoding='utf-8')
    result = builder.local_readme_image(tmp_path / 'SKILL.md', 524288)
    assert base64.b64decode(result['value'].split(',', 1)[1]) == image.read_bytes()


def test_readme_preview_is_used_before_generated_fallback(builder, tmp_path):
    (tmp_path / 'hero.png').write_bytes(PNG)
    (tmp_path / 'README.md').write_text('![Preview](hero.png)', encoding='utf-8')
    result = builder.choose_image(tmp_path / 'SKILL.md', {}, 'other', 'real-skill', 'real-skill', 'Example', {'image': {'max_embedded_bytes': 524288}})
    assert result['status'] == 'verified-local'
    assert result['source'].startswith('readme:')


def test_frontmatter_image_cannot_escape_skill_folder(builder, tmp_path):
    skill = tmp_path / 'skill'
    skill.mkdir()
    (tmp_path / 'private.png').write_bytes(PNG)
    (skill / 'preview.png').write_bytes(PNG)
    config = {
        'image': {
            'max_embedded_bytes': 524288,
            'github_repository_previews': False,
            'frontmatter_keys': ['preview_image'],
        }
    }
    escaped = builder.choose_image(
        skill / 'SKILL.md',
        {'preview_image': '../private.png'},
        'other', 'skill', 'skill/SKILL.md', 'Example',
        config,
    )
    assert escaped['status'] == 'generated-fallback'
    assert escaped['source'] == 'invalid-frontmatter:preview_image'
    inside = builder.choose_image(
        skill / 'SKILL.md',
        {'preview_image': 'preview.png'},
        'other', 'skill', 'skill/SKILL.md', 'Example',
        config,
    )
    assert inside['status'] == 'verified-local'
    assert inside['source'] == 'frontmatter:preview_image'


def test_sidecar_image_cannot_escape_skill_folder(builder, tmp_path):
    skill = tmp_path / 'skill'
    skill.mkdir()
    (tmp_path / 'private.png').write_bytes(PNG)
    config = {
        'image': {
            'max_embedded_bytes': 524288,
            'github_repository_previews': False,
            'sidecar_names': ['../private.png'],
        }
    }
    result = builder.choose_image(
        skill / 'SKILL.md', {}, 'other', 'skill', 'skill/SKILL.md', 'Example', config,
    )
    assert result['status'] == 'generated-fallback'


def test_image_data_uri_rejects_oversized_file_before_reading(builder, tmp_path, monkeypatch):
    image = tmp_path / 'oversized.png'
    image.write_bytes(PNG + b'x' * 2048)

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError('oversized image must be rejected by stat before read_bytes')

    monkeypatch.setattr(Path, 'read_bytes', unexpected_read)
    assert builder.image_data_uri(image, 128) == ''


def test_scan_does_not_follow_links_outside_root(builder, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'SKILL.md').write_text(
        '---\nname: outside-leak\ndescription: private outside content\n---\n',
        encoding='utf-8',
    )
    root = tmp_path / 'root'
    root.mkdir()
    linked = root / 'linked'
    if sys.platform == 'win32':
        created = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(linked), str(outside)],
            capture_output=True,
            text=True,
        )
        if created.returncode != 0:
            pytest.skip('Windows junction creation is unavailable in this environment')
    else:
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip('Directory symlink creation is unavailable in this environment')
    config = builder.load_config(builder.DEFAULT_CONFIG)
    config['github_discovery']['enabled'] = False
    config['image']['github_repository_previews'] = False
    items, _, _ = builder.scan(
        config,
        [{'path': str(root), 'label': 'Skills', 'kind': 'skill'}],
        False,
        tmp_path / 'cache',
    )
    assert items == []


def _make_dir_link(link: Path, target: Path) -> bool:
    if sys.platform == 'win32':
        created = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
            capture_output=True,
            text=True,
        )
        return created.returncode == 0
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except OSError:
        return False


def test_follow_linked_dirs_opts_in_and_keeps_unique_identities(builder, tmp_path):
    """--follow-linked-dirs includes junctioned skills, each with its own identity."""

    first = tmp_path / 'first-target'
    second = tmp_path / 'second-target'
    for outside, name in ((first, 'linked-one'), (second, 'linked-two')):
        outside.mkdir()
        (outside / 'SKILL.md').write_text(
            f'---\nname: {name}\ndescription: linked outside the scan root\n---\n',
            encoding='utf-8',
        )
    root = tmp_path / 'root'
    root.mkdir()
    links = []
    for outside in (first, second):
        linked = root / outside.name
        if not _make_dir_link(linked, outside):
            pytest.skip('Directory link creation is unavailable in this environment')
        links.append(linked)
    config = builder.load_config(builder.DEFAULT_CONFIG)
    config['github_discovery']['enabled'] = False
    config['image']['github_repository_previews'] = False

    # Default: skipped, never silently.
    items, _, _ = builder.scan(
        config,
        [{'path': str(root), 'label': 'Skills', 'kind': 'skill'}],
        False,
        tmp_path / 'cache-default',
    )
    assert items == []
    assert sorted(entry['name'] for entry in config['_skipped_linked_dirs']) == [
        'first-target',
        'second-target',
    ]

    # Opt-in: both linked skills included, with distinct ids and real relative paths.
    config['scan']['follow_linked_dirs'] = True
    config.pop('_skipped_linked_dirs', None)
    items, _, _ = builder.scan(
        config,
        [{'path': str(root), 'label': 'Skills', 'kind': 'skill'}],
        False,
        tmp_path / 'cache-follow',
    )
    names = {item['name'] for item in items}
    assert names == {'linked-one', 'linked-two'}
    assert {item['id'] for item in items} and len(items) == 2
    assert all(item['relative_path'].endswith('SKILL.md') and '/' in item['relative_path'] for item in items)
