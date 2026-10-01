/* 归档页：板块标签切换 + 日期浏览 + 跨归档检索 */
(function () {
  'use strict';
  var WIS = window.WIS;
  var data = window.WIS_DATA || { meta: {}, blocks: [] };
  var index = window.WIS_ARCHIVE_INDEX || { days: [] };
  var days = index.days || [];
  var currentDate = days.length ? days[0].date : '';
  var loaded = {};

  WIS.setBlockNames(data.meta || {});

  var metaBlocks = (data.meta || {}).blocks || [];
  var blocks = metaBlocks.map(function (b) { return { key: b.key, name: b.name }; });
  var blockName = {};
  blocks.forEach(function (b) { blockName[b.key] = b.name; });
  var current = '';   // '' = 全部板块

  function status(text, isErr) {
    var el = WIS.$('#searchHint');
    el.innerHTML = text ? '<span class="' + (isErr ? 'err' : '') + '">' + WIS.esc(text) + '</span>' : '';
  }

  function updateScopeNote() {
    WIS.$('#scopeNote').innerHTML = '检索范围：<b>' + WIS.esc(current ? blockName[current] : '全部板块') + '</b>';
  }

  /* ---------------- 板块标签 ---------------- */
  function renderTabs() {
    var list = [{ key: '', name: '全部', count: index.total_items || 0 }].concat(blocks.map(function (b) {
      return { key: b.key, name: b.name, count: null };
    }));
    WIS.$('#boardTabs').innerHTML = WIS.tabsHTML(list, current, {});
  }

  /* ---------------- 日期列表 ---------------- */
  function renderDayList() {
    var host = WIS.$('#dayList');
    if (!days.length) {
      host.innerHTML = '<div class="skeleton">暂无归档</div>';
      return;
    }
    WIS.$('#arcStat').textContent = index.total_days + ' 天 · ' + index.total_items + ' 条 · 更新 ' +
      (WIS.fmtFull(index.updated_at) || '—');
    host.innerHTML = days.map(function (d) {
      var rounds = (d.rounds || []).join(' / ');
      return '<button class="day-btn' + (d.date === currentDate ? ' active' : '') + '" data-date="' + WIS.esc(d.date) + '">' +
        '<span>' + WIS.esc(d.date) + '</span>' +
        '<span class="d-count">' + (d.total || 0) + ' 条</span></button>';
    }).join('');
  }

  /* ---------------- 单日视图（按所选板块过滤） ---------------- */
  function renderDay(date) {
    var view = WIS.$('#dayView');
    view.innerHTML = '<div class="skeleton">正在载入 ' + WIS.esc(date) + ' …</div>';
    WIS.loadSnapshot(date).then(function (snap) {
      loaded[date] = snap;
      var byBlock = {};
      (snap.items || []).forEach(function (it) {
        var k = it.block || 'other';
        (byBlock[k] = byBlock[k] || []).push(it);
      });
      var order = blocks.map(function (b) { return b.key; });
      Object.keys(byBlock).forEach(function (k) { if (order.indexOf(k) === -1) order.push(k); });

      var body = order.filter(function (k) {
        if (!byBlock[k]) return false;
        return !current || current === k;
      }).map(function (k) {
        var items = byBlock[k].map(function (it) {
          var c = {}; for (var q in it) if (Object.prototype.hasOwnProperty.call(it, q)) c[q] = it[q];
          c.blockName = WIS.blockNames[k] || k;
          return c;
        });
        return '<section class="block-sec" data-block-sec="' + WIS.esc(k) + '">' +
          '<h3>' + WIS.esc(WIS.blockNames[k] || k) + '<span class="cnt">' + items.length + ' 条</span></h3>' +
          WIS.cardsHTML(items, { showBlock: false, showDate: false }) +
          '</section>';
      }).join('');

      view.innerHTML = '<div class="arc-title">' +
        '<h2>' + WIS.esc(date) + '</h2>' +
        '<span class="cnt">' + (snap.total || (snap.items || []).length) + ' 条</span>' +
        '<span class="rounds">' + (snap.rounds || []).map(function (r) {
          return '<span class="round">' + WIS.esc(r) + '</span>';
        }).join('') + '</span>' +
        '<span class="hint" style="margin:0">更新 ' + WIS.esc(WIS.fmtFull(snap.updated_at) || '—') + '</span>' +
        '</div>' + (body || '<div class="empty">该板块当日无条目</div>');
    }).catch(function (err) {
      view.innerHTML = '<div class="empty err">载入失败：' + WIS.esc(err.message) + '</div>';
    });
  }

  /* ---------------- 检索 ---------------- */
  function readFilters() {
    var dayOnly = WIS.$('#inDayOnly').querySelector('input').checked;
    return {
      kw: (WIS.$('#kw').value || '').trim(),
      blocks: current ? [current] : [],
      from: dayOnly ? '' : (WIS.$('#from').value || ''),
      to: dayOnly ? '' : (WIS.$('#to').value || ''),
      dayOnly: dayOnly
    };
  }

  function doSearch() {
    var f = readFilters();
    if (!f.kw && !f.from && !f.to) {
      status('请输入关键词，或取消「仅检索当前选中日期」后指定日期区间', true);
      return;
    }
    var targets = f.dayOnly
      ? days.filter(function (d) { return d.date === currentDate; })
      : days.filter(function (d) { return WIS.inRange(d.date, f.from, f.to); });

    if (!targets.length) {
      status('没有匹配的归档日期', true);
      return;
    }

    var btn = WIS.$('#btnSearch');
    btn.disabled = true;
    var all = [];
    var seq = Promise.resolve();
    targets.forEach(function (d, i) {
      seq = seq.then(function () {
        status('载入归档 ' + (i + 1) + '/' + targets.length + ' · ' + d.date + ' …');
        return WIS.loadSnapshot(d.date).then(function (snap) {
          loaded[d.date] = snap;
          WIS.snapshotItems(snap).forEach(function (it) {
            it.date = snap.date;
            all.push(it);
          });
        }).catch(function (err) {
          status('归档 ' + d.date + ' 载入失败，已跳过（' + err.message + '）', true);
        });
      });
    });

    seq.then(function () {
      var items = all.filter(function (it) { return WIS.matchItem(it, f); });
      items.sort(function (a, b) { return (b.date || '') < (a.date || '') ? -1 : 1; });
      status('');
      WIS.$('#resCount').textContent = items.length + ' 条 · 范围 ' + targets.length + ' 天 · 板块 ' +
        (current ? blockName[current] : '全部');
      WIS.$('#resBody').innerHTML = WIS.cardsHTML(items, { showBlock: !current, showDate: true });
      WIS.$('#results').classList.remove('hidden');
      WIS.$('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }).catch(function (err) {
      status('检索失败：' + err.message, true);
    }).then(function () { btn.disabled = false; });
  }

  /* ---------------- 事件 ---------------- */
  WIS.$('#boardTabs').addEventListener('click', function (e) {
    var tab = e.target.closest('.tab');
    if (!tab) return;
    current = tab.getAttribute('data-block');
    WIS.$$('.tab', this).forEach(function (t) { t.classList.toggle('active', t === tab); });
    if (tab.offsetLeft > this.clientWidth - 90) this.scrollLeft = Math.max(0, tab.offsetLeft - 60);
    status('');
    updateScopeNote();
    if (currentDate) renderDay(currentDate);
  });

  WIS.$('#dayList').addEventListener('click', function (e) {
    var btn = e.target.closest('.day-btn');
    if (!btn) return;
    currentDate = btn.getAttribute('data-date');
    WIS.$$('.day-btn').forEach(function (b) { b.classList.toggle('active', b === btn); });
    WIS.$('#results').classList.add('hidden');
    status('');
    renderDay(currentDate);
  });

  WIS.$('#inDayOnly').addEventListener('change', function () {
    this.classList.toggle('on', this.querySelector('input').checked);
  });
  WIS.$('#inDayOnly').classList.add('on');

  WIS.$('#btnSearch').addEventListener('click', doSearch);
  WIS.$('#kw').addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
  WIS.$('#btnBack').addEventListener('click', function () {
    WIS.$('#results').classList.add('hidden');
    WIS.$('#dayView').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  WIS.$('#btnClear').addEventListener('click', function () {
    WIS.$('#kw').value = ''; WIS.$('#from').value = ''; WIS.$('#to').value = '';
    WIS.$('#results').classList.add('hidden');
    status('');
  });

  renderTabs();
  renderDayList();
  updateScopeNote();
  if (currentDate) renderDay(currentDate);
  else WIS.$('#dayView').innerHTML = '<div class="empty">暂无归档数据，请先运行 <code>python3 scripts/update_data.py</code>。</div>';
})();
