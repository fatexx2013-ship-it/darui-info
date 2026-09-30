/* 大瑞的信息网 · 公共脚本
   同时兼容 http(s) 托管与本地 file:// 直接打开：
   数据一律通过 <script> 注入 window.WIS_DATA / window.WIS_ARCHIVE_INDEX / window.WIS_SNAPSHOT，
   不依赖 fetch，避免 file:// 的跨域限制。 */
(function () {
  'use strict';

  var WIS = {};
  var credClass = { '一手官方': 'cred-official', '主流媒体': 'cred-mainstream', '二手转载': 'cred-repost' };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  /* ---------- 时间 ---------- */
  function parseISO(iso) {
    if (!iso) return null;
    var d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function fmtWhen(iso) {
    var d = parseISO(iso);
    if (!d) return '';
    return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function fmtFull(iso) {
    var d = parseISO(iso);
    if (!d) return '';
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' +
      pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  /* 条目所属日期：优先发布时间，无则用首次入库时间 */
  function itemDate(it) {
    var d = parseISO(it.published_at) || parseISO(it.first_seen);
    if (!d) return '';
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }

  /* ---------- 卡片渲染 ---------- */
  function itemCard(it, opts) {
    opts = opts || {};
    var cred = it.credibility || '二手转载';
    var credCls = credClass[cred] || 'cred-repost';
    var date = itemDate(it);
    var when = it.published_at ? fmtWhen(it.published_at) : (fmtFull(it.first_seen) + ' 入库');
    var url = it.source_url || '';
    var titleHtml = url
      ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(it.title) + '</a>'
      : esc(it.title);
    var blk = opts.showBlock && it.blockName ? '<span class="tag blk">' + esc(it.blockName) + '</span>' : '';
    var dateTag = opts.showDate && date ? '<span class="tag">' + esc(date) + '</span>' : '';
    var sum = it.summary ? '<p class="sum">' + esc(it.summary) + '</p>' : '';
    var srcLink = url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(it.source_name || '原始链接') + '</a>' : esc(it.source_name || '');
    return '<article class="card item-card" data-id="' + esc(it.id) + '" data-block="' + esc(it.block || '') +
      '" data-date="' + esc(date) + '">' +
      '<h3>' + titleHtml + '</h3>' + sum +
      '<div class="src">' +
      '<span class="tag ' + credCls + '">' + esc(cred) + '</span>' + blk + dateTag +
      '<span class="src-out">' + srcLink + '</span>' +
      '<span class="when">' + esc(when) + '</span>' +
      '</div></article>';
  }

  function cardsHTML(items, opts) {
    if (!items.length) return '<div class="empty">没有符合条件的条目</div>';
    return '<div class="grid">' + items.map(function (it) { return itemCard(it, opts); }).join('') + '</div>';
  }

  /* ---------- 数据加载 ---------- */
  var scripted = {};
  function loadScript(src, key) {
    if (scripted[src]) return scripted[src];
    scripted[src] = new Promise(function (resolve, reject) {
      if (key && window[key]) { resolve(window[key]); return; }
      var s = document.createElement('script');
      s.src = src;
      s.async = false;
      s.onload = function () { resolve(key ? window[key] : true); };
      s.onerror = function () {
        delete scripted[src];              // 失败不缓存，允许重试
        reject(new Error('无法加载 ' + src));
      };
      document.head.appendChild(s);
    });
    return scripted[src];
  }

  var snapCache = {};
  function loadSnapshot(date) {
    if (window.WIS_SNAPSHOT && window.WIS_SNAPSHOT[date]) {
      return Promise.resolve(window.WIS_SNAPSHOT[date]);
    }
    if (snapCache[date]) return snapCache[date];
    snapCache[date] = loadScript('archive/' + date + '.js', null).then(function () {
      var snap = window.WIS_SNAPSHOT && window.WIS_SNAPSHOT[date];
      if (!snap) throw new Error('快照 ' + date + ' 无数据');
      return snap;
    }).catch(function (err) {
      delete snapCache[date];              // 失败不缓存，允许重试
      throw err;
    });
    return snapCache[date];
  }

  function latestItems(meta) {
    var data = window.WIS_DATA || { meta: {}, blocks: [] };
    var names = {};
    (data.meta.blocks || []).forEach(function (b) { names[b.key] = b.name; });
    var out = [];
    (data.blocks || []).forEach(function (b) {
      (b.items || []).forEach(function (it) {
        var copy = {};
        for (var k in it) if (Object.prototype.hasOwnProperty.call(it, k)) copy[k] = it[k];
        copy.blockName = b.name || names[it.block] || '';
        out.push(copy);
      });
    });
    return out;
  }

  function snapshotItems(snap) {
    return (snap.items || []).map(function (it) {
      var copy = {};
      for (var k in it) if (Object.prototype.hasOwnProperty.call(it, k)) copy[k] = it[k];
      copy.blockName = (BLOCK_NAMES[it.block] || it.block || '');
      if (!copy.date) copy.date = snap.date;
      return copy;
    });
  }

  var BLOCK_NAMES = {};
  function setBlockNames(meta) {
    (meta.blocks || []).forEach(function (b) { BLOCK_NAMES[b.key] = b.name; });
  }

  /* ---------- 检索 ---------- */
  function matchItem(it, f) {
    if (f.blocks && f.blocks.length && f.blocks.indexOf(it.block) === -1) return false;
    if (f.kw) {
      var hay = ((it.title || '') + ' ' + (it.summary || '') + ' ' + (it.source_name || '')).toLowerCase();
      if (f.kw.toLowerCase().split(/\s+/).some(function (w) { return w && hay.indexOf(w) === -1; })) return false;
    }
    var d = itemDate(it) || it.date || '';
    if (f.from && d && d < f.from) return false;
    if (f.to && d && d > f.to) return false;
    return true;
  }

  function inRange(date, from, to) {
    if (from && date < from) return false;
    if (to && date > to) return false;
    return true;
  }

  WIS.esc = esc; WIS.$ = $; WIS.$$ = $$;
  WIS.fmtWhen = fmtWhen; WIS.fmtFull = fmtFull; WIS.itemDate = itemDate;
  WIS.itemCard = itemCard; WIS.cardsHTML = cardsHTML;
  WIS.loadScript = loadScript; WIS.loadSnapshot = loadSnapshot;
  WIS.latestItems = latestItems; WIS.snapshotItems = snapshotItems;
  WIS.setBlockNames = setBlockNames; WIS.blockNames = BLOCK_NAMES;
  WIS.matchItem = matchItem; WIS.inRange = inRange;
  WIS.CRED_CLASS = credClass;

  window.WIS = WIS;
})();
