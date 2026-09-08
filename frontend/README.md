# DrivePulse AI frontend

Basic Next.js App Router, TypeScript, and Tailwind setup for the premium dashboard in issue #10.

## Run locally

Use Node.js 20 or newer. From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. No environment variables or backend are required for this setup.

## Verify and build

```bash
npm run lint
npm run typecheck
npm run build
npm start
```

`npm start` serves the production build on port 3000; stop the development server first.

## Foundation

- `src/app/layout.tsx`: shared header, navigation, footer, metadata, and global stylesheet.
- `src/app/page.tsx`: responsive dashboard shell with empty states.
- `src/app/vehicles/[id]/page.tsx`: vehicle detail placeholder.
- `tailwind.config.ts`: shared charcoal, silver, and mint theme tokens.
- `postcss.config.js`: Tailwind and Autoprefixer integration.
- `.eslintrc.json`: noninteractive Next.js lint configuration.

Telemetry, predictions, and backend integration are not implemented; no sample readings are presented as live data.

## Vercel deployment

`vercel.json` selects Next.js and reproducible installation/build commands. No environment variables are required for the current shell.

1. Connect Vercel to the GitHub repository `direkkakkar319-ops/DrivePulseAI` and import it as a project.
2. Set **Root Directory** to `frontend` and **Framework Preset** to **Next.js**. Keep the default output directory.
3. Keep `main` as the production branch. Deploy `feat/10-frontend-basic-setup` as a preview to review this change before merging.
4. Confirm that the preview renders and the Vercel deployment status appears on the pull request. The GitHub integration creates this status automatically; no token-based GitHub Actions workflow is needed.
5. After review and merge to `main`, verify the production deployment URL.

The configuration alone does not publish a site or enable GitHub checks. A Vercel account with access to the repository must connect the project first. Deployment and check verification remain pending until that connection is made.

See [Vercel for GitHub](https://vercel.com/docs/git/vercel-for-github) and [monorepo setup](https://vercel.com/docs/monorepos).
