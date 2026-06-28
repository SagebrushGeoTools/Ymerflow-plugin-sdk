# Frontend Hook Reference

Frontend hooks are registered with `registerHook(name, fn)` (from `ymerflow-plugin-sdk` or
`window.__nagelfluh_registerHook`). Each registration adds a callback `fn` to the named hook;
when the host calls that hook it collects the concatenated return values of all registered
callbacks. Hooks come in three runner flavours:

- **`run`** — synchronous, returns plain values
- **`run_async`** — asynchronous, `fn` may return a Promise
- **`run_jsx`** — synchronous, React elements are wrapped in an error boundary

All callbacks must return an array (or `null`/`undefined` to contribute nothing).

> Source-path references below point at the **host application** repository (see the
> [overview](README.md) for context).

## Active hooks

### `dataset_types`

Register custom dataset classes that the frontend uses to load data by MIME type.

- **Runner:** `run`
- **Consumed by:** `datamodel/datasetRegistry.js` → `buildDatasetRegistry()` (called at startup after plugins load)
- **Callback returns:** `Array<{ mimeType: string, cls: DatasetClass }>`
  - `mimeType` — MIME type string (e.g. `"application/x-my-format"`)
  - `cls` — Dataset class implementing the gladly Data interface (`columns()`, `getData(col)`, etc.)

```js
registerHook('dataset_types', () => [
  { mimeType: 'application/x-my-format', cls: MyDataset },
])
```

### `widgets`

Register custom widget components that can be placed in the flexout layout.

- **Runner:** `run`
- **Consumed by:** `App.jsx` → `buildWidgets()` (called at startup after plugins load)
- **Callback returns:** `Array<{ name: string, component: ReactComponent }>`
  - `name` — unique widget type name used in the layout tree's `widget` field
  - `component` — React component; should export a static `.title` string for the pane dropdown

```js
registerHook('widgets', () => [
  { name: 'MyWidget', component: MyWidget },
])
```

### `layer_types`

Register custom gladly-plot layer types for use in PlotView.

- **Runner:** `run`
- **Consumed by:** `plugins/registries.js` → `buildLayerTypeRegistry()` → `registerLayerType(name, cls)`
- **Callback returns:** `Array<{ name: string, layerClass: Class }>`
  - `name` — layer type identifier used in PlotView layer configs
  - `layerClass` — class conforming to the gladly-plot layer interface

```js
registerHook('layer_types', () => [
  { name: 'MyLayerType', layerClass: MyLayerType },
])
```

### `quantity_kinds`

Register custom axis quantity kind descriptors used by gladly-plot for axis labelling and scale
selection.

- **Runner:** `run`
- **Consumed by:** `plugins/registries.js` → `buildQuantityKindRegistry()` → `registerAxisQuantityKind(name, descriptor)`
- **Callback returns:** `Array<{ name: string, descriptor: object }>`
  - `name` — quantity kind identifier (e.g. `"my_unit"`)
  - `descriptor` — gladly-plot quantity kind object (e.g. `{ label: 'My Unit', scale: 'linear' }`)

```js
registerHook('quantity_kinds', () => [
  { name: 'my_unit', descriptor: { label: 'My Unit', scale: 'linear' } },
])
```

### `pages`

Register custom full-page React components routed under `/app/plugin/{path}`.

- **Runner:** `run`
- **Consumed by:** `App.jsx` (renders each item as `<Route path="/app/plugin/{path}" element={<C />} />`)
- **Callback returns:** `Array<{ path: string, component: ReactComponent, title: string }>`
  - `path` — URL segment appended to `/app/plugin/` (no leading slash)
  - `component` — page component
  - `title` — human-readable page title

```js
registerHook('pages', () => [
  { path: 'my-page', title: 'My Page', component: MyPage },
])
```

### `app_routes`

Register additional React Router `<Route>` elements with full path control (not constrained to
the `/app/plugin/` prefix).

- **Runner:** `run_jsx`
- **Consumed by:** `App.jsx` (renders as `<Route path={path} element={element} />`)
- **Callback returns:** `Array<{ path: string, element: ReactElement }>`
  - `path` — full route path
  - `element` — React element to render

```js
registerHook('app_routes', () => [
  { path: '/my-standalone-page', element: <MyStandalonePage /> },
])
```

### `app_providers`

Wrap the entire authenticated application in additional React context providers.

- **Runner:** `run_jsx`
- **Consumed by:** `App.jsx` — providers are nested innermost-first (`reduceRight`) around the main app node, so the last registered provider is the outermost wrapper
- **Callback returns:** `Array<{ Component: ReactComponent }>`
  - `Component` — a component that accepts `children` and returns `<Component>{children}</Component>`

```js
registerHook('app_providers', () => [
  { Component: MyContextProvider },
])
```

### `account_tabs`

Add extra tabs to the Account page.

- **Runner:** `run`
- **Consumed by:** `AccountPage.jsx`
- **Callback returns:** `Array<{ id: string, title: string, content: ReactElement }>`
  - `id` — unique tab identifier
  - `title` — tab label shown in the tab bar
  - `content` — React element rendered as the tab body

```js
registerHook('account_tabs', () => [
  { id: 'my-tab', title: 'My Tab', content: <MyAccountSection /> },
])
```

### `resource_cost_display`

Provide a cost estimate component shown in the ProcessEditor before a user runs a process. Only
the **first** registered contribution is used.

- **Runner:** `run`
- **Consumed by:** `widgets/ProcessEditor.jsx`
- **Callback returns:** `Array<{ Component: ReactComponent }>`
  - `Component` — receives the current process parameters and renders a cost estimate

```js
registerHook('resource_cost_display', () => [
  { Component: MyCostDisplay },
])
```

### `user_menu_extra_items`

Add items to the user dropdown menu in the menu bar.

- **Runner:** `run_jsx`
- **Consumed by:** `UserMenu.jsx`
- **Callback returns:** array of ReactElements (rendered directly inside the menu)

```js
registerHook('user_menu_extra_items', () => [
  <li key="my-item"><button onClick={...}>My Action</button></li>,
])
```

## Reserved hooks

These hook names are accepted by `registerHook` but are not yet consumed by the host. Registering
them is harmless and forward-compatible, but they currently have no effect.

### `nav_items`

Intended for adding entries to navigation menus.

- **Callback returns:** `Array<{ menuPath: string, label: string, to?: string, onSelect?: Function }>`

### `process_actions`

Intended for adding action buttons to the ProcessEditor toolbar.

- **Callback returns:** array of ReactElements

### `plot_overlays`

Intended for adding overlay elements to the PlotView canvas.

- **Callback returns:** array of ReactElements
