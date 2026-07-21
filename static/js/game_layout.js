/* Choose the desktop tabletop view without changing the mobile game experience. */
(() => {
    const desktopQuery = window.matchMedia('(min-width: 1025px)');
    const route = window.location.pathname;
    const tableRoute = route.endsWith('/table');
    const isGameRoute = route === '/game/single' || route === '/game/multi' || tableRoute;
    if (!isGameRoute) return;

    const baseRoute = route.replace(/\/table$/, '');
    const target = (nextRoute) => {
        const targetParams = new URLSearchParams(window.location.search);
        targetParams.delete('layout');
        const query = targetParams.toString();
        return `${nextRoute}${query ? `?${query}` : ''}`;
    };

    // The layout follows the viewport: mobile keeps the vertical screen and
    // desktop always uses the fixed three-column tabletop.
    if (!desktopQuery.matches && tableRoute) {
        window.location.replace(target(baseRoute));
    } else if (desktopQuery.matches && !tableRoute) {
        window.location.replace(target(`${baseRoute}/table`));
    }
})();
