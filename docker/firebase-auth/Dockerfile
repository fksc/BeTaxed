# Firebase Auth emulator only. No Java (Firestore/RTDB not started).
FROM node:24-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g firebase-tools@14.16.0

WORKDIR /workspace
COPY firebase.json .firebaserc ./

EXPOSE 9099 4000
CMD ["firebase", "emulators:start", "--only", "auth", "--project", "demo-betaxed"]
