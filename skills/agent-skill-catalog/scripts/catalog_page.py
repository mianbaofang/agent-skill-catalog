"""Render the self-contained catalog page.

The generated page is a working local search tool, not a marketing site: it stays
information dense, uses the existing muted teal / off-white identity, and depends
only on inline CSS/SVG (no external fonts, frameworks or remote icons). Live write
actions (refresh, image replace, delete) are localhost-service capabilities and are
shown as disabled, explained states when the page is opened as a static file.
"""

from __future__ import annotations

import json
from typing import Any, Dict


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="搜索你已安装的 Agent Skills：可搜索、可查看来源与调用方式的本地 HTML 目录。">
  <title>Agent Skill Catalog</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2032%2032'%3E%3Crect%20width='32'%20height='32'%20rx='6'%20fill='%23104e4b'/%3E%3Ctext%20x='16'%20y='21'%20font-family='sans-serif'%20font-size='13'%20font-weight='700'%20fill='%23ffffff'%20text-anchor='middle'%3EAC%3C/text%3E%3C/svg%3E">
  <style>
    :root {
      font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
      color: #182326;
      background: #f1f3ef;
      --ink: #182326;
      --muted: #5c7075;
      --line: #d7ded9;
      --paper: #fff;
      --green: #104e4b;
      --green-dark: #0a3b39;
      --teal: #0f766e;
      --orange: #e55732;
      --soft: #edf2ee;
      --radius: 6px;
      --ease: cubic-bezier(.25,1,.5,1);
      --gutter: 28px;
    }
    * { box-sizing: border-box; }
    html { scrollbar-gutter: stable; scroll-padding-top: 76px; }
    body { margin: 0; background: #f1f3ef; }
    body.modal-locked { overflow: hidden; }
    button, input { font: inherit; }
    button { letter-spacing: 0; }
    a { color: inherit; }
    svg { display: block; flex: none; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    :focus-visible { outline: 3px solid var(--orange); outline-offset: 3px; }
    .shell { width: min(1480px, calc(100% - 2 * var(--gutter))); margin-inline: auto; padding: 0 0 60px; }

    /* Top bar */
    .topbar { position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 18px; min-height: 64px; padding: 6px 0; border-bottom: 1px solid rgba(24,35,38,.14); background: rgba(241,243,239,.94); backdrop-filter: blur(16px) saturate(140%); }
    .brand { display: flex; align-items: center; gap: 11px; font-size: 18px; font-weight: 760; }
    .brand-mark { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 5px; color: #fff; background: var(--green); font-size: 13px; font-weight: 780; }
    .refresh-wrap { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .status { max-width: 420px; color: var(--muted); font-size: 12px; text-align: right; }

    /* Buttons */
    .button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 38px; padding: 8px 14px; border: 1px solid #b9c8c2; border-radius: 5px; color: var(--green); background: #fff; font-weight: 700; cursor: pointer; transition: transform .16s var(--ease), box-shadow .16s var(--ease), border-color .16s var(--ease); }
    .button:hover { transform: translateY(-1px); border-color: #7da39a; box-shadow: 0 6px 14px rgba(16,78,75,.1); }
    .button:active { transform: scale(.98); }
    .button.primary { border-color: var(--green); color: #fff; background: var(--green); }
    .button.primary:hover { background: var(--green-dark); }
    .button.danger { border-color: #d5a091; color: #a93d21; background: #fff8f6; }
    .button:disabled { cursor: not-allowed; opacity: .5; transform: none; box-shadow: none; }

    /* Search-led first screen */
    .finder { padding: 30px 0 6px; }
    .finder h1 { margin: 0; max-width: 30ch; font-size: clamp(23px, 3.4vw, 33px); line-height: 1.2; letter-spacing: 0; }
    .finder-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-top: 20px; }
    .tabs { display: inline-flex; overflow: hidden; border: 1px solid #c6d0cb; border-radius: 5px; background: #fff; }
    .tabs button { display: inline-flex; align-items: center; min-height: 40px; min-width: 96px; padding: 8px 18px; border: 0; border-right: 1px solid #c6d0cb; color: #40565a; background: transparent; font-weight: 720; cursor: pointer; }
    .tabs button:last-child { border-right: 0; }
    .tabs button.active { color: #fff; background: var(--green); }
    .stat { display: flex; align-items: baseline; gap: 8px; color: var(--muted); font-size: 13px; }
    .stat strong { color: var(--green); font-size: 30px; line-height: 1; font-variant-numeric: tabular-nums; }
    .search-field { margin-top: 16px; }
    .search-label { display: block; margin-bottom: 7px; color: var(--ink); font-size: 13px; font-weight: 700; }
    .search-input-wrap { position: relative; }
    .search-input-wrap .search-icon { position: absolute; top: 50%; left: 14px; transform: translateY(-50%); color: var(--muted); pointer-events: none; }
    .search { width: 100%; min-height: 48px; padding: 10px 14px 10px 44px; border: 1px solid #c6d0cb; border-radius: 6px; color: var(--ink); background: #fff; font-size: 15px; }
    .search::placeholder { color: #7b8c90; }
    .search:focus { border-color: var(--teal); outline: 0; box-shadow: 0 0 0 4px rgba(15,118,110,.12); }
    .finder-hint { margin: 12px 0 0; max-width: 82ch; color: var(--muted); font-size: 13px; line-height: 1.6; }

    /* Compact category chips (overview + filter in one row) */
    .overview { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0 26px; }
    .category-chip { display: inline-flex; align-items: center; gap: 7px; min-height: 36px; padding: 6px 12px; border: 1px solid #c9d2ce; border-radius: 999px; color: #33484c; background: #fff; font-size: 13px; font-weight: 640; cursor: pointer; transition: border-color .16s var(--ease), background-color .16s var(--ease), color .16s var(--ease); }
    .category-chip:hover { border-color: var(--teal); color: var(--green); }
    .category-chip.active { border-color: var(--green); color: #fff; background: var(--green); }
    .category-chip .count { color: inherit; opacity: .72; font-variant-numeric: tabular-nums; }

    /* Results */
    .results-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 0 0 14px; }
    .results-head h2 { margin: 0; font-size: 20px; }
    .results-head span { color: var(--muted); font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 292px), 1fr)); gap: 16px; }
    .card { display: grid; min-width: 0; grid-template-rows: auto 1fr; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius); background: #fff; box-shadow: 0 5px 16px rgba(29,52,54,.06); transition: transform .2s var(--ease), box-shadow .2s var(--ease), border-color .2s var(--ease); }
    .card:hover { transform: translateY(-2px); border-color: #afc3bc; box-shadow: 0 12px 26px rgba(29,52,54,.12); }
    .thumb { position: relative; display: grid; aspect-ratio: 16 / 7; place-items: center; overflow: hidden; background: #e9eeeb; }
    .thumb img { width: 100%; height: 100%; object-fit: contain; transition: transform .38s var(--ease); }
    .card:hover .thumb img { transform: scale(1.02); }
    .thumb-link { display: block; color: inherit; }
    .image-badge { position: absolute; right: 8px; bottom: 8px; max-width: calc(100% - 16px); padding: 4px 7px; border-radius: 4px; color: #f0f7f5; background: rgba(8,36,36,.84); font-size: 11px; overflow-wrap: anywhere; backdrop-filter: blur(6px); }
    .card-body { display: flex; min-width: 0; flex-direction: column; padding: 14px 15px 15px; }
    .card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
    .card h3 { min-width: 0; margin: 0; font-size: 16px; line-height: 1.35; overflow-wrap: anywhere; }
    .tag { flex: none; max-width: 100%; padding: 3px 7px; border-radius: 4px; color: #3f5f5c; background: var(--soft); font-size: 11px; overflow-wrap: anywhere; }
    .card-description { display: -webkit-box; overflow: hidden; margin: 9px 0 12px; color: #53686d; font-size: 13px; line-height: 1.58; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow-wrap: anywhere; }
    .card-meta { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: auto; padding-top: 4px; color: #6a797d; font-size: 12px; }
    .card-count { overflow-wrap: anywhere; }
    .card-actions { display: flex; gap: 7px; flex: none; }
    .card-actions .button { min-height: 32px; padding: 6px 10px; font-size: 12px; }
    .empty { grid-column: 1/-1; padding: 44px 20px; border: 1px dashed #b6c5bf; border-radius: var(--radius); color: var(--muted); background: #fff; text-align: center; }

    /* Detail dialog */
    dialog { padding: 0; border: 0; }
    dialog::backdrop { background: rgba(7,21,23,.66); backdrop-filter: blur(5px); }
    #detail { width: min(1200px, calc(100vw - 2 * var(--gutter))); max-width: none; max-height: none; overflow: hidden; border-radius: 8px; background: #fff; box-shadow: 0 30px 90px rgba(4,18,20,.42); }
    .detail-shell { position: relative; display: grid; height: min(820px, calc(100vh - 2 * var(--gutter))); grid-template-columns: minmax(0, 400px) minmax(0, 1fr); overflow: hidden; }
    .detail-media, .detail-content { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
    .detail-media { padding: 20px; border-right: 1px solid var(--line); background: #e9eeeb; }
    .detail-content { padding: 28px 38px 36px; background: #fff; }
    .close { position: absolute; z-index: 5; top: 12px; right: 12px; display: grid; width: 38px; height: 38px; place-items: center; padding: 0; border: 1px solid #cdd6d2; border-radius: 5px; color: #476064; background: rgba(255,255,255,.94); cursor: pointer; box-shadow: 0 3px 10px rgba(18,41,42,.08); }
    .close:hover { color: var(--green); background: #fff; }
    .gallery { display: grid; gap: 14px; }
    .gallery figure { margin: 0; overflow: hidden; border: 1px solid #cfd8d3; border-radius: 6px; background: #fff; }
    .gallery a, .gallery div { display: grid; min-height: 200px; place-items: center; background: #f8faf8; }
    .gallery img { display: block; width: 100%; max-height: 460px; object-fit: contain; }
    .gallery figcaption { display: flex; justify-content: space-between; gap: 10px; padding: 8px 10px; border-top: 1px solid #dbe2de; color: #617277; font-size: 11px; }
    .gallery figcaption span { min-width: 0; overflow-wrap: anywhere; }
    .media-tools { margin-top: 16px; padding: 14px; border: 1px solid #cbd6d1; border-radius: 6px; background: rgba(255,255,255,.86); }
    .media-tools h3 { margin: 0 0 6px; font-size: 14px; }
    .media-tools p { margin: 0 0 12px; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .media-tool-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .file-button { position: relative; overflow: hidden; }
    .file-button input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .image-status { display: block; min-height: 18px; margin-top: 8px; color: var(--muted); font-size: 11px; }
    .detail-heading { padding-right: 46px; }
    .detail-heading h2 { margin: 8px 0 12px; font-size: clamp(21px, 2.4vw, 27px); line-height: 1.25; overflow-wrap: anywhere; }
    .detail-summary { margin: 0; color: #50666b; font-size: 14px; line-height: 1.7; }
    .section-label { margin: 24px 0 8px; color: var(--green); font-size: 12px; font-weight: 800; }
    .github { display: inline-block; color: #08717a; font-weight: 700; overflow-wrap: anywhere; }
    .code { padding: 12px 14px; border-left: 3px solid var(--orange); color: #263f42; background: #edf2ee; font-size: 13px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
    .subskills { border-top: 1px solid var(--line); }
    .subskill { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 7px 12px; padding: 13px 0; border-bottom: 1px solid var(--line); }
    .subskill strong { min-width: 0; overflow-wrap: anywhere; }
    .subskill p { grid-column: 1/-1; margin: 0; color: #627579; font-size: 12px; line-height: 1.58; overflow-wrap: anywhere; }
    .detail-evidence { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr)); gap: 8px; }
    .detail-evidence div { padding: 10px 11px; background: #f2f5f2; color: #5c7075; font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }
    .detail-evidence strong { display: block; margin-bottom: 2px; color: var(--green); font-size: 11px; }
    .danger-zone { margin-top: 26px; padding-top: 18px; border-top: 1px solid #e2bcb1; }
    .danger-zone p { margin: 0 0 10px; color: #7d625c; font-size: 12px; line-height: 1.55; }

    /* Delete confirm dialog */
    #delete-confirm { width: min(470px, calc(100vw - 2 * var(--gutter))); border-radius: 7px; background: #fff; box-shadow: 0 22px 70px rgba(4,18,20,.36); }
    .confirm-body { padding: 24px; }
    .confirm-body h2 { margin: 0 0 9px; font-size: 21px; }
    .confirm-body p { margin: 0 0 14px; color: #5d6e72; line-height: 1.6; }
    .confirm-body strong { overflow-wrap: anywhere; }
    .confirm-body label { display: block; color: #344a4d; font-size: 13px; font-weight: 700; }
    .confirm-body input { width: 100%; margin-top: 7px; padding: 10px 11px; border: 1px solid #c5cfcb; border-radius: 5px; }
    .confirm-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
    .confirm-status { min-height: 18px; margin-top: 9px; color: #a43e24; font-size: 12px; }

    /* Responsive: tablet */
    @media (max-width: 900px) {
      :root { --gutter: 20px; }
      .detail-content { padding: 24px 26px 30px; }
    }
    /* Responsive: detail stacks to one column, full-screen */
    @media (max-width: 820px) {
      #detail { width: 100vw; height: 100dvh; border-radius: 0; }
      .detail-shell { display: flex; flex-direction: column; height: 100dvh; }
      .detail-media { flex: 0 0 auto; max-height: 44dvh; border-right: 0; border-bottom: 1px solid var(--line); }
      .detail-content { flex: 1 1 auto; }
      .close { top: 10px; right: 10px; }
      .status { max-width: none; }
    }
    /* Responsive: phone */
    @media (max-width: 600px) {
      :root { --gutter: 16px; }
      .shell { padding-bottom: 44px; }
      .topbar { min-height: 58px; }
      .brand { font-size: 16px; }
      .refresh-wrap { width: 100%; justify-content: space-between; }
      .status { text-align: left; }
      .finder { padding-top: 22px; }
      .finder-row { align-items: stretch; }
      .stat strong { font-size: 26px; }
      .tabs { width: 100%; }
      .tabs button { flex: 1 1 0; min-width: 0; min-height: 44px; }
      .overview { gap: 7px; }
      .button { min-height: 44px; }
      .category-chip { min-height: 44px; }
      .card-actions .button { min-height: 44px; }
      .close { width: 44px; height: 44px; }
    }
    @media (max-width: 360px) {
      .card-actions { width: 100%; }
      .card-actions .button { flex: 1 1 0; }
      .card-meta { flex-wrap: wrap; }
    }

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

    <section class="finder">
      <h1>按用途找到 Skill，打开就能看清它怎么用。</h1>
      <div class="finder-row">
        <nav class="tabs" aria-label="目录视图"><button class="mode active" data-mode="skills" type="button">技能</button><button class="mode" data-mode="plugins" type="button">插件</button></nav>
        <div class="stat"><strong id="total"></strong><span id="stat-label"></span></div>
      </div>
      <div class="search-field"><label class="search-label" for="search">搜索技能与插件</label><div class="search-input-wrap"><svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input class="search" id="search" type="search" placeholder="搜索名称、用途、GitHub 或相对路径" autocomplete="off" spellcheck="false"></div></div>
      <p class="finder-hint">主 Skill 会合并显示，插件单独归档。每一项都保留功能说明、调用方式、来源位置和可核对的图片来源。</p>
    </section>

    <section class="overview" id="overview" aria-label="分类筛选"></section>

    <section>
      <div class="results-head"><h2 id="result-title"></h2><span id="count"></span></div>
      <div class="grid" id="list"></div>
    </section>
  </main>

  <dialog id="detail" aria-labelledby="detail-name">
    <article class="detail-shell">
      <button class="close" id="close" type="button" title="关闭详情" aria-label="关闭详情"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
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
    // Live write endpoints (refresh / image / delete) are capabilities of the local
    // catalog service. They are offered only after a bounded same-origin health
    // check against a loopback http origin confirms a real catalog service. A static
    // file (file://), a public host (https), or a plain static server on localhost
    // (health check absent / not JSON) keeps every write control disabled and
    // explained, so the page never exposes misleading server actions.
    const LOCAL_ORIGIN=location.protocol==='http:'&&['localhost','127.0.0.1','[::1]','::1'].includes(location.hostname);
    let SERVER_MODE=false;
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
    function card(record){const skillCount=(record.skill_ids||[]).length;const countText=state.mode==='plugins'?`携带 ${skillCount} 个技能`:(skillCount>1?`包含 ${skillCount} 个子技能`:'独立技能');const imageAction=SERVER_MODE?`<button class="button" type="button" data-image-record="${escapeHtml(record.id)}">换图</button>`:'';return `<article class="card">${preview(record)}<div class="card-body"><div class="card-top"><h3>${escapeHtml(record.name)}</h3><span class="tag">${escapeHtml(labels[record.category]||record.category)}</span></div><p class="card-description">${escapeHtml(record.description)}</p><div class="card-meta"><span class="card-count">${countText}</span><div class="card-actions"><button class="button" type="button" data-record="${escapeHtml(record.id)}">查看详情</button>${imageAction}</div></div></div></article>`}
    const categoryIcons={
      visual:'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="M4 17l4.5-5 3.5 4 3-3 5 5"/>',
      video:'<rect x="3" y="5" width="12" height="14" rx="2"/><path d="M15 10l6-3v10l-6-3z"/>',
      audio:'<path d="M4 14v-4M8 17V7M12 19V5M16 16V8M20 13v-2"/>',
      content:'<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h6"/>',
      internet_search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
      learning:'<path d="M4 5a2 2 0 0 1 2-2h5v18H6a2 2 0 0 1-2-2z"/><path d="M20 5a2 2 0 0 0-2-2h-5v18h5a2 2 0 0 0 2-2z"/>',
      securities:'<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
      data:'<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 17v-5M13 17V8M18 17v-8"/>',
      development:'<path d="M9 8l-4 4 4 4"/><path d="M15 8l4 4-4 4"/>',
      productivity:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 12l3 3 5-6"/>',
      system_ops:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3"/><path d="M12 15h5"/>',
      specialist:'<path d="M12 3l2.6 5.6 6 .8-4.4 4.2 1.1 6L12 16.8 6.7 19.6l1.1-6L3.4 9.4l6-.8z"/>',
      other:'<circle cx="6" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18" cy="12" r="1.4"/>'
    };
    const iconSvg=(id,size=16)=>`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${categoryIcons[id]||categoryIcons.other}</svg>`;
    function renderOverview(){const counts=records().reduce((out,item)=>(out[item.category]=(out[item.category]||0)+1,out),{});const unit=state.mode==='plugins'?'插件':'技能';const entries=[['all','全部',records().length],...Object.keys(labels).filter(id=>counts[id]).map(id=>[id,labels[id],counts[id]])];$('#overview').innerHTML=entries.map(([id,label,count])=>`<button class="category-chip ${state.category===id?'active':''}" data-category="${escapeHtml(id)}" type="button">${id==='all'?'':iconSvg(id)}${escapeHtml(label)}<span class="count">${count} ${unit}</span></button>`).join('')}
    function render(){const items=filtered();$('#total').textContent=records().length;$('#stat-label').textContent=state.mode==='plugins'?'已整理插件':'已整理主技能';$('#result-title').textContent=state.category==='all'?(state.mode==='plugins'?'全部插件':'全部技能'):(labels[state.category]||state.category);$('#count').textContent=`${items.length} 项结果 · ${data.generated_at||'尚未生成'}`;renderOverview();$('#list').innerHTML=items.length?items.map(card).join(''):'<div class="empty">没有找到匹配的 Skill 或插件。</div>';document.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{state.category=button.dataset.category;render()}));document.querySelectorAll('[data-record]').forEach(button=>button.addEventListener('click',()=>openRecord(button.dataset.record)));document.querySelectorAll('[data-image-record]').forEach(button=>button.addEventListener('click',()=>openRecord(button.dataset.imageRecord,true)))}
    function lockBackground(){if(document.body.classList.contains('modal-locked'))return;lockedScrollY=window.scrollY;document.body.style.position='fixed';document.body.style.top=`-${lockedScrollY}px`;document.body.style.width='100%';document.body.classList.add('modal-locked')}
    function unlockBackground(){if(!document.body.classList.contains('modal-locked'))return;document.body.classList.remove('modal-locked');document.body.style.position='';document.body.style.top='';document.body.style.width='';const restore=()=>window.scrollTo(0,lockedScrollY);requestAnimationFrame(()=>{restore();requestAnimationFrame(restore)})}
    function uniqueGallery(record){const entries=[{name:record.name,image:record.image,github:record.github?.url},...recordSkills(record).map(item=>({name:item.name,image:item.image,github:item.github?.url}))];const seen=new Set();return entries.filter(entry=>{const value=entry.image?.value||'';if(!value||seen.has(value))return false;seen.add(value);return true})}
    function canDelete(record){if(!SERVER_MODE)return false;const skills=recordSkills(record);const item=primarySkill(record);return state.mode==='skills'&&skills.length===1&&item?.allow_delete===true&&item?.family_size===1}
    function openRecord(id,focusImage=false){const record=records().find(entry=>entry.id===id);if(!record)return;lastFocus=document.activeElement;activeRecord=record;selectedImage=null;const skills=recordSkills(record);const image=record.image||{};$('#image-file').value='';$('#image-save').disabled=true;$('#image-remove').hidden=image.status!=='curated-local';$('#image-editor-status').textContent='';const gallery=uniqueGallery(record);$('#detail-gallery').innerHTML=gallery.map((entry,index)=>`<figure>${entry.github?`<a href="${escapeHtml(entry.github)}" target="_blank" rel="noreferrer" title="打开 GitHub 仓库">`: '<div>'}<img src="${escapeHtml(entry.image.value)}" alt="${escapeHtml(entry.name)} 的项目图片">${entry.github?'</a>':'</div>'}<figcaption><span>${escapeHtml(index===0?record.name:entry.name)}</span><span>${escapeHtml(imageLabel(entry.image))}</span></figcaption></figure>`).join('');$('#detail-tag').textContent=labels[record.category]||record.category;$('#detail-name').textContent=state.mode==='plugins'?`${record.name} 插件`:record.name;$('#detail-description').textContent=record.description;$('#detail-invocation').textContent=record.invocation;$('#detail-locations').textContent=(record.locations||[]).join('\n');const github=record.github?.url;$('#github-panel').hidden=!github;if(github){$('#detail-github').href=github;$('#detail-github').textContent=github}$('#subskills-label').textContent=state.mode==='plugins'?`插件携带技能（${skills.length}）`:(skills.length>1?`包含的子技能（${skills.length}）`:'技能说明');$('#detail-subskills').innerHTML=skills.map(item=>`<article class="subskill"><strong>${escapeHtml(item.name)}</strong><span class="tag">${escapeHtml(labels[item.category]||item.category)}</span><p>${escapeHtml(item.description)}</p><p>调用：${escapeHtml(item.invocation)}</p></article>`).join('');$('#detail-evidence').innerHTML=`<div><strong>分类依据</strong>${escapeHtml(record.category_tie_reason||record.category_tie_break||'未说明')}</div><div><strong>分类置信度</strong>${Math.round(Number(record.confidence||0)*100)}%</div><div><strong>图片状态</strong>${escapeHtml(imageLabel(image))}</div><div><strong>图片来源</strong>${escapeHtml(image.source||'unknown')}</div>`;$('#danger-zone').hidden=!canDelete(record);lockBackground();$('#detail').showModal();$('#detail-media').scrollTop=0;$('#detail-content').scrollTop=0;$('#close').focus({preventScroll:true});if(focusImage)requestAnimationFrame(()=>{$('#detail-media').scrollTop=$('#image-editor').offsetTop-20;$('#image-editor').focus({preventScroll:true})})}
    function closeDetail(){if($('#delete-confirm').open)$('#delete-confirm').close();if($('#detail').open)$('#detail').close()}
    function applyStaticMode(){const refresh=$('#refresh');refresh.disabled=true;refresh.title='静态目录：刷新需通过本地服务 (serve_catalog) 打开';$('#status').textContent='静态目录：刷新、更换预览图与删除需通过本地服务打开。';$('#image-editor').hidden=true}
    function applyServerMode(){if(SERVER_MODE)return;SERVER_MODE=true;const refresh=$('#refresh');refresh.disabled=false;refresh.title='';$('#status').textContent='';$('#image-editor').hidden=false;render()}
    async function probeServerMode(){if(!LOCAL_ORIGIN||SERVER_MODE)return;const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),2500);try{const response=await fetch('/api/health',{method:'GET',signal:controller.signal,headers:{'Accept':'application/json'}});if(!response.ok)return;const contentType=response.headers.get('Content-Type')||'';if(!contentType.includes('application/json'))return;const payload=await response.json().catch(()=>null);if(payload&&payload.ok===true&&payload.catalog===true)applyServerMode()}catch(error){/* static origin or unreachable service: keep write controls disabled */}finally{clearTimeout(timer)}}
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
    applyStaticMode();
    render();
    probeServerMode();
  </script>
</body>
</html>'''


def render_catalog_html(catalog: Dict[str, Any]) -> str:
    data = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__CATALOG__", data)
