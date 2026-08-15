# 给其他 Agent 的中文提示模板

## 首次扫描

```text
请读取 `agent-skill-catalog/SKILL.md`，扫描以下本地根目录：
- <根目录 1>
- <根目录 2，可选>

把结果写到 <输出目录>，运行：
python scripts/build_catalog.py --root <根目录 1> --output-dir <输出目录>

只读扫描，不安装、不修改、不删除任何被扫描的 Skill。首次构建就带上 `--require-complete-descriptions`。退出码 3 表示说明队列未完成；这是你必须自行完成的工作队列，不要让用户手工补。使用相同的根目录或配置运行 `python scripts/description_queue.py next --output-dir <输出目录> --batch-size 12`，读取生成的 `description-batch.json`，根据本地 `SKILL.md` 证据和可用的 GitHub README 摘要，用自然中文写清用途、适用场景、输入输出或限制。按批次里的 `response_contract` 写入 `description-batch.responses.json`，再运行 `python scripts/description_queue.py apply --output-dir <输出目录> --input <输出目录>/description-batch.responses.json`。重复 next/apply，直到 `batch_count` 为 0；中途停止时直接继续，已完成内容保存在 `catalog-curation.json`。最后用 `--refresh --require-complete-descriptions` 重建，只有退出码为 0 且 `pending_description_count` 为 0 才算完成。证据不足的项保留 `missing evidence`，不要编造。最后报告：实际扫描根、catalog.json、description-enrichment.json、index.html、独立 Skill/插件 Skill/插件/家族数量、分类覆盖、低置信度项、图片状态、GitHub 元数据来源和未找到的根目录。
```

## 刷新已有 Agent Skill Catalog

```text
请在确认输出目录属于当前 Agent Skill Catalog 后，使用 `--refresh` 刷新：
python scripts/build_catalog.py --config references/catalog-config.json --output-dir <已有输出目录> --refresh

刷新只允许覆盖该输出目录。不要清理源目录，不要凭空补分类或图片。先检查 `catalog.json` 的 `previous_generated_at`、`category_coverage.uncovered`、`families`、`plugins` 和 `unresolved_roots`，再打开 HTML。若希望网页按钮自动刷新，请用 `python scripts/serve_catalog.py --config <配置> --curation <整理文件，可选> --output-dir <已有输出目录> --require-complete-descriptions` 启动服务；说明队列未完成时不能把刷新报告为成功。
```

## 分类争议

```text
请不要默默改分类。指出该项的 `category_evidence`、置信度、命中的规则和候选分类；如果需要人工决定，给出 A/B 选项并暂停，等待我确认后再写入 `category_overrides`。
```

## 图片证据

```text
请按 `references/image-priority.md` 检查图片。默认先保留人工选择图，再从已识别的 GitHub 仓库获取并缓存公开仓库图片，随后才检查 Skill 自带本地图片。区分 `curated-local`、`github-repository`、`github-social-preview`、`verified-local`、`generated-fallback`、`remote-metadata`、`category-cover` 和 `missing`；不要把类别封面当作 Skill 预览。网页详情里的“选择图片”只能写入输出目录的 `curated-images/` 和 `catalog-curation.json`，不得改写 Skill 源目录。生成的说明封面必须写明 Skill 名称和功能摘要，不得伪装成源项目截图。
```
