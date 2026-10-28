# AGIOne Demo front-end origin

The UI assets originate from the AGIOne front-end prototype.

- `original-style.css`, `original-live.css` and
  `original-dashboard-finance.css` are unchanged copies of the original CSS.
- `demo-scoped.css` contains the same rules and values, with each selector
  prefixed by `.agione-demo`. Original `:root`, `body`, and root state classes
  are mapped onto the wrapper. The original CSS files are not imported globally.
- `core.mjs` is an unchanged copy of the pure front-end helper module. The page
  imports calendar and trend helpers only; its historical `FIXED_WINDOW` export
  is not used as data or as the synchronization window.
- `AgioneOps.vue` ports the original `index.html` shell and the dashboard,
  connection menu, calendar, model, and finance DOM/classes from `app.mjs`,
  `connections.mjs`, and `dashboard-finance.mjs` into Vue bindings.
- The original app bootstrap, unauthenticated fetch layer, storage access and
  port-specific behavior are not executed. Data uses DevMind's authenticated,
  scoped `/api/v1/agione-ops/` endpoints through the existing API client.
- Missing financial values are not fabricated as zero.
