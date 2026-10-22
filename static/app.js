// Mejoras visuales sin cambiar la lógica de Flask ni la base de datos.
document.addEventListener('DOMContentLoaded', () => {
    // Reserva la altura real de los atajos fijos para no tapar el contenido móvil.
    const shortcuts = document.querySelector('.shortcut-panel');
    if (shortcuts) {
        const updateShortcutHeight = () => {
            document.documentElement.style.setProperty(
                '--mobile-shortcuts-height', `${Math.ceil(shortcuts.getBoundingClientRect().height)}px`
            );
        };
        updateShortcutHeight();
        if ('ResizeObserver' in window) {
            new ResizeObserver(updateShortcutHeight).observe(shortcuts);
        }
        window.addEventListener('resize', updateShortcutHeight, { passive: true });
    }

    const search = document.getElementById('catalog-search');
    const status = document.getElementById('catalog-status');
    const table = document.querySelector('.available-table');
    const items = table ? Array.from(table.querySelectorAll('tr.catalog-item')) : [];
    const count = document.getElementById('catalog-count');
    const empty = document.getElementById('catalog-empty');
    // Ignora mayúsculas, tildes y espacios repetidos.
    const normalize = value => String(value || '').toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/\s+/g, ' ').trim();

    function filterCatalog() {
        if (!search || !table) return;
        const query = normalize(search.value);
        const filter = status ? status.value : 'all';
        let visibleCount = 0;
        for (const row of items) {
            const inventory = normalize(row.dataset.busqueda || row.textContent);
            const isAvailable = Number(row.dataset.disponibles) > 0 && row.dataset.prestable === '1';
            const matchesName = query.split(' ').every(word => inventory.includes(word));
            const matchesStatus = filter === 'all' ||
                (filter === 'available' ? isAvailable : !isAvailable);
            const show = matchesName && matchesStatus;
            row.hidden = !show;
            row.classList.toggle('catalog-hidden', !show);
            if (show) visibleCount++;
        }
        for (const tbody of table.tBodies) {
            const heading = tbody.querySelector('tr.category-row');
            if (heading) {
                const containsVisible = Array.from(tbody.querySelectorAll('tr.catalog-item'))
                    .some(row => !row.hidden);
                heading.hidden = !containsVisible;
                heading.classList.toggle('catalog-hidden', !containsVisible);
            }
        }
        if (count) count.textContent = `${visibleCount} objeto${visibleCount === 1 ? '' : 's'} encontrado${visibleCount === 1 ? '' : 's'}`;
        if (empty) empty.hidden = visibleCount !== 0;
    }
    if (search) {
        search.addEventListener('input', filterCatalog);
        search.addEventListener('search', filterCatalog);
    }
    if (status) status.addEventListener('change', filterCatalog);
    filterCatalog();

    const topButton = document.querySelector('#back-to-top');
    const updateTop = () => { if (topButton) topButton.classList.toggle('visible', window.scrollY > 350); };
    window.addEventListener('scroll', updateTop, { passive: true });
    topButton?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    updateTop();

    const modal = document.querySelector('#photo-modal');
    const modalImage = modal?.querySelector('img');
    let lastFocused = null;
    function closeModal() {
        if (!modal || modal.hidden) return;
        modal.hidden = true;
        modalImage.removeAttribute('src');
        document.body.classList.remove('modal-open');
        lastFocused?.focus();
    }
    document.querySelectorAll('.photo-link').forEach(link => {
        link.addEventListener('click', event => {
            if (!modal || !modalImage) return;
            event.preventDefault();
            lastFocused = link;
            modalImage.src = link.href;
            modalImage.alt = link.querySelector('img')?.alt || 'Imagen del objeto';
            modal.hidden = false;
            document.body.classList.add('modal-open');
            modal.querySelector('.photo-close').focus();
        });
    });
    modal?.querySelector('.photo-close')?.addEventListener('click', closeModal);
    modal?.addEventListener('click', event => { if (event.target === modal) closeModal(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeModal(); });
});
