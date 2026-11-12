import base64
import importlib.util
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
