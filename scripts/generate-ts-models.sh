#! /usr/bin/env bash

set -eux -o pipefail

# Start backend if it's not already running
nc -z localhost 8000 || docker compose up -d || docker-compose up -d

pushd ui
  echo "// DO NOT EDIT THIS FILE. IT IS GENERATED AUTOMATICALLY." > client.d.ts
  echo "//" >> client.d.ts
  echo "// Run scripts/generate-ts-models.sh to regenerate." >> client.d.ts
  echo "// $(date)" >> client.d.ts
  echo "// Commit: $(git rev-parse HEAD)" >> client.d.ts
  npx typegen http://localhost:8000/openapi.json > client.d.ts
popd
