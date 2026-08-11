# Agent Skill Catalog

[English](README.md) | 面向 Codex 和其他 AI 编程 Agent 的本地 Skill 与插件目录生成器。

`Agent Skill Catalog` 只扫描你明确指定的 `SKILL.md` 根目录，生成可搜索的桌面目录。它以可审查的证据进行分类，聚合真实的主/子 Skill 家族，把插件与独立 Skill 分开，并在详情中展示调用方式、GitHub 元数据、图片证据与来源位置。

它不会安装、执行、修改或上传被扫描的 Skill。

## 产品演示

以下动画由项目真实生成的页面录制，使用的是公开演示 Skill 数据。它依次展示分类总览、按类别筛选和打开 Skill 详情。

![Agent Skill Catalog：浏览分类、筛选视频 Skill、打开详情](docs/media/agent-skill-catalog-demo.gif)

| 目录总览 | Skill 详情 |
| --- | --- |
| ![Agent Skill Catalog 分类筛选和 Skill 卡片总览](docs/media/agent-skill-catalog-overview.png) | ![Agent Skill Catalog 的调用方式和分类证据详情](docs/media/agent-skill-catalog-detail.png) |

## 安装

通过 GitHub CLI 安装已发布的 Skill：

```powershell
gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --agent codex --scope user
```

发布版本后，可固定到指定版本：

```powershell
gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --pin v0.2.1 --agent codex --scope user
```

可安装内容位于 [`skills/agent-skill-catalog`](skills/agent-skill-catalog)。这是 GitHub Agent Skills 的发现路径；仓库根目录只放介绍文档、测试、发布证据与演示媒体。

## 在 Agent 中使用

给 Agent 明确任务和本地根目录，例如：

```text
Use $agent-skill-catalog to scan my local Skill root and Codex plugin cache, build a searchable catalog, keep standalone Skills and plugins separate, and report low-confidence classifications and missing image evidence. Do not install, edit, or execute scanned Skills.
```

## 从源码生成目录

要求：Python 3.10+，只使用标准库。

```powershell
python skills/agent-skill-catalog/scripts/build_catalog.py `
  --root "C:\path\to\skills" `
  --output-dir "$env:TEMP\agent-skill-catalog-output"
```

扫描插件缓存时，复制平台示例配置，将对应根目录的 `kind` 设置为 `plugin`，再传入 `--config`：

```powershell
python skills/agent-skill-catalog/scripts/build_catalog.py `
  --config .\my-catalog-config.json `
  --output-dir "$env:TEMP\agent-skill-catalog-output"
```

生成后可直接打开 `index.html`。需要启用页面内“刷新索引”时，用同一批根目录和整理文件启动受限的本地服务：

```powershell
python skills/agent-skill-catalog/scripts/serve_catalog.py `
  --output-dir "$env:TEMP\agent-skill-catalog-output" `
  --root "C:\path\to\skills"
```

## 目录内容

| 范围 | 内容 |
| --- | --- |
| 分类 | 候选分类、命中证据、置信度、胜出边际和低置信度标记 |
| Skill 家族 | 仅在嵌套目录、同名主 Skill 加至少两个来源一致的同前缀子 Skill，或人工整理证据存在时聚合主/子 Skill |
| 插件 | 按 `provider:name` 聚合到独立视图，不与独立 Skill 混在一起 |
| 调用 | Agent 调用提示与相对来源位置 |
| 图片 | 已验证本地图片、整理后预览、远程元数据或明确标注的回退封面 |
| GitHub | 仅在本地 Skill 元数据、Git 配置或整理文件提供时显示仓库地址 |

## 隐私与边界

- 只扫描操作者指定的根目录。
- 扫描根目录保持只读。
- 不抓取远程内容，不执行发现到的 Skill。
- 默认隐藏绝对路径。
- 刷新接口不接受网页传入的命令或路径。

## 兼容与发现

- GitHub Agent Skills：可安装包位于 `skills/agent-skill-catalog/SKILL.md`。
- Codex：包含 UI 元数据 `agents/openai.yaml`，并保留 Yao Meta 接口契约 `agents/interface.yaml`。
- 通用本地使用：使用明确的根目录直接运行 Python 脚本。

## 验证

```powershell
python tools/validate_package.py .
python tests/test_build_catalog.py
gh skill publish --dry-run
```

截图使用的公开演示数据位于 [`docs/demo`](docs/demo)。其中的 `DEMO.md` 是刻意不参与 GitHub Skill 发现的示例文件，不含本机路径、私人目录或个人 Skill 清单。

## 许可

MIT。详见 [LICENSE](LICENSE)。
