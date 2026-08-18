"""Render the self-contained desktop catalog page."""

from __future__ import annotations

import json
from typing import Any, Dict


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Agent Skill Catalog</title>
  <link rel="icon" href="favicon.svg">
  <style>
    :root {
      font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
      color: #182326;
      background: #f1f3ef;
      --ink: #182326;
      --muted: #607176;
      --line: #d7ded9;
      --paper: #fff;
      --green: #104e4b;
      --green-dark: #0a3b39;
      --orange: #e55732;
      --soft: #edf2ee;
      --radius: 6px;
      --ease: cubic-bezier(.25,1,.5,1);
    }
    * { box-sizing: border-box; }
    html { scrollbar-gutter: stable; }
    body { min-width: 1180px; margin: 0; background: #f1f3ef; }
    body.modal-locked { overflow: hidden; }
    button, input { font: inherit; }
    button { letter-spacing: 0; }
    a { color: inherit; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    :focus-visible { outline: 3px solid #e55732; outline-offset: 3px; }
    .shell { width: min(1500px, calc(100% - 56px)); margin: auto; padding: 0 0 54px; }
    .topbar { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; min-height: 72px; border-bottom: 1px solid rgba(24,35,38,.14); background: rgba(241,243,239,.93); backdrop-filter: blur(18px) saturate(140%); }
    .brand { display: flex; align-items: center; gap: 11px; font-size: 19px; font-weight: 780; }
    .brand-mark { display: grid; width: 36px; height: 36px; place-items: center; border-radius: 5px; color: #fff; background: var(--green); font-size: 13px; }
    .refresh-wrap { display: flex; align-items: center; gap: 12px; }
    .status { max-width: 360px; color: var(--muted); font-size: 12px; text-align: right; }
    .button { min-height: 38px; padding: 8px 13px; border: 1px solid #b9c8c2; border-radius: 5px; color: var(--green); background: #fff; font-weight: 720; cursor: pointer; transition: transform .16s var(--ease), box-shadow .16s var(--ease), border-color .16s var(--ease); }
    .button:hover { transform: translateY(-1px); border-color: #7da39a; box-shadow: 0 7px 16px rgba(16,78,75,.1); }
    .button:active { transform: scale(.98); }
    .button.primary { border-color: var(--green); color: #fff; background: var(--green); }
    .button.primary:hover { background: var(--green-dark); }
    .button.danger { border-color: #d5a091; color: #a93d21; background: #fff8f6; }
    .button:disabled { cursor: not-allowed; opacity: .48; transform: none; box-shadow: none; }
    .intro { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 42px; align-items: end; padding: 35px 0 25px; }
    .intro h1 { max-width: 820px; margin: 0; font-size: 36px; line-height: 1.14; letter-spacing: 0; }
    .intro p { max-width: 800px; margin: 12px 0 0; color: var(--muted); font-size: 15px; line-height: 1.65; }
    .stat { min-width: 150px; padding-left: 20px; border-left: 3px solid var(--orange); }
    .stat strong { display: block; color: var(--green); font-size: 38px; line-height: 1; }
    .stat span { display: block; margin-top: 7px; color: var(--muted); font-size: 13px; }
    .control-row { display: grid; grid-template-columns: auto minmax(340px,1fr); gap: 14px; margin-bottom: 18px; }
    .tabs { display: inline-flex; overflow: hidden; border: 1px solid #c6d0cb; border-radius: 5px; background: #fff; }
    .tabs button { min-width: 94px; padding: 9px 16px; border: 0; border-right: 1px solid #c6d0cb; color: #40565a; background: transparent; font-weight: 740; cursor: pointer; }
    .tabs button:last-child { border-right: 0; }
    .tabs button.active { color: #fff; background: var(--green); }
    .search { width: 100%; min-height: 42px; padding: 10px 14px; border: 1px solid #c6d0cb; border-radius: 5px; color: var(--ink); background: #fff; font-size: 14px; }
    .search:focus { border-color: var(--green); outline: 0; box-shadow: 0 0 0 4px rgba(16,78,75,.1); }
    .overview { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 11px; margin: 0 0 24px; }
    .category-card { position: relative; min-width: 0; height: 132px; overflow: hidden; padding: 0; border: 0; border-radius: var(--radius); color: #fff; text-align: left; background: #233d3d; cursor: pointer; box-shadow: 0 8px 20px rgba(22,39,40,.09); transition: transform .2s var(--ease), box-shadow .2s var(--ease); }
    .category-card:hover { transform: translateY(-3px); box-shadow: 0 15px 30px rgba(22,39,40,.2); }
    .category-card img { width: 100%; height: 100%; object-fit: cover; filter: saturate(.78) contrast(1.04); transition: transform .45s var(--ease); }
    .category-card:hover img { transform: scale(1.045); }
    .category-shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(8,24,25,.05) 12%, rgba(8,24,25,.88) 100%); }
    .category-copy { position: absolute; inset: auto 14px 13px; }
    .category-copy strong { display: block; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 17px; font-weight: 800; text-shadow: 0 2px 12px rgba(0,0,0,.36); }
    .category-copy span { display: block; margin-top: 3px; color: rgba(255,255,255,.78); font-size: 12px; }
    .filters { display: flex; gap: 7px; flex-wrap: wrap; margin: 0 0 24px; }
    .filter { min-height: 34px; padding: 7px 11px; border: 1px solid #c9d2ce; border-radius: 5px; color: #4b5e63; background: rgba(255,255,255,.72); cursor: pointer; }
    .filter:hover { border-color: #8facA5; color: var(--green); }
    .filter.active { border-color: var(--green); color: #fff; background: var(--green); }
    .results-head { display: flex; align-items: baseline; justify-content: space-between; margin: 0 0 14px; }
    .results-head h2 { margin: 0; font-size: 21px; }
    .results-head span { color: var(--muted); font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 16px; }
    .card { display: grid; min-width: 0; grid-template-rows: auto 1fr; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); background: #fff; box-shadow: 0 7px 20px rgba(29,52,54,.055); transition: transform .2s var(--ease), box-shadow .2s var(--ease), border-color .2s var(--ease); }
    .card:hover { transform: translateY(-3px); border-color: #afc3bc; box-shadow: 0 16px 34px rgba(29,52,54,.13); }
    .thumb { position: relative; display: grid; aspect-ratio: 16/8.6; place-items: center; overflow: hidden; background: #e9eeeb; }
    .thumb img { width: 100%; height: 100%; object-fit: contain; transition: transform .38s var(--ease); }
    .card:hover .thumb img { transform: scale(1.025); }
    .thumb-link { display: block; color: inherit; }
    .image-badge { position: absolute; right: 9px; bottom: 9px; padding: 5px 7px; border-radius: 4px; color: #f0f7f5; background: rgba(8,36,36,.83); font-size: 11px; backdrop-filter: blur(7px); }
    .card-body { display: flex; min-width: 0; flex-direction: column; padding: 15px; }
    .card-top { display: flex; align-items: start; justify-content: space-between; gap: 10px; }
    .card h3 { min-width: 0; margin: 0; font-size: 17px; overflow-wrap: anywhere; }
    .tag { flex: none; padding: 4px 7px; border-radius: 4px; color: #3f5f5c; background: var(--soft); font-size: 11px; }
    .card-description { display: -webkit-box; overflow: hidden; margin: 9px 0 13px; color: #53686d; font-size: 13px; line-height: 1.58; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
    .card-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: auto; color: #6a797d; font-size: 12px; }
    .card-actions { display: flex; gap: 7px; }
    .card-actions .button { min-height: 32px; padding: 6px 9px; font-size: 12px; }
    .empty { grid-column: 1/-1; padding: 48px; border: 1px dashed #b6c5bf; color: var(--muted); background: #fff; text-align: center; }

    dialog { padding: 0; border: 0; }
    dialog::backdrop { background: rgba(7,21,23,.68); backdrop-filter: blur(6px); }
    #detail { width: min(1240px, calc(100vw - 56px)); max-width: none; max-height: none; overflow: hidden; border-radius: 8px; background: #fff; box-shadow: 0 34px 110px rgba(4,18,20,.44); }
    .detail-shell { position: relative; display: grid; height: min(820px, calc(100vh - 56px)); grid-template-columns: 440px minmax(0,1fr); overflow: hidden; }
    .detail-media, .detail-content { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
    .detail-media { padding: 22px; border-right: 1px solid var(--line); background: #e9eeeb; }
    .detail-content { padding: 32px 42px 40px; background: #fff; }
    .close { position: absolute; z-index: 4; top: 13px; right: 14px; display: grid; width: 36px; height: 36px; place-items: center; padding: 0; border: 1px solid #cdd6d2; border-radius: 5px; color: #476064; background: rgba(255,255,255,.92); font-size: 24px; line-height: 1; cursor: pointer; box-shadow: 0 4px 12px rgba(18,41,42,.08); }
    .close:hover { color: var(--green); background: #fff; }
    .gallery { display: grid; gap: 16px; }
    .gallery figure { margin: 0; overflow: hidden; border: 1px solid #cfd8d3; border-radius: 6px; background: #fff; }
    .gallery a { display: grid; min-height: 250px; place-items: center; background: #f8faf8; }
    .gallery img { display: block; width: 100%; max-height: 520px; object-fit: contain; }
    .gallery figcaption { display: flex; justify-content: space-between; gap: 12px; padding: 9px 11px; border-top: 1px solid #dbe2de; color: #617277; font-size: 11px; }
    .media-tools { margin-top: 18px; padding: 16px; border: 1px solid #cbd6d1; border-radius: 6px; background: rgba(255,255,255,.86); }
    .media-tools h3 { margin: 0 0 6px; font-size: 15px; }
    .media-tools p { margin: 0 0 12px; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .media-tool-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .file-button { position: relative; overflow: hidden; }
    .file-button input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .image-status { display: block; min-height: 18px; margin-top: 9px; color: var(--muted); font-size: 11px; }
    .detail-heading { padding-right: 44px; }
    .detail-heading h2 { margin: 8px 0 12px; font-size: 29px; line-height: 1.2; overflow-wrap: anywhere; }
    .detail-summary { margin: 0; color: #50666b; font-size: 15px; line-height: 1.75; }
    .section-label { margin: 25px 0 9px; color: var(--green); font-size: 12px; font-weight: 800; }
    .github { display: inline-block; color: #08717a; font-weight: 700; overflow-wrap: anywhere; }
    .code { padding: 13px 15px; border-left: 3px solid var(--orange); color: #263f42; background: #edf2ee; font-size: 13px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
    .subskills { border-top: 1px solid var(--line); }
    .subskill { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 7px 12px; padding: 14px 0; border-bottom: 1px solid var(--line); }
    .subskill strong { overflow-wrap: anywhere; }
    .subskill p { grid-column: 1/-1; margin: 0; color: #627579; font-size: 12px; line-height: 1.58; }
    .detail-evidence { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
    .detail-evidence div { padding: 10px 11px; background: #f2f5f2; color: #5c7075; font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }
    .detail-evidence strong { display: block; margin-bottom: 2px; color: var(--green); font-size: 11px; }
    .danger-zone { margin-top: 28px; padding-top: 20px; border-top: 1px solid #e2bcb1; }
    .danger-zone p { margin: 0 0 10px; color: #7d625c; font-size: 12px; line-height: 1.55; }
    #delete-confirm { width: 470px; border-radius: 7px; background: #fff; box-shadow: 0 24px 80px rgba(4,18,20,.38); }
    .confirm-body { padding: 26px; }
    .confirm-body h2 { margin: 0 0 9px; font-size: 22px; }
    .confirm-body p { margin: 0 0 14px; color: #5d6e72; line-height: 1.6; }
    .confirm-body label { display: block; color: #344a4d; font-size: 13px; font-weight: 700; }
    .confirm-body input { width: 100%; margin-top: 7px; padding: 10px 11px; border: 1px solid #c5cfcb; border-radius: 5px; }
    .confirm-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
    .confirm-status { min-height: 18px; margin-top: 9px; color: #a43e24; font-size: 12px; }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
    @media (prefers-reduced-transparency: reduce) {
      .topbar, dialog::backdrop { backdrop-filter: none; }
      .topbar { background: #f1f3ef; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">AC</span>Agent Skill Catalog</div>
      <div class="refresh-wrap"><span class="status" id="status" role="status" aria-live="polite"></span><button class="button primary" id="refresh" type="button">刷新索引</button></div>
    </header>
    <section class="intro">
      <div><h1>按用途找到 Skill，打开就能看清它怎么用。</h1><p>主 Skill 会合并显示，插件单独归档。每一项都保留功能说明、调用方式、来源位置和可核对的仓库图片。</p></div>
      <div class="stat"><strong id="total"></strong><span id="stat-label"></span></div>
    </section>
    <section class="control-row">
      <nav class="tabs" aria-label="目录视图"><button class="mode active" data-mode="skills" type="button">技能</button><button class="mode" data-mode="plugins" type="button">插件</button></nav>
      <label><span class="sr-only">搜索技能与插件</span><input class="search" id="search" type="search" placeholder="搜索名称、用途、GitHub 或相对路径"></label>
    </section>
    <section class="overview" id="overview" aria-label="分类概览"></section>
    <section class="filters" id="filters" aria-label="分类筛选"></section>
    <section><div class="results-head"><h2 id="result-title"></h2><span id="count"></span></div><div class="grid" id="list"></div></section>
  </main>

  <dialog id="detail" aria-labelledby="detail-name">
    <article class="detail-shell">
      <button class="close" id="close" type="button" title="关闭详情" aria-label="关闭详情">×</button>
      <aside class="detail-media" id="detail-media">
        <div class="gallery" id="detail-gallery"></div>
        <section class="media-tools" id="image-editor" tabindex="-1">
          <h3>更换预览图</h3><p>上传后只替换目录中的预览，不会修改原 Skill。也可以随时恢复为自动获取的 GitHub 图片。</p>
          <div class="media-tool-row"><label class="button file-button" for="image-file">选择本地图片<input id="image-file" type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"></label><button class="button primary" id="image-save" type="button" disabled>保存图片</button><button class="button" id="image-remove" type="button" hidden>恢复自动图</button></div>
          <span class="image-status" id="image-editor-status" role="status" aria-live="polite"></span>
        </section>
      </aside>
      <section class="detail-content" id="detail-content">
        <header class="detail-heading"><span class="tag" id="detail-tag"></span><h2 id="detail-name"></h2><p class="detail-summary" id="detail-description"></p></header>
        <section id="github-panel" hidden><div class="section-label">GitHub 仓库</div><a class="github" id="detail-github" target="_blank" rel="noreferrer"></a></section>
        <div class="section-label">调用方式</div><div class="code" id="detail-invocation"></div>
        <section id="subskills-panel"><div class="section-label" id="subskills-label"></div><div class="subskills" id="detail-subskills"></div></section>
        <div class="section-label">来源位置</div><div class="code" id="detail-locations"></div>
        <div class="section-label">整理依据</div><section class="detail-evidence" id="detail-evidence"></section>
        <section class="danger-zone" id="danger-zone" hidden><div class="section-label">删除 Skill</div><p>只允许删除统一技能库中的顶层独立 Skill。删除后无法从目录中恢复。</p><button class="button danger" id="delete-open" type="button">删除这个 Skill</button></section>
      </section>
    </article>
  </dialog>

  <dialog id="delete-confirm" aria-labelledby="delete-title">
    <form class="confirm-body" method="dialog" id="delete-form"><h2 id="delete-title">确认删除 Skill</h2><p>请输入完整 Skill 名称 <strong id="delete-name"></strong>。此操作会删除它的整个顶层目录。</p><label>Skill 名称<input id="delete-input" autocomplete="off" spellcheck="false"></label><div class="confirm-status" id="delete-status" role="status" aria-live="polite"></div><div class="confirm-actions"><button class="button" id="delete-cancel" type="button">取消</button><button class="button danger" id="delete-submit" type="submit" disabled>永久删除</button></div></form>
  </dialog>

  <script>
    const data=__CATALOG__;
    const $=selector=>document.querySelector(selector);
    const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    const labels=Object.fromEntries(Object.entries(data.categories||{}).map(([id,meta])=>[id,meta.label||id]));
    const byId=new Map((data.items||[]).map(item=>[item.id,item]));
    const state={mode:'skills',category:'all',query:''};
    let activeRecord=null; let selectedImage=null; let lockedScrollY=0; let lastFocus=null;
    const records=()=>state.mode==='plugins'?(data.plugins||[]):(data.families||[]);
    const recordSkills=record=>(record.skill_ids||[]).map(id=>byId.get(id)).filter(Boolean);
    const primarySkill=record=>{const skills=recordSkills(record);return record.primary_id?(skills.find(item=>item.id===record.primary_id)||skills[0]||record):(skills[0]||record)};
    const recordText=record=>[record.name,record.description,record.invocation,...(record.locations||[]),record.github?.url,...recordSkills(record).flatMap(item=>[item.name,item.description,item.relative_path,item.github?.url])].join(' ').toLowerCase();
    const filtered=()=>records().filter(record=>(state.category==='all'||record.category===state.category)&&(!state.query||recordText(record).includes(state.query)));
    const imageLabel=image=>image?.status==='curated-local'?'人工预览图':image?.status==='github-repository'?'GitHub 项目图片':image?.status==='github-social-preview'?'GitHub 仓库封面':image?.status==='verified-local'?'Skill 自带图片':image?.status==='remote-metadata'?'远程图片信息':'自动生成封面';
    function preview(record){const image=record.image||{};const picture=`<div class="thumb"><img src="${escapeHtml(image.value||'')}" alt="${escapeHtml(record.name)} 的预览图"><span class="image-badge">${escapeHtml(imageLabel(image))}</span></div>`;return record.github?.url?`<a class="thumb-link" href="${escapeHtml(record.github.url)}" target="_blank" rel="noreferrer" title="打开 GitHub 仓库">${picture}</a>`:picture}
    function card(record){const skillCount=(record.skill_ids||[]).length;const countText=state.mode==='plugins'?`携带 ${skillCount} 个技能`:(skillCount>1?`包含 ${skillCount} 个子技能`:'独立技能');return `<article class="card">${preview(record)}<div class="card-body"><div class="card-top"><h3>${escapeHtml(record.name)}</h3><span class="tag">${escapeHtml(labels[record.category]||record.category)}</span></div><p class="card-description">${escapeHtml(record.description)}</p><div class="card-meta"><span>${countText}</span><div class="card-actions"><button class="button" type="button" data-record="${escapeHtml(record.id)}">查看详情</button><button class="button" type="button" data-image-record="${escapeHtml(record.id)}">换图</button></div></div></div></article>`}
    const categoryArt={
      visual:{bg:'#183d3d',accent:'#f4c95d',soft:'#8fd3c7',motif:'<rect x="690" y="108" width="310" height="205" rx="18" fill="none" stroke="currentColor" stroke-width="18"/><path d="M724 276l82-84 72 62 54-51 45 73" fill="none" stroke="currentColor" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/><rect x="824" y="346" width="260" height="158" rx="15" fill="none" stroke="currentColor" stroke-width="12" opacity=".55"/>'},
      video:{bg:'#402b35',accent:'#ff846a',soft:'#ffc7a7',motif:'<rect x="682" y="132" width="376" height="270" rx="24" fill="none" stroke="currentColor" stroke-width="18"/><path d="M836 214l104 73-104 73z" fill="currentColor"/><path d="M715 470h310M738 445v50M803 445v50M868 445v50M933 445v50M998 445v50" stroke="currentColor" stroke-width="13" opacity=".6"/>'},
      audio:{bg:'#25344b',accent:'#7dd3fc',soft:'#b9f4e5',motif:'<path d="M670 320h46l24-104 42 230 42-312 46 374 43-250 37 146 26-84h92" fill="none" stroke="currentColor" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/><path d="M690 530h360" stroke="currentColor" stroke-width="10" opacity=".35"/>'},
      content:{bg:'#4d3428',accent:'#f6bd60',soft:'#f7e1b5',motif:'<rect x="686" y="110" width="340" height="408" rx="18" fill="none" stroke="currentColor" stroke-width="15"/><path d="M738 186h236M738 240h190M738 324h236M738 370h214M738 416h162" stroke="currentColor" stroke-width="15" stroke-linecap="round"/><path d="M912 84l74 74" stroke="currentColor" stroke-width="24" opacity=".5"/>'},
      internet_search:{bg:'#123b4a',accent:'#57d6c3',soft:'#b7e4ff',motif:'<path d="M850 112c-118 0-214 96-214 214s96 214 214 214 214-96 214-214-96-214-214-214zM642 326h416M850 118c58 61 89 131 89 208s-31 147-89 208M850 118c-58 61-89 131-89 208s31 147 89 208" fill="none" stroke="currentColor" stroke-width="14"/><path d="M1000 472l96 96" stroke="currentColor" stroke-width="24" stroke-linecap="round"/>'},
      learning:{bg:'#43385a',accent:'#f2cf67',soft:'#c6b8ff',motif:'<path d="M660 180c88-40 176-31 248 22v310c-72-53-160-62-248-22zM1156 180c-88-40-176-31-248 22v310c72-53 160-62 248-22z" fill="none" stroke="currentColor" stroke-width="17" stroke-linejoin="round"/><path d="M908 202v310" stroke="currentColor" stroke-width="12" opacity=".55"/>'},
      securities:{bg:'#244036',accent:'#f3c969',soft:'#9ee0bd',motif:'<path d="M664 480V320M722 406V194M780 502V350M838 300V142M896 430V248M954 330V168M1012 462V286M1070 260V108" stroke="currentColor" stroke-width="13"/><path d="M642 438l95-86 82 30 92-124 77 36 108-130" fill="none" stroke="currentColor" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/>'},
      data:{bg:'#293850',accent:'#66c7f0',soft:'#a9e0c2',motif:'<path d="M672 504V376h80v128M790 504V270h80v234M908 504V176h80v328M1026 504V112h80v392" fill="none" stroke="currentColor" stroke-width="17"/><path d="M650 546h480" stroke="currentColor" stroke-width="12" opacity=".5"/><path d="M686 320l144-100 120 40 134-130" fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round"/>'},
      development:{bg:'#26372f',accent:'#8bd6a6',soft:'#f2cc78',motif:'<path d="M790 172L650 326l140 154M980 172l140 154-140 154M930 126L842 526" fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" stroke-linejoin="round"/><path d="M682 568h410" stroke="currentColor" stroke-width="9" opacity=".35"/>'},
      productivity:{bg:'#40404a',accent:'#f2c66d',soft:'#c4d8ff',motif:'<rect x="706" y="100" width="310" height="410" rx="18" fill="none" stroke="currentColor" stroke-width="16"/><path d="M764 196h194M764 254h194M764 312h126" stroke="currentColor" stroke-width="15" stroke-linecap="round"/><path d="M770 407l58 54 130-142" fill="none" stroke="currentColor" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/><rect x="654" y="150" width="52" height="310" fill="currentColor" opacity=".35"/>'},
      system_ops:{bg:'#283a3b',accent:'#72d0c6',soft:'#f3c36b',motif:'<rect x="650" y="120" width="456" height="390" rx="20" fill="none" stroke="currentColor" stroke-width="16"/><path d="M650 198h456" stroke="currentColor" stroke-width="14"/><path d="M710 278l64 54-64 54M816 394h132" fill="none" stroke="currentColor" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/><path d="M956 276h94M956 326h66" stroke="currentColor" stroke-width="14" opacity=".55"/>'},
      specialist:{bg:'#46353a',accent:'#f39a7d',soft:'#f3d590',motif:'<path d="M856 112l54 128 138 12-104 90 31 136-119-72-119 72 31-136-104-90 138-12z" fill="none" stroke="currentColor" stroke-width="17" stroke-linejoin="round"/><path d="M856 224v204M754 326h204" stroke="currentColor" stroke-width="18" opacity=".55"/>'},
      other:{bg:'#343a40',accent:'#c4d0d8',soft:'#f1c978',motif:'<rect x="660" y="122" width="166" height="166" rx="20" fill="none" stroke="currentColor" stroke-width="16"/><rect x="862" y="122" width="236" height="166" rx="20" fill="none" stroke="currentColor" stroke-width="16"/><rect x="660" y="324" width="236" height="188" rx="20" fill="none" stroke="currentColor" stroke-width="16"/><rect x="932" y="324" width="166" height="188" rx="20" fill="none" stroke="currentColor" stroke-width="16"/>'}
    };
    function categoryImage(id){const art=categoryArt[id]||categoryArt.other;const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675"><rect width="1200" height="675" fill="${art.bg}"/><path d="M0 92h1200M0 584h1200" stroke="${art.soft}" stroke-width="3" opacity=".16"/><path d="M92 0v675M1120 0v675" stroke="${art.soft}" stroke-width="3" opacity=".12"/><g color="${art.accent}">${art.motif}</g><path d="M92 518h430" stroke="${art.soft}" stroke-width="10" opacity=".22"/><path d="M92 550h298" stroke="${art.soft}" stroke-width="10" opacity=".14"/></svg>`;return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`}
    function renderOverview(){const counts=records().reduce((out,item)=>(out[item.category]=(out[item.category]||0)+1,out),{});$('#overview').innerHTML=Object.keys(labels).filter(id=>counts[id]).map(id=>`<button class="category-card" data-category="${escapeHtml(id)}" type="button"><img src="${escapeHtml(categoryImage(id))}" alt=""><span class="category-shade"></span><span class="category-copy"><strong>${escapeHtml(labels[id])}</strong><span>${counts[id]} ${state.mode==='plugins'?'个插件':'个主技能'}</span></span></button>`).join('')}
    function renderFilters(){const counts=records().reduce((out,item)=>(out[item.category]=(out[item.category]||0)+1,out),{});const entries=[['all','全部',records().length],...Object.keys(labels).filter(id=>counts[id]).map(id=>[id,labels[id],counts[id]])];$('#filters').innerHTML=entries.map(([id,label,count])=>`<button class="filter ${state.category===id?'active':''}" data-category="${escapeHtml(id)}" type="button">${escapeHtml(label)} ${count}</button>`).join('')}
    function render(){const items=filtered();$('#total').textContent=records().length;$('#stat-label').textContent=state.mode==='plugins'?'已整理插件':'已整理主技能';$('#result-title').textContent=state.category==='all'?(state.mode==='plugins'?'全部插件':'全部技能'):(labels[state.category]||state.category);$('#count').textContent=`${items.length} 项结果 · ${data.generated_at||'尚未生成'}`;renderOverview();renderFilters();$('#list').innerHTML=items.length?items.map(card).join(''):'<div class="empty">没有找到匹配的 Skill 或插件。</div>';document.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{state.category=button.dataset.category;render()}));document.querySelectorAll('[data-record]').forEach(button=>button.addEventListener('click',()=>openRecord(button.dataset.record)));document.querySelectorAll('[data-image-record]').forEach(button=>button.addEventListener('click',()=>openRecord(button.dataset.imageRecord,true)))}
    function lockBackground(){if(document.body.classList.contains('modal-locked'))return;lockedScrollY=window.scrollY;document.body.style.position='fixed';document.body.style.top=`-${lockedScrollY}px`;document.body.style.width='100%';document.body.classList.add('modal-locked')}
    function unlockBackground(){if(!document.body.classList.contains('modal-locked'))return;document.body.classList.remove('modal-locked');document.body.style.position='';document.body.style.top='';document.body.style.width='';window.scrollTo(0,lockedScrollY)}
    function uniqueGallery(record){const entries=[{name:record.name,image:record.image,github:record.github?.url},...recordSkills(record).map(item=>({name:item.name,image:item.image,github:item.github?.url}))];const seen=new Set();return entries.filter(entry=>{const value=entry.image?.value||'';if(!value||seen.has(value))return false;seen.add(value);return true})}
    function canDelete(record){const skills=recordSkills(record);const item=primarySkill(record);return state.mode==='skills'&&skills.length===1&&item?.allow_delete===true&&item?.family_size===1}
    function openRecord(id,focusImage=false){const record=records().find(entry=>entry.id===id);if(!record)return;lastFocus=document.activeElement;activeRecord=record;selectedImage=null;const skills=recordSkills(record);const image=record.image||{};$('#image-file').value='';$('#image-save').disabled=true;$('#image-remove').hidden=image.status!=='curated-local';$('#image-editor-status').textContent='';const gallery=uniqueGallery(record);$('#detail-gallery').innerHTML=gallery.map((entry,index)=>`<figure>${entry.github?`<a href="${escapeHtml(entry.github)}" target="_blank" rel="noreferrer" title="打开 GitHub 仓库">`: '<div>'}<img src="${escapeHtml(entry.image.value)}" alt="${escapeHtml(entry.name)} 的项目图片">${entry.github?'</a>':'</div>'}<figcaption><span>${escapeHtml(index===0?record.name:entry.name)}</span><span>${escapeHtml(imageLabel(entry.image))}</span></figcaption></figure>`).join('');$('#detail-tag').textContent=labels[record.category]||record.category;$('#detail-name').textContent=state.mode==='plugins'?`${record.name} 插件`:record.name;$('#detail-description').textContent=record.description;$('#detail-invocation').textContent=record.invocation;$('#detail-locations').textContent=(record.locations||[]).join('\n');const github=record.github?.url;$('#github-panel').hidden=!github;if(github){$('#detail-github').href=github;$('#detail-github').textContent=github}$('#subskills-label').textContent=state.mode==='plugins'?`插件携带技能（${skills.length}）`:(skills.length>1?`包含的子技能（${skills.length}）`:'技能说明');$('#detail-subskills').innerHTML=skills.map(item=>`<article class="subskill"><strong>${escapeHtml(item.name)}</strong><span class="tag">${escapeHtml(labels[item.category]||item.category)}</span><p>${escapeHtml(item.description)}</p><p>调用：${escapeHtml(item.invocation)}</p></article>`).join('');$('#detail-evidence').innerHTML=`<div><strong>分类依据</strong>${escapeHtml(record.category_tie_reason||'未说明')}</div><div><strong>分类置信度</strong>${Math.round(Number(record.confidence||0)*100)}%</div><div><strong>图片状态</strong>${escapeHtml(imageLabel(image))}</div><div><strong>图片来源</strong>${escapeHtml(image.source||'unknown')}</div>`;$('#danger-zone').hidden=!canDelete(record);lockBackground();$('#detail').showModal();$('#detail-media').scrollTop=0;$('#detail-content').scrollTop=0;$('#close').focus({preventScroll:true});if(focusImage)requestAnimationFrame(()=>{$('#detail-media').scrollTop=$('#image-editor').offsetTop-20;$('#image-editor').focus({preventScroll:true})})}
    function closeDetail(){if($('#delete-confirm').open)$('#delete-confirm').close();if($('#detail').open)$('#detail').close()}
    document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{state.mode=button.dataset.mode;state.category='all';state.query='';$('#search').value='';document.querySelectorAll('[data-mode]').forEach(tab=>tab.classList.toggle('active',tab.dataset.mode===state.mode));render()}));
    $('#search').addEventListener('input',event=>{state.query=event.target.value.trim().toLowerCase();render()});
    $('#close').addEventListener('click',closeDetail);
    $('#detail').addEventListener('cancel',event=>{event.preventDefault();closeDetail()});
    $('#detail').addEventListener('close',()=>{unlockBackground();activeRecord=null;if(lastFocus&&typeof lastFocus.focus==='function')lastFocus.focus({preventScroll:true})});
    $('#refresh').addEventListener('click',async()=>{const button=$('#refresh'),status=$('#status');button.disabled=true;status.textContent='正在重新扫描并整理目录…';try{const response=await fetch('/api/refresh',{method:'POST'});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.details||payload.error||'刷新失败');location.reload()}catch(error){status.textContent=`无法刷新：${error.message||'请通过本地服务打开页面'}`;button.disabled=false}});
    $('#image-file').addEventListener('change',event=>{const file=event.target.files?.[0]||null;selectedImage=file;if(!file){$('#image-save').disabled=true;$('#image-editor-status').textContent='';return}if(file.size>2*1024*1024){selectedImage=null;$('#image-save').disabled=true;$('#image-editor-status').textContent='图片不能超过 2 MiB。';return}$('#image-save').disabled=false;$('#image-editor-status').textContent=`已选择：${file.name}`});
    $('#image-save').addEventListener('click',async()=>{if(!activeRecord||!selectedImage)return;const button=$('#image-save'),status=$('#image-editor-status'),item=primarySkill(activeRecord);button.disabled=true;status.textContent='正在保存并刷新目录…';try{const response=await fetch('/api/image',{method:'POST',headers:{'Content-Type':selectedImage.type||'application/octet-stream','X-Catalog-Skill-Name':item.name,'X-Catalog-Relative-Path':item.relative_path},body:selectedImage});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.error||'保存失败');location.reload()}catch(error){status.textContent=`无法保存：${error.message||'请通过本地服务打开页面'}`;button.disabled=false}});
    $('#image-remove').addEventListener('click',async()=>{if(!activeRecord)return;const button=$('#image-remove'),status=$('#image-editor-status'),item=primarySkill(activeRecord);button.disabled=true;status.textContent='正在恢复 GitHub 自动图…';try{const response=await fetch('/api/image',{method:'DELETE',headers:{'X-Catalog-Relative-Path':item.relative_path}});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.error||'恢复失败');location.reload()}catch(error){status.textContent=`无法恢复：${error.message||'请通过本地服务打开页面'}`;button.disabled=false}});
    $('#delete-open').addEventListener('click',()=>{if(!activeRecord||!canDelete(activeRecord))return;const name=primarySkill(activeRecord).name;$('#delete-name').textContent=name;$('#delete-input').value='';$('#delete-status').textContent='';$('#delete-submit').disabled=true;$('#delete-confirm').showModal();$('#delete-input').focus()});
    $('#delete-input').addEventListener('input',event=>{$('#delete-submit').disabled=!activeRecord||event.target.value!==primarySkill(activeRecord).name});
    $('#delete-cancel').addEventListener('click',()=>$('#delete-confirm').close());
    $('#delete-confirm').addEventListener('cancel',event=>{event.preventDefault();$('#delete-confirm').close()});
    $('#delete-form').addEventListener('submit',async event=>{event.preventDefault();if(!activeRecord||!canDelete(activeRecord))return;const item=primarySkill(activeRecord),confirmation=$('#delete-input').value,button=$('#delete-submit');if(confirmation!==item.name)return;button.disabled=true;$('#delete-status').textContent='正在删除并重新扫描目录…';try{const response=await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:item.id,name:item.name,relative_path:item.relative_path,confirmation})});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.error||payload.details||'删除失败');location.reload()}catch(error){$('#delete-status').textContent=`无法删除：${error.message||'服务拒绝了请求'}`;button.disabled=false}});
    render();
  </script>
</body>
</html>'''


def render_catalog_html(catalog: Dict[str, Any]) -> str:
    data = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__CATALOG__", data)
