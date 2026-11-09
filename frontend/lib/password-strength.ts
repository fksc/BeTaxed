import { ZxcvbnFactory } from "@zxcvbn-ts/core";
import * as zxcvbnCommonPackage from "@zxcvbn-ts/language-common";
import * as zxcvbnEnPackage from "@zxcvbn-ts/language-en";

export const MIN_PASSWORD_SCORE = 2;

const LABELS = ["veryWeak", "weak", "fair", "good", "strong"] as const;

let zxcvbnInstance: ZxcvbnFactory | null = null;

function getZxcvbn() {
  if (!zxcvbnInstance) {
    zxcvbnInstance = new ZxcvbnFactory({
      dictionary: {
        ...zxcvbnCommonPackage.dictionary,
        ...zxcvbnEnPackage.dictionary,
      },
      graphs: zxcvbnCommonPackage.adjacencyGraphs,
      translations: zxcvbnEnPackage.translations,
    });
  }
  return zxcvbnInstance;
}

export function passwordScore(password: string): number {
  if (!password) return 0;
  return getZxcvbn().check(password).score;
}

export function passwordLabelKey(score: number): (typeof LABELS)[number] {
  return LABELS[Math.min(Math.max(score, 0), LABELS.length - 1)];
}

export function passwordBarClass(score: number): string {
  if (score <= 0) return "bg-red-500";
  if (score === 1) return "bg-orange-500";
  if (score === 2) return "bg-amber-400";
  if (score === 3) return "bg-lime-500";
  return "bg-emerald-500";
}
