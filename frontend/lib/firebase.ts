import { initializeApp, getApps, getApp } from "firebase/app";
import {
  getAuth,
  connectAuthEmulator,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  type Auth,
  type User,
} from "firebase/auth";

let connectedEmulator = false;

function getFirebaseAuth(): Auth {
  const projectId =
    process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID?.trim() || "demo-betaxed";
  const apiKey =
    process.env.NEXT_PUBLIC_FIREBASE_API_KEY?.trim() || "fake-api-key";
  const app = getApps().length
    ? getApp()
    : initializeApp({
        apiKey,
        projectId,
        authDomain: `${projectId}.firebaseapp.com`,
      });
  const auth = getAuth(app);
  const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST?.trim();
  if (emulator && !connectedEmulator) {
    const url = emulator.startsWith("http") ? emulator : `http://${emulator}`;
    try {
      connectAuthEmulator(auth, url, { disableWarnings: true });
    } catch {
      /* HMR may already have connected */
    }
    connectedEmulator = true;
  }
  return auth;
}

export async function ensureEmailUser(
  email: string,
  password: string,
): Promise<User> {
  const auth = getFirebaseAuth();
  try {
    const created = await createUserWithEmailAndPassword(auth, email, password);
    return created.user;
  } catch (error) {
    const code = (error as { code?: string }).code;
    if (code === "auth/email-already-in-use") {
      const signed = await signInWithEmailAndPassword(auth, email, password);
      return signed.user;
    }
    throw error;
  }
}

export async function currentIdToken(): Promise<string | null> {
  const auth = getFirebaseAuth();
  const user = auth.currentUser;
  if (!user) {
    return null;
  }
  return user.getIdToken();
}
