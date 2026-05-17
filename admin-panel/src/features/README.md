# features/

One folder per feature module. Each folder follows the same shape:

```
features/<name>/
├── api.ts            React Query hooks + fetcher functions
├── components/       feature-local UI building blocks
├── pages/            top-level routed pages
├── types.ts          feature-local TypeScript types
└── index.ts          public exports consumed by routes/
```

Empty for now — feature modules land here as each one is wired up.
Cross-feature reusable primitives belong in `src/components/`, not here.
