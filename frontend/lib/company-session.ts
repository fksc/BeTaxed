const COMPANY_ID_KEY = "betaxed.workspace.companyId";
const COMPANY_NAME_KEY = "betaxed.workspace.legalName";

export function saveCompanyId(companyId: string): void {
  sessionStorage.setItem(COMPANY_ID_KEY, companyId);
}

export function loadCompanyId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return sessionStorage.getItem(COMPANY_ID_KEY);
}

export function saveWorkspaceName(legalName: string): void {
  sessionStorage.setItem(COMPANY_NAME_KEY, legalName);
}

export function loadWorkspaceName(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return sessionStorage.getItem(COMPANY_NAME_KEY);
}

export function clearCompanySession(): void {
  sessionStorage.removeItem(COMPANY_ID_KEY);
  sessionStorage.removeItem(COMPANY_NAME_KEY);
}
