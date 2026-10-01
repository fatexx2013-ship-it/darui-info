/* 首页：顶部板块标签切换 + 板块内检索（最新一期 / 含历史归档） */
(function () {
  'use strict';
  var WIS = window.WIS;
  var data = window.WIS_DATA || { meta: {}, blocks: [] };
  var index = window.WIS_ARCHIVE_INDEX || { days: [] };
  var meta = data.meta || {};

  WIS.setBlockNames(meta);

  /* 板块清单（顺序取 meta.blocks，即配置里的展示顺序；首个板块为默认落地板块） */
  var metaBlocks = meta.blocks || [];
  var byKey = {};
  (data.blocks || []).forEach(function (b) { byKey[b.key] = b; });
  var blocks = metaBlocks.map(function (b) {
    var d = byKey[b.key] || {};
    return { key: b.key, name: b.name, desc: b.desc || d.desc || '', count: d.count || (d.items || []).length || 0 };
  });

  var current = blocks.length ? blocks[0].key : '';
  var scope = 'latest';

  /* ---------------- 顶部信息 ---------------- */
  function renderHero() {
    var host = WIS.$('#heroMeta');
    var archived = (index.days || []).length;
    var chips = [
      '数据时间 ' + (WIS.fmtFull(meta.generatedAt) || '—'),
      '今日轮次 ' + ((meta.rounds || []).join(' / ') || '—'),
      '最新一期 ' + (meta.total || 0) + ' 条 · ' + blocks.length + ' 板块',
      '归档 ' + archived + ' 天 / ' + (index.total_items || 0) + ' 条'
    ];
    host.innerHTML = chips.map(function (t) { return '<span class="chip">' + WIS.esc(t) + '</span>'; }).join('') +
      '<span class="chip live-chip ' + (meta.generatedAt ? 'on' : 'off') + '">' +
      (meta.generatedAt ? '已更新' : '暂无数据') + '</span>';
    WIS.$('#footTiny').textContent = '生成时间 ' + (WIS.fmtFull(meta.generatedAt) || '—') +
      ' · 归档 ' + (index.total_days || 0) + ' 天 / ' + (index.total_items || 0) + ' 条';
  }

  /* ---------------- 标签栏 ---------------- */
  function renderTabs() {
    var host = WIS.$('#boardTabs');
    host.innerHTML = WIS.tabsHTML(blocks, current, { leadKey: blocks.length ? blocks[0].key : '' });
    var active = WIS.$('.tab.active', host);
    if (active && active.offsetLeft > host.clientWidth - 90) {
      host.scrollLeft = Math.max(0, active.offsetLeft - 60);
    } else {
      host.scrollLeft = 0;
    }
  }

  function blockOf(key) { return byKey[key] || {}; }

  /* ---------------- 板块内容 ---------------- */
  function renderBoard() {
    var host = WIS.$('#boardView');
    var b = blockOf(current);
    var name = (blocks.filter(function (x) { return x.key === current; })[0] || {}).name || current;
    var items = (b.items || []).map(function (it) {
      var c = {}; for (var k in it) if (Object.prototype.hasOwnProperty.call(it, k)) c[k] = it[k];
      c.blockName = name; return c;
    });
    if (!blocks.length) {
      host.innerHTML = '<div class="board-empty">暂无数据：请先运行 <code>python3 scripts/update_data.py</code> 生成站点数据。</div>';
      return;
    }
    host.innerHTML = '<section class="board" id="board-' + WIS.esc(current) + '">' +
      '<div class="board-head">' +
      '<h2>' + WIS.esc(name) + '<span class="cnt">' + items.length + ' 条</span></h2>' +
      '<p class="board-sub">' + WIS.esc(b.desc || '') + '</p>' +
      '</div>' +
      (items.length ? WIS.cardsHTML(items, { showBlock: false, showDate: false })
                    : '<div class="empty">该板块本期暂无条目，可切换其他板块或稍后重试。</div>') +
      '</section>';
  }

  function updateScopeNote() {
    var name = (blocks.filter(function (x) { return x.key === current; })[0] || {}).name || '—';
    WIS.$('#scopeNote').innerHTML = '检索范围：<b>' + WIS.esc(name) + '</b> · ' +
      (scope === 'latest' ? '仅最新一期' : '含历史归档');
  }

  /* ---------------- 检索 ---------------- */
  var scopeSeg = WIS.$('#scopeSeg');

  scopeSeg.addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-scope]');
    if (!btn) return;
    scope = btn.getAttribute('data-scope');
    WIS.$$('button', scopeSeg).forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
    updateScopeNote();
  });

  WIS.$('#boardTabs').addEventListener('click', function (e) {
    var tab = e.target.closest('.tab');
    if (!tab) return;
    current = tab.getAttribute('data-block');
    WIS.$$('.tab', this).forEach(function (t) { t.classList.toggle('active', t === tab); });
    if (tab.offsetLeft > this.clientWidth - 90) this.scrollLeft = Math.max(0, tab.offsetLeft - 60);
    hideResults();
    status('');
    renderBoard();
    updateScopeNote();
  });

  function readFilters() {
    return {
      kw: (WIS.$('#kw').value || '').trim(),
      blocks: current ? [current] : [],
      from: WIS.$('#from').value || '',
      to: WIS.$('#to').value || ''
    };
  }

  function status(text, isErr) {
    var el = WIS.$('#searchHint');
    el.innerHTML = text ? '<span class="' + (isErr ? 'err' : '') + '">' + WIS.esc(text) + '</span>' : '';
  }

  function hideResults() {
    WIS.$('#results').classList.add('hidden');
    WIS.$('#boardView').classList.remove('hidden');
  }

  function showResults(items, note) {
    var name = (blocks.filter(function (x) { return x.key === current; })[0] || {}).name || '';
    WIS.$('#resCount').textContent = items.length + ' 条 · 板块 ' + name + (note ? ' · ' + note : '');
    WIS.$('#resBody').innerHTML = WIS.cardsHTML(items, { showBlock: false, showDate: true });
    WIS.$('#boardView').classList.add('hidden');
    WIS.$('#results').classList.remove('hidden');
    WIS.$('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function collectArchive(f) {
    var days = (index.days || []).filter(function (d) { return WIS.inRange(d.date, f.from, f.to); });
    if (!days.length) return Promise.resolve({ items: [], days: 0 });
    var all = [];
    var seq = Promise.resolve();
    days.forEach(function (d, i) {
      seq = seq.then(function () {
        status('正在载入归档 ' + (i + 1) + '/' + days.length + ' · ' + d.date + ' …');
        return WIS.loadSnapshot(d.date).then(function (snap) {
          all = all.concat(WIS.snapshotItems(snap));
        }).catch(function (err) {
          status('归档 ' + d.date + ' 载入失败，已跳过（' + err.message + '）', true);
        });
      });
    });
    return seq.then(function () { return { items: all, days: days.length }; });
  }

  function doSearch() {
    var f = readFilters();
    if (!f.kw && !f.from && !f.to) {
      status('请在当前板块内输入关键词，或展开「日期区间」后再检索', true);
      return;
    }
    if (scope === 'latest') {
      var items = WIS.latestItems(meta).filter(function (it) { return WIS.matchItem(it, f); });
      status('');
      showResults(items, '最新一期 ' + (meta.date || '') + ' · ' + (meta.rounds || []).join('/'));
      return;
    }
    var btn = WIS.$('#btnSearch');
    btn.disabled = true;
    collectArchive(f).then(function (res) {
      var items = res.items.filter(function (it) { return WIS.matchItem(it, f); });
      status('');
      if (!res.days) { status('所选日期范围内没有归档数据', true); }
      showResults(items, '归档 ' + res.days + ' 天');
    }).catch(function (err) {
      status('归档载入失败：' + err.message, true);
    }).then(function () { btn.disabled = false; });
  }

  WIS.$('#btnSearch').addEventListener('click', doSearch);
  WIS.$('#kw').addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
  WIS.$('#btnBack').addEventListener('click', function () { hideResults(); status(''); WIS.$('#boardTabs').scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  WIS.$('#btnReset').addEventListener('click', function () {
    WIS.$('#kw').value = '';
    WIS.$('#from').value = '';
    WIS.$('#to').value = '';
    hideResults();
    status('');
    renderBoard();
  });

  renderHero();
  renderTabs();
  renderBoard();
  updateScopeNote();
})();
