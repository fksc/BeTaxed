/** App Router hrefs (no locale prefix — next-intl adds it). */
export const paths = {
  home: "/",
  start: "/start",
  about: "/about",
  contact: "/contact",
  privacy: "/privacy",
  login: "/login",
  companies: "/companies",
  companiesDashboard: "/companies/dashboard",
  companiesSettings: "/companies/settings",
  admins: "/admins",
  adminsDashboard: "/admins/dashboard",
  adminsSettings: "/admins/settings",
} as const;
