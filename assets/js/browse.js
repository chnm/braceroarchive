// Browse enhancements for the static site:
//  1. the "page N of M" input jumps to Hugo's paginated URL on submit;
//  2. the Sort-by links re-order the current page's records client-side
//     (the server order is newest-first). Sorting is page-local by design —
//     a static site can't re-sort the full 3,209-item set server-side.
(function () {
  // Page-input jump.
  document.querySelectorAll('form.page-jump').forEach((f) => {
    f.addEventListener('submit', (e) => {
      e.preventDefault();
      const base = f.getAttribute('data-base') || '/';
      const n = parseInt(f.querySelector('input[name="page"]').value, 10);
      if (!n || n < 1) return;
      window.location.href = n === 1 ? base : base + 'page/' + n + '/';
    });
  });

  // Client-side sort of the current page.
  const list = document.getElementById('items-primary');
  if (!list) return;
  document.querySelectorAll('#sort-links-list a[data-sort]').forEach((a) => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const key = a.getAttribute('data-sort');
      const items = Array.from(list.querySelectorAll('.item.record'));
      items.sort((x, y) => {
        if (key === 'date') return (+y.dataset.id || 0) - (+x.dataset.id || 0);
        const vx = (x.dataset[key] || '').toLowerCase();
        const vy = (y.dataset[key] || '').toLowerCase();
        return vx < vy ? -1 : vx > vy ? 1 : 0;
      });
      items.forEach((it) => list.appendChild(it));
      document
        .querySelectorAll('#sort-links-list li')
        .forEach((li) => li.classList.remove('sorting', 'desc', 'asc'));
      a.closest('li').classList.add('sorting', key === 'date' ? 'desc' : 'asc');
    });
  });
})();
