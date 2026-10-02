#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo " REPLIKERS - RESTAURAR ARCHIVOS .ENV"
echo "=========================================="
echo

read -r -s -p "Clave maestra de cifrado: " ENV_PASSWORD
echo
echo

export REPLIKERS_ENV_PASSWORD="$ENV_PASSWORD"

FILES_RESTORED=0

if [ -f "$ROOT_DIR/backend/.env.enc" ]; then
  BACKEND_TEMP="$ROOT_DIR/backend/.env.tmp"

  rm -f "$BACKEND_TEMP"

  openssl enc \
    -d \
    -aes-256-cbc \
    -pbkdf2 \
    -iter 600000 \
    -md sha256 \
    -in "$ROOT_DIR/backend/.env.enc" \
    -out "$BACKEND_TEMP" \
    -pass env:REPLIKERS_ENV_PASSWORD

  if [ $? -eq 0 ]; then
    mv "$BACKEND_TEMP" "$ROOT_DIR/backend/.env"

    echo "[OK] backend/.env restaurado"
    FILES_RESTORED=$((FILES_RESTORED + 1))
  else
    rm -f "$BACKEND_TEMP"
    echo "[ERROR] Clave incorrecta o archivo backend corrupto"
  fi
else
  echo "[INFO] backend/.env.enc no existe"
fi

if [ -f "$ROOT_DIR/frontend/.env.enc" ]; then
  FRONTEND_TEMP="$ROOT_DIR/frontend/.env.tmp"

  rm -f "$FRONTEND_TEMP"

  openssl enc \
    -d \
    -aes-256-cbc \
    -pbkdf2 \
    -iter 600000 \
    -md sha256 \
    -in "$ROOT_DIR/frontend/.env.enc" \
    -out "$FRONTEND_TEMP" \
    -pass env:REPLIKERS_ENV_PASSWORD

  if [ $? -eq 0 ]; then
    mv "$FRONTEND_TEMP" "$ROOT_DIR/frontend/.env"

    echo "[OK] frontend/.env restaurado"
    FILES_RESTORED=$((FILES_RESTORED + 1))
  else
    rm -f "$FRONTEND_TEMP"
    echo "[ERROR] Clave incorrecta o archivo frontend corrupto"
  fi
else
  echo "[INFO] frontend/.env.enc no existe"
fi

unset REPLIKERS_ENV_PASSWORD
unset ENV_PASSWORD

echo
echo "ARCHIVOS_RESTAURADOS=$FILES_RESTORED"
echo
echo "=========================================="
echo " RESTAURACION TERMINADA"
echo "=========================================="
