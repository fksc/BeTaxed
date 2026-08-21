const SESSION_KEY = "betaxed.intake.session";
const INTAKE_KEY = "betaxed.intake.id";
const COMPANY_NAME_KEY = "betaxed.workspace.legalName";

export function loadIntakeSession(): { intakeId: string; sessionToken: string | null } | null {
  if (typeof window === "undefined") {
    return null;
  }
  const intakeId = sessionStorage.getItem(INTAKE_KEY);
  if (!intakeId) {
    return null;
  }
  return {
    intakeId,
    sessionToken: sessionStorage.getItem(SESSION_KEY),
  };
}

export function saveIntakeSession(intakeId: string, sessionToken: string | null): void {
  sessionStorage.setItem(INTAKE_KEY, intakeId);
  if (sessionToken) {
    sessionStorage.setItem(SESSION_KEY, sessionToken);
  } else {
    sessionStorage.removeItem(SESSION_KEY);
  }
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

export function clearIntakeSession(): void {
  sessionStorage.removeItem(INTAKE_KEY);
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(COMPANY_NAME_KEY);
}
