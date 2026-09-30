/* 归档页：日期浏览 + 跨归档检索 */
(function () {
  'use strict';
  var WIS = window.WIS;
  var index = window.WIS_ARCHIVE_INDEX || { days: [] };
  var days = index.days || [];
  var currentDate = days.length ? days[0].date : '';
  var loaded = {};

  WIS.setBlockNames((window.WIS_DATA || {}).meta || {});

  function status(text, isErr) {
    var el = WIS.$('#searchHint');
    el.innerHTML = text ? '<span class="' + (isErr ? 'err' : '') + '">' + WIS.esc(text) + '</span>' : '';
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

  /* ---------------- 单日视图 ---------------- */
  function renderDay(date) {
    var view = WIS.$('#dayView');
    var meta = days.filter(function (d) { return d.date === date; })[0] || {};
    view.innerHTML = '<div class="skeleton">正在载入 ' + WIS.esc(date) + ' …</div>';
    WIS.loadSnapshot(date).then(function (snap) {
      loaded[date] = snap;
      var byBlock = {};
      (snap.items || []).forEach(function (it) {
        var k = it.block || 'other';
        (byBlock[k] = byBlock[k] || []).push(it);
      });
      var order = ['geopolitics', 'oddities', 'domestic', 'buzz', 'tech'];
      var rest = Object.keys(byBlock).filter(function (k) { return order.indexOf(k) === -1; });
      order = order.concat(rest);

      var body = order.filter(function (k) { return byBlock[k]; }).map(function (k) {
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
        '</div>' + (body || '<div class="empty">该日无条目</div>');
    }).catch(function (err) {
      view.innerHTML = '<div class="empty err">载入失败：' + WIS.esc(err.message) + '</div>';
    });
  }

  /* ---------------- 检索 ---------------- */
  function readFilters() {
    var groups = { geopolitics: '国际观察', oddities: '奇闻怪事', domestic: '国内热点', buzz: '网络舆论', tech: '科技前沿' };
    var blocks = WIS.$$('[data-block-chk] input:checked').map(function (i) { return i.value; });
    return {
      kw: (WIS.$('#kw').value || '').trim(),
      blocks: blocks,
      blockNames: blocks.map(function (b) { return groups[b] || b; }),
      from: WIS.$('#from').value || '',
      to: WIS.$('#to').value || '',
      dayOnly: WIS.$('#inDayOnly').querySelector('input').checked
    };
  }

  function doSearch() {
    var f = readFilters();
    if (!f.kw && !f.blocks.length && !f.from && !f.to) {
      status('请至少输入关键词或选择条件', true);
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
      WIS.$('#resCount').textContent = items.length + ' 条 · 范围 ' + targets.length + ' 天' +
        (f.blocks.length ? ' · 板块 ' + f.blockNames.join('/') : '');
      WIS.$('#resBody').innerHTML = WIS.cardsHTML(items, { showBlock: true, showDate: true });
      WIS.$('#results').classList.add('on');
      WIS.$('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }).catch(function (err) {
      status('检索失败：' + err.message, true);
    }).then(function () { btn.disabled = false; });
  }

  /* ---------------- 事件 ---------------- */
  WIS.$('#dayList').addEventListener('click', function (e) {
    var btn = e.target.closest('.day-btn');
    if (!btn) return;
    currentDate = btn.getAttribute('data-date');
    WIS.$$('.day-btn').forEach(function (b) { b.classList.toggle('active', b === btn); });
    WIS.$('#results').classList.remove('on');
    status('');
    renderDay(currentDate);
  });

  WIS.$$('[data-block-chk]').forEach(function (label) {
    var box = label.querySelector('input');
    box.addEventListener('change', function () { label.classList.toggle('on', box.checked); });
  });

  WIS.$('#inDayOnly').addEventListener('change', function () {
    this.classList.toggle('on', this.querySelector('input').checked);
  });
  WIS.$('#inDayOnly').classList.add('on');

  WIS.$('#btnSearch').addEventListener('click', doSearch);
  WIS.$('#kw').addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
  WIS.$('#btnClear').addEventListener('click', function () {
    WIS.$('#kw').value = ''; WIS.$('#from').value = ''; WIS.$('#to').value = '';
    WIS.$$('[data-block-chk] input').forEach(function (i) { i.checked = false; });
    WIS.$$('[data-block-chk]').forEach(function (l) { l.classList.remove('on'); });
    WIS.$('#results').classList.remove('on');
    status('');
  });

  renderDayList();
  if (currentDate) renderDay(currentDate);
  else WIS.$('#dayView').innerHTML = '<div class="empty">暂无归档数据，请先运行 <code>python3 scripts/update_data.py</code>。</div>';
})();
