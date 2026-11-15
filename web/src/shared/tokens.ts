/** Numbers the components need in script; colours and sizes live in theme.css. */
export const motion = {
  reveal: 0.22,
  stagger: 0.06,
  rise: 6,
  ease: [0.2, 0.7, 0.2, 1] as const,
}

export const layout = {
  skeletonRows: 5,
  skeletonWidths: ['92%', '76%', '84%', '60%', '70%'],
}

export const config = {
  apiKey: (import.meta.env.VITE_API_KEY as string | undefined) ?? 'manager-demo-key',
  locale: 'en-GB',
}

export const PHASE_LABEL: Record<string, string> = {
  discovery: 'Discovery',
  build: 'Build',
  go_live: 'Go-live',
  hypercare: 'Hypercare',
}

export const PROFILE_LABEL: Record<string, string> = {
  advisory: 'Advisory',
  builder: 'Builder',
  operating: 'Operating',
  support: 'Support',
}
