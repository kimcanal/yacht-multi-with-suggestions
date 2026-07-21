/* Choose the desktop tabletop view without changing the mobile game experience. */
(() => {
    const desktopQuery = window.matchMedia('(min-width: 1025px)');
    const route = window.location.pathname;
    const tableRoute = route.endsWith('/table');
    const isGameRoute = route === '/game/single' || route === '/game/multi' || tableRoute;
    const params = new URLSearchParams(window.location.search);
    const classicRequested = params.get('layout') === 'classic';

    if (!isGameRoute) return;

    const baseRoute = route.replace(/\/table$/, '');
    const targetParams = new URLSearchParams(params);
    const target = (nextRoute) => {
        const query = targetParams.toString();
        return `${nextRoute}${query ? `?${query}` : ''}`;
    };

    // Mobile keeps the established vertical game screen.  Desktop defaults to
    // the fixed three-column tabletop, while ?layout=classic stays available
    // for an intentional before/after comparison.
    if (!desktopQuery.matches && tableRoute) {
        targetParams.set('layout', 'classic');
        window.location.replace(target(baseRoute));
    } else if (desktopQuery.matches && !tableRoute && !classicRequested) {
        targetParams.delete('layout');
        window.location.replace(target(`${baseRoute}/table`));
    }
})();
