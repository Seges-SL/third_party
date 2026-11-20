#!/usr/bin/env bash
# Pruebas con toda la rama (D41 y D42, 17/11/2026): crea las dos carpetas de
# laboratorio de P-2 y P-14, como en el MANUAL del kit (6.7, «Carpeta de
# laboratorio»):
#   ~/GitHub/lab_pns_ai_879   3.1.879 de ~/pns_ai_3973/fase0/modulos_3879
#                             (SHA-256 comprobado contra sha256_copias.tsv);
#   ~/GitHub/lab_pns_ai_973f  base limpia 3.1.973: git archive del commit de la
#                             1b (33ca68c, «base 3.1.973 del fabricante»), solo
#                             pns_base, pns_ai_mcp y pns_ai_chatboo.
# Cada una con git init, CLAUDE.md («Versión de Odoo: 14.0»), .odoo-dev.conf
# (COMPARTIDOS="" y DOCKERFILE="infra/Dockerfile.14"), infra/Dockerfile.14
# (copia del de ~/GitHub/lab_pns_ai_3973), ORIGEN.txt y SHA256SUMS.txt.
# Permisos de los módulos: 644 (archivos) y 755 (carpetas).
# Permisos de la raíz y de lo que escribe el script (infra/, infra/Dockerfile.14,
# CLAUDE.md, .odoo-dev.conf, SHA256SUMS.txt y ORIGEN.txt): 755 y 644, sea cual
# sea el umask de la terminal (umask 022 y chmod explícito). Corrección del
# 18/11/2026: con umask 077, mkdir, las redirecciones y cp sin -p los dejaban en
# 700/600 y el usuario del contenedor no podía entrar (paridad «SIN CÓDIGO»).
# Al final comprueba que todo lo de las dos carpetas (sin .git) es legible por
# otros; si no, nombra lo que no lo es y falla (código 1).
#
# SOLO ESCRIBE en esas dos carpetas, que no pueden existir antes. No arranca
# Odoo, no toca ninguna BD y solo lee third_party (git archive, ls-tree y
# hash-object sin -w). Si algo falla a medias, borra las carpetas que creó en
# esta ejecución.
#
# Uso: bash rama_carpetas.sh
# Códigos: 0 creadas y comprobadas; 1 falló al crearlas o algo no es legible
# por otros (se borra lo creado);
# 10 respuesta distinta de «s»; 13 falta un origen; 17 un SHA-256 o el commit
# no es el previsto (no se crea nada); 18 alguna carpeta ya existe (no se crea
# nada).
set -uo pipefail
umask 022  # lo nuevo, 755 y 644 (no el umask de la terminal)

REPO=~/GitHub/third_party
COMMIT_1B=33ca68c
ASUNTO_1B='[IMP] pns_ai: base 3.1.973 del fabricante, sin cambios'
DOCKERFILE_ORIGEN=~/GitHub/lab_pns_ai_3973/infra/Dockerfile.14
SHA_DOCKERFILE=cfc58aed82d52734706dca9b28bef12dfbe42d5db6288f224ec2a481a9f4c348
FASE0=~/pns_ai_3973/fase0
TSV=$FASE0/sha256_copias.tsv
DEST_879=~/GitHub/lab_pns_ai_879
DEST_973F=~/GitHub/lab_pns_ai_973f
MODULOS=(pns_base pns_ai_mcp pns_ai_chatboo)

CREADAS=()
deshacer() {
    local d
    for d in ${CREADAS[@]+"${CREADAS[@]}"}; do
        case "$d" in
            "$DEST_879"|"$DEST_973F") rm -rf -- "$d" && echo "Borrada (creada en esta ejecución): $d" ;;
        esac
    done
}
falla() { echo "FALLO: $1"; deshacer; exit 1; }

# Lista «sha256  ruta» de los archivos de los tres módulos de 3.1.879 en la tabla.
tabla_879() {
    awk -F'\t' 'NR > 1 && $1 ~ /^modulos_3879\// && $4 == "sí" { print $3 "  " $1 }' "$TSV"
}

# Permisos de D41 en los módulos de una carpeta.
permisos() {
    local m
    for m in "${MODULOS[@]}"; do
        find "$1/$m" -type d -exec chmod 755 {} + && find "$1/$m" -type f -exec chmod 644 {} + || return 1
    done
}

# SHA256SUMS.txt de los módulos de una carpeta; imprime su propio SHA-256.
sumas() {
    (cd "$1" && find "${MODULOS[@]}" -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) \
        > "$1/SHA256SUMS.txt" && chmod 644 "$1/SHA256SUMS.txt" || return 1
    sha256sum "$1/SHA256SUMS.txt" | cut -d' ' -f1
}

# Lo que otros no pueden leer en una carpeta, sin .git: carpetas sin r-x y
# archivos sin r para «otros» (el usuario del contenedor). Solo lectura.
no_legibles() {
    find "$1" -path "$1/.git" -prune -o \( -type d ! -perm -o=rx -o ! -type d ! -perm -o=r \) -print
}

base_carpeta() {  # base_carpeta <destino> <título>
    mkdir "$1" || return 1
    CREADAS+=("$1")
    git -C "$1" init -q || return 1
    printf '# %s\n\nVersión de Odoo: 14.0\n' "$2" > "$1/CLAUDE.md" || return 1
    printf 'COMPARTIDOS=""\nDOCKERFILE="infra/Dockerfile.14"\n' > "$1/.odoo-dev.conf" || return 1
    mkdir "$1/infra" && cp "$DOCKERFILE_ORIGEN" "$1/infra/Dockerfile.14" || return 1
    chmod 755 "$1" "$1/infra" && chmod 644 "$1/CLAUDE.md" "$1/.odoo-dev.conf" "$1/infra/Dockerfile.14" || return 1
    echo "$SHA_DOCKERFILE  $1/infra/Dockerfile.14" | sha256sum -c --quiet - >/dev/null 2>&1
}

# -- Comprobaciones previas (solo lectura) ---------------------------------
for d in "$DEST_879" "$DEST_973F"; do
    [ ! -e "$d" ] || { echo "Ya existe $d: no se crea nada."; exit 18; }
done
[ -f "$DOCKERFILE_ORIGEN" ] || { echo "No existe $DOCKERFILE_ORIGEN."; exit 13; }
[ -f "$TSV" ] && [ -d "$FASE0/modulos_3879" ] || { echo "Falta $TSV o $FASE0/modulos_3879."; exit 13; }
[ -d "$REPO/.git" ] || { echo "No existe $REPO."; exit 13; }
echo "$SHA_DOCKERFILE  $DOCKERFILE_ORIGEN" | sha256sum -c --quiet - >/dev/null 2>&1 \
    || { echo "El SHA-256 de $DOCKERFILE_ORIGEN no es el previsto: no se crea nada."; exit 17; }

N_TABLA=$(tabla_879 | wc -l)
[ "$N_TABLA" = 711 ] || { echo "La tabla tiene $N_TABLA filas de modulos_3879 con «sí» (se esperaban 711)."; exit 17; }
(cd "$FASE0" && tabla_879 | sha256sum -c --quiet - >/dev/null 2>&1) \
    || { echo "modulos_3879 no coincide con $TSV: no se crea nada."; exit 17; }
SOBRAN=$(comm -13 <(tabla_879 | cut -c67- | LC_ALL=C sort) \
                  <(cd "$FASE0" && find modulos_3879 -type f | LC_ALL=C sort) | wc -l)
[ "$SOBRAN" = 0 ] || { echo "modulos_3879 tiene $SOBRAN archivos fuera de la tabla."; exit 17; }

ASUNTO=$(git -C "$REPO" log -1 --format=%s "$COMMIT_1B" 2>/dev/null) || ASUNTO=
[ "$ASUNTO" = "$ASUNTO_1B" ] || { echo "El commit $COMMIT_1B no es el de la 1b: no se crea nada."; exit 17; }
COMMIT_LARGO=$(git -C "$REPO" rev-parse "$COMMIT_1B^{commit}")
N_1B=$(git -C "$REPO" ls-tree -r --name-only "$COMMIT_1B" -- "${MODULOS[@]}" | wc -l)

echo "Orígenes comprobados (solo lectura):"
echo "  Dockerfile.14 de lab_pns_ai_3973: SHA-256 $SHA_DOCKERFILE"
echo "  modulos_3879: $N_TABLA archivos, todos con el SHA-256 de sha256_copias.tsv, ninguno de más"
echo "  commit de la 1b: $COMMIT_LARGO ($N_1B archivos de los tres módulos)"
read -rp "Esto ESCRIBE en ~/GitHub: crea $DEST_879 y $DEST_973F. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se crea nada."; exit 10; }
trap 'echo; falla "interrumpido"' INT TERM

# -- lab_pns_ai_879 ---------------------------------------------------------
base_carpeta "$DEST_879" 'Laboratorio pns_ai 3.1.879 (P-2 y P-14 de la rama 14.0-pns-ai-3973)' \
    || falla "no se pudo preparar $DEST_879"
for m in "${MODULOS[@]}"; do
    cp -r --no-preserve=mode,ownership "$FASE0/modulos_3879/$m" "$DEST_879/$m" || falla "copia de $m"
done
permisos "$DEST_879" || falla "permisos de $DEST_879"
(cd "$DEST_879" && tabla_879 | sed 's#  modulos_3879/#  #' | sha256sum -c --quiet - >/dev/null 2>&1) \
    || falla "la copia de $DEST_879 no coincide con la tabla"
SUMAS_879=$(sumas "$DEST_879") || falla "SHA256SUMS.txt de $DEST_879"
[ "$(wc -l < "$DEST_879/SHA256SUMS.txt")" = 711 ] || falla "$DEST_879 no tiene 711 archivos en sus módulos"
cat > "$DEST_879/ORIGEN.txt" <<EOF || falla "ORIGEN.txt de $DEST_879"
3.1.879 para P-2 (a y b) y P-14 de la rama 14.0-pns-ai-3973 (D41, 17/11/2026).
Módulos copiados de ~/pns_ai_3973/fase0/modulos_3879 (711 archivos, SHA-256 de sha256_copias.tsv).
SHA256SUMS.txt (lista de los módulos): $SUMAS_879
Dockerfile.14: copia de ~/GitHub/lab_pns_ai_3973/infra/Dockerfile.14 ($SHA_DOCKERFILE).
EOF
chmod 644 "$DEST_879/ORIGEN.txt" || falla "permisos de ORIGEN.txt de $DEST_879"

# -- lab_pns_ai_973f --------------------------------------------------------
base_carpeta "$DEST_973F" 'Laboratorio pns_ai 3.1.973 base limpia (P-2 b de la rama 14.0-pns-ai-3973)' \
    || falla "no se pudo preparar $DEST_973F"
git -C "$REPO" archive --format=tar "$COMMIT_1B" -- "${MODULOS[@]}" | tar -x -C "$DEST_973F" \
    || falla "git archive de $COMMIT_1B"
permisos "$DEST_973F" || falla "permisos de $DEST_973F"
# Cada archivo extraído es el blob del commit (hash-object sin -w no escribe nada).
DIFS=$(diff <(git -C "$REPO" ls-tree -r "$COMMIT_1B" -- "${MODULOS[@]}" | awk '{print $3 "\t" $4}' | LC_ALL=C sort -k2) \
            <(cd "$DEST_973F" && find "${MODULOS[@]}" -type f | LC_ALL=C sort | while IFS= read -r f; do
                  printf '%s\t%s\n' "$(git hash-object --no-filters -- "$f")" "$f"; done | LC_ALL=C sort -k2) | wc -l)
[ "$DIFS" = 0 ] || falla "$DEST_973F no coincide con el commit $COMMIT_1B ($DIFS líneas distintas)"
SUMAS_973F=$(sumas "$DEST_973F") || falla "SHA256SUMS.txt de $DEST_973F"
cat > "$DEST_973F/ORIGEN.txt" <<EOF || falla "ORIGEN.txt de $DEST_973F"
Base limpia 3.1.973 para P-2 (b) de la rama 14.0-pns-ai-3973 (D41, 17/11/2026).
git archive de third_party, commit $COMMIT_LARGO («$ASUNTO_1B»):
pns_base, pns_ai_mcp y pns_ai_chatboo ($N_1B archivos, cada uno igual a su blob del commit).
SHA256SUMS.txt (lista de los módulos): $SUMAS_973F
Dockerfile.14: copia de ~/GitHub/lab_pns_ai_3973/infra/Dockerfile.14 ($SHA_DOCKERFILE).
EOF
chmod 644 "$DEST_973F/ORIGEN.txt" || falla "permisos de ORIGEN.txt de $DEST_973F"

# -- Permisos: todo legible por otros (sin .git), solo lectura ----------------
NO_LEGIBLES=$(for d in "$DEST_879" "$DEST_973F"; do no_legibles "$d"; done)
if [ -n "$NO_LEGIBLES" ]; then
    echo "No legibles por otros (el usuario del contenedor no podría leerlos):"
    printf '%s\n' "$NO_LEGIBLES" | sed 's/^/  /'
    falla "permisos de las carpetas"
fi
trap - INT TERM

echo "Creadas y comprobadas:"
echo "  $DEST_879: 711 archivos de módulos; SHA256SUMS.txt $SUMAS_879"
echo "  $DEST_973F: $N_1B archivos de módulos (blobs de $COMMIT_1B); SHA256SUMS.txt $SUMAS_973F"
echo "  Dockerfile.14 en las dos: $SHA_DOCKERFILE"
echo "  Permisos en las dos (sin .git): todo legible por otros (carpetas 755, archivos 644)"
exit 0
