# Agent Skill Catalog

`Agent Skill Catalog` 是一个本地优先的 Skill：它扫描你明确指定的 `SKILL.md` 根目录和可选插件缓存，生成可搜索的桌面 HTML 目录与 `catalog.json`。

它解决的不是“多装一个 Skill”，而是把已经安装的能力整理清楚：按功能分类、保留分类证据和置信度、合并真实的主/子 Skill 家族、将插件与独立 Skill 分开展示，并提供调用方式、GitHub 元数据和图片证据状态。

## 特性

- 只读扫描指定目录，不安装、不执行、不修改被扫描的 Skill。
- 分类结果可审查：输出候选分类、命中证据、胜出边际和低置信度标记。
- 主 Skill 与子 Skill 聚合；插件按 `provider:name` 聚合，避免同名插件混在一起。
- 图片严格区分真实本地预览、整理后的本地预览、远程元数据和生成封面；缺少证据时明确标注。
- GitHub 地址仅从本地 `SKILL.md`、Git 配置或人工整理文件读取，不联网抓取。
- 页面提供“技能”和“插件”两个视图，以及本地受限刷新接口。

## 首次生成

```powershell
python scripts/build_catalog.py --root "C:\\path\\to\\skills" --output-dir "$env:TEMP\\agent-skill-catalog-output"
```

扫描插件缓存时，复制并修改 `references/catalog-config.windows.example.json` 或 `references/catalog-config.posix.example.json`，将对应根目录标记为 `"kind": "plugin"`：

```powershell
python scripts/build_catalog.py --config .\my-catalog-config.json --output-dir "$env:TEMP\\agent-skill-catalog-output"
```

生成后直接打开输出目录中的 `index.html`。它是自包含页面，可以离线查看。

## 页面内刷新

要让“刷新索引”按钮生效，使用相同的配置和根目录启动本地服务：

```powershell
python scripts/serve_catalog.py --config .\my-catalog-config.json --output-dir "$env:TEMP\\agent-skill-catalog-output"
```

服务默认只绑定 `127.0.0.1:8765`。刷新请求不接受网页传入的路径或命令，只会重复启动时确认过的构建参数。

## 人工整理文件

当自动分类、中文说明、GitHub 地址、家族归属或图片需要人工修正时，复制 `references/catalog-curation.example.json`，并通过 `--curation` 传入。整理规则只作用于本次目录生成，不会改写原 Skill。

## 发布验证

```powershell
python scripts/validate_package.py .
python tests/test_build_catalog.py
python scripts/package_skill.py .
```

发布 ZIP 位于 `dist/agent-skill-catalog-skill.zip`，同目录的 `.sha256` 文件给出校验值。打包过程会排除扫描结果、浏览器缓存、私有目录、日志、Git 元数据和本机配置。

## 许可

MIT。详见 [LICENSE](LICENSE)。
