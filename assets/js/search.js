// Site search. Reads search-index.json (rebuilt by tools/build.py) and lists pages and
// downloadable files that contain every word typed. No server and no outside service.
(function () {
  var params = new URLSearchParams(window.location.search);
  var q = (params.get('q') || '').trim();
  var input = document.getElementById('q');
  var status = document.getElementById('status');
  var list = document.getElementById('results');
  input.value = q;
  if (!q) { status.textContent = 'Type a word or phrase to search.'; return; }

  var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
  var sectionNames = { home: 'Home', assessment: 'Assessment', accreditation: 'Accreditation', ai: 'AI', data: 'Data & Reports', search: 'Search' };

  function count(hay, term) {
    var n = 0, i = hay.indexOf(term);
    while (i !== -1) { n++; i = hay.indexOf(term, i + term.length); }
    return n;
  }

  fetch('../search-index.json')
    .then(function (r) { return r.json(); })
    .then(function (index) {
      var hits = [];
      index.forEach(function (item) {
        if (item.section === 'search') return;
        var title = item.title.toLowerCase();
        var text = (item.text || '').toLowerCase();
        var score = 0;
        for (var k = 0; k < terms.length; k++) {
          var t = count(title, terms[k]) * 5 + count(text, terms[k]);
          if (!t) return;
          score += t;
        }
        if (item.kind === 'file') score += 2;
        hits.push({ item: item, score: score });
      });
      hits.sort(function (a, b) { return b.score - a.score; });

      status.textContent = hits.length === 0
        ? 'No results for "' + q + '". Try a shorter or different word.'
        : hits.length + (hits.length === 1 ? ' result' : ' results') + ' for "' + q + '".';

      hits.slice(0, 50).forEach(function (h) {
        var it = h.item;
        var li = document.createElement('li');
        var where = document.createElement('div');
        where.className = 'where';
        where.textContent = it.kind === 'file'
          ? 'Download · ' + sectionNames[it.section] + (it.group ? ' · ' + it.group : '')
          : 'Page · ' + (sectionNames[it.section] || '');
        var h2 = document.createElement('h2');
        var a = document.createElement('a');
        a.href = '../' + it.url;
        a.textContent = it.title;
        if (it.kind === 'file') a.setAttribute('download', '');
        h2.appendChild(a);
        var p = document.createElement('p');
        var snippet = it.text || '';
        if (it.kind === 'page') {
          var pos = snippet.toLowerCase().indexOf(terms[0]);
          var start = Math.max(0, pos - 80);
          snippet = (start > 0 ? '...' : '') + snippet.slice(start, start + 220) + '...';
        }
        p.textContent = snippet;
        li.appendChild(where); li.appendChild(h2); li.appendChild(p);
        list.appendChild(li);
      });
    })
    .catch(function () {
      status.textContent = 'Search could not load. Try again, or browse the sections from the menu above.';
    });
})();
