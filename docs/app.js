/* 首页：板块渲染 + 检索（最新一期 / 含历史归档） */
(function () {
  'use strict';
  var data = window.WIS_DATA || { meta: {}, blocks: [] };
  var index = window.WIS_ARCHIVE_INDEX || { days: [] };
  var meta = data.meta || {};
  var WIS = window.WIS;

  WIS.setBlockNames(meta);

  /* ---------------- 顶部信息 ---------------- */
  function renderHero() {
    var host = WIS.$('#heroMeta');
    var archived = (index.days || []).length;
    var chips = [
      '数据时间 ' + (WIS.fmtFull(meta.generatedAt) || '—') ,
      '今日轮次 ' + ((meta.rounds || []).join(' / ') || '—'),
      '最新一期 ' + (meta.total || 0) + ' 条',
      '归档 ' + archived + ' 天 / ' + (index.total_items || 0) + ' 条'
    ];
    host.innerHTML = chips.map(function (t) { return '<span class="chip">' + WIS.esc(t) + '</span>'; }).join('') +
      '<span class="chip live-chip ' + (meta.generatedAt ? 'on' : 'off') + '">' +
      (meta.generatedAt ? '已更新' : '暂无数据') + '</span>';
    WIS.$('#footTiny').textContent = '生成时间 ' + (WIS.fmtFull(meta.generatedAt) || '—') +
      ' · 归档 ' + (index.total_days || 0) + ' 天 / ' + (index.total_items || 0) + ' 条';
  }

  /* ---------------- 板块渲染 ---------------- */
  function renderBoards() {
    var host = WIS.$('#boards');
    var blocks = data.blocks || [];
    if (!blocks.length) {
      host.innerHTML = '<div class="empty">暂无数据：请先运行 <code>python3 scripts/update_data.py</code> 生成站点数据。</div>';
      return;
    }
    host.innerHTML = blocks.map(function (b, i) {
      return '<section class="board" id="board-' + WIS.esc(b.key) + '">' +
        '<div class="board-head">' +
        '<h2><span class="idx">' + (i < 9 ? '0' : '') + (i + 1) + '</span>' + WIS.esc(b.name) +
        '<span class="cnt">' + (b.count || (b.items || []).length) + ' 条</span></h2>' +
        '<p class="board-sub">' + WIS.esc(b.desc || '') + '</p>' +
        '</div>' +
        WIS.cardsHTML((b.items || []).map(function (it) {
          var c = {}; for (var k in it) if (Object.prototype.hasOwnProperty.call(it, k)) c[k] = it[k];
          c.blockName = b.name; return c;
        }), { showBlock: false, showDate: false }) +
        '</section>';
    }).join('');
  }

  /* ---------------- 检索 ---------------- */
  var scope = 'latest';
  var scopeSeg = WIS.$('#scopeSeg');

  scopeSeg.addEventListener('click', function (e) {
    var btn = e.target.closest('button[data-scope]');
    if (!btn) return;
    scope = btn.getAttribute('data-scope');
    WIS.$$('button', scopeSeg).forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
  });

  WIS.$$('[data-block-chk]').forEach(function (label) {
    var box = label.querySelector('input');
    box.addEventListener('change', function () {
      label.classList.toggle('on', box.checked);
    });
  });

  function readFilters() {
    return {
      kw: (WIS.$('#kw').value || '').trim(),
      blocks: WIS.$$('[data-block-chk] input:checked').map(function (i) { return i.value; }),
      from: WIS.$('#from').value || '',
      to: WIS.$('#to').value || ''
    };
  }

  function status(text, isErr) {
    var el = WIS.$('#searchHint');
    el.innerHTML = text ? '<span class="' + (isErr ? 'err' : '') + '">' + WIS.esc(text) + '</span>' : '';
  }

  function showResults(items, note) {
    WIS.$('#resCount').textContent = items.length + ' 条' + (note ? ' · ' + note : '');
    WIS.$('#resBody').innerHTML = WIS.cardsHTML(items, { showBlock: true, showDate: true });
    WIS.$('#results').classList.add('on');
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
    if (!f.kw && !f.blocks.length && !f.from && !f.to) {
      WIS.$('#results').classList.remove('on');
      status('请输入关键词或选择条件后再检索（空条件将展示全部条目，略去以免刷屏）');
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
  WIS.$('#btnReset').addEventListener('click', function () {
    WIS.$('#kw').value = '';
    WIS.$('#from').value = '';
    WIS.$('#to').value = '';
    WIS.$$('[data-block-chk] input').forEach(function (i) { i.checked = false; });
    WIS.$$('[data-block-chk]').forEach(function (l) { l.classList.remove('on'); });
    WIS.$('#results').classList.remove('on');
    status('');
  });

  renderHero();
  renderBoards();
})();
