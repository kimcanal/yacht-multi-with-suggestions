/* Keep the wide desktop tabletop optional without changing compact layouts. */
(() => {
    const TABLE_MIN_WIDTH = 1201;
    const desktopQuery = window.matchMedia(`(min-width: ${TABLE_MIN_WIDTH}px)`);
    const preferenceKey = 'yacht-game-layout';
    const route = window.location.pathname;
    const tableRoute = route.endsWith('/table');
    const isGameRoute = route === '/game/single' || route === '/game/multi' || tableRoute;
    if (!isGameRoute) return;

    const baseRoute = route.replace(/\/table$/, '');
    const getPreference = () => {
        try {
            const preference = window.localStorage.getItem(preferenceKey);
            return preference === 'classic' || preference === 'table' ? preference : 'table';
        } catch (_) {
            return 'table';
        }
    };
    const savePreference = (preference) => {
        try {
            window.localStorage.setItem(preferenceKey, preference);
        } catch (_) {
            // Private browsing or a blocked storage policy should not prevent play.
        }
    };
    const target = (nextRoute) => {
        const targetParams = new URLSearchParams(window.location.search);
        targetParams.delete('layout');
        const query = targetParams.toString();
        return `${nextRoute}${query ? `?${query}` : ''}`;
    };
    const routeFor = (preference) => (
        preference === 'table' && desktopQuery.matches ? `${baseRoute}/table` : baseRoute
    );
    const navigateIfNeeded = (replace = true) => {
        const desiredRoute = routeFor(getPreference());
        if (window.location.pathname === desiredRoute && !new URLSearchParams(window.location.search).has('layout')) return;
        if (replace) {
            window.location.replace(target(desiredRoute));
        } else {
            window.location.assign(target(desiredRoute));
        }
    };

    window.setGameLayout = (preference) => {
        if (preference !== 'classic' && preference !== 'table') return;
        savePreference(preference);
        navigateIfNeeded(false);
    };

    const requestedLayout = new URLSearchParams(window.location.search).get('layout');
    if (requestedLayout === 'classic' || requestedLayout === 'table') {
        savePreference(requestedLayout);
    }

    // Compact screens use the established layout. Wide screens default to the
    // table unless the player has explicitly kept the classic view.
    navigateIfNeeded();
    desktopQuery.addEventListener('change', () => navigateIfNeeded());
})();
