#!/usr/bin/env bash
# extrae_alumnado.sh
# 1) Ir a la raíz del proyecto
# 2) Buscar ficheros de hoy con patrón ./logs/YYYY_MM_DD*www.html
# 3) Ejecutar grep -B 1 '/Alumnado' y generar CSVs en ./csvs
# 4) Descargar los CSVs al equipo del usuario mediante scp (si se define SCP_TARGET)

set -euo pipefail

# --- CONFIGURACIÓN ---
ROOT_DIR="/var/fp-distancia-gestion-usuarios-automatica"

# (Opcional) destino de descarga para scp, por ejemplo:
# export SCP_TARGET="usuario@miportatil:/home/usuario/Descargas"
SCP_TARGET="${SCP_TARGET:-}"

# Si el servidor no está en tu zona horaria, ajusta TZ.
# export TZ="Europe/Madrid"
DATE_STR="$(date +%Y_%m_%d)"   # p.ej., 2025_10_16

# --- 1) Ir a la raíz del proyecto ---
cd "$ROOT_DIR"

# --- 2) Obtener ficheros del día de hoy ---
shopt -s nullglob
mapfile -t html_files < <(printf '%s\n' ./logs/"${DATE_STR}"*www.html)

if ((${#html_files[@]}==0)); then
  echo "No se encontraron ficheros con el patrón ./logs/${DATE_STR}*www.html"
  exit 1
fi

# --- 3) Ejecutar grep y generar CSVs ---
mkdir -p ./csvs
generated=()

for f in "${html_files[@]}"; do
  base="$(basename "$f" .html)"          # ej: 2025_10_16_04_15_29_www
  out="./csvs/${base}.csv"               # ej: ./csvs/2025_10_16_04_15_29_www.csv

  # Equivale a: cat logs/… | grep -B 1 '/Alumnado' > csvs/….
  # Se usa grep directamente sobre el fichero (más eficiente).
  grep -B 1 '/Alumnado' "$f" > "$out" || true

  echo "Generado: $out"
  generated+=("$out")
done
