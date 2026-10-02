#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo " REPLIKERS - CIFRAR ARCHIVOS .ENV"
echo "=========================================="
echo

read -r -s -p "Clave maestra de cifrado: " ENV_PASSWORD
echo

read -r -s -p "Repite la clave maestra: " ENV_PASSWORD_CONFIRM
echo
echo

if [ "$ENV_PASSWORD" != "$ENV_PASSWORD_CONFIRM" ]; then
  echo "[ERROR] Las claves no coinciden."
else
  export REPLIKERS_ENV_PASSWORD="$ENV_PASSWORD"

  FILES_ENCRYPTED=0

  if [ -f "$ROOT_DIR/backend/.env" ]; then
    openssl enc \
      -aes-256-cbc \
      -salt \
      -pbkdf2 \
      -iter 600000 \
      -md sha256 \
      -in "$ROOT_DIR/backend/.env" \
      -out "$ROOT_DIR/backend/.env.enc" \
      -pass env:REPLIKERS_ENV_PASSWORD

    if [ $? -eq 0 ]; then
      echo "[OK] backend/.env.enc creado"
      FILES_ENCRYPTED=$((FILES_ENCRYPTED + 1))
    else
      echo "[ERROR] No se pudo cifrar backend/.env"
    fi
  else
    echo "[INFO] backend/.env no existe"
  fi

  if [ -f "$ROOT_DIR/frontend/.env" ]; then
    openssl enc \
      -aes-256-cbc \
      -salt \
      -pbkdf2 \
      -iter 600000 \
      -md sha256 \
      -in "$ROOT_DIR/frontend/.env" \
      -out "$ROOT_DIR/frontend/.env.enc" \
      -pass env:REPLIKERS_ENV_PASSWORD

    if [ $? -eq 0 ]; then
      echo "[OK] frontend/.env.enc creado"
      FILES_ENCRYPTED=$((FILES_ENCRYPTED + 1))
    else
      echo "[ERROR] No se pudo cifrar frontend/.env"
    fi
  else
    echo "[INFO] frontend/.env no existe"
  fi

  unset REPLIKERS_ENV_PASSWORD
  unset ENV_PASSWORD
  unset ENV_PASSWORD_CONFIRM

  echo
  echo "ARCHIVOS_CIFRADOS=$FILES_ENCRYPTED"
  echo

  if [ "$FILES_ENCRYPTED" -gt 0 ]; then
    echo "=========================================="
    echo " CIFRADO COMPLETADO"
    echo "=========================================="
    echo
    echo "Ahora puedes subir los archivos .env.enc"
    echo "a GitHub de forma cifrada."
  fi
fi
