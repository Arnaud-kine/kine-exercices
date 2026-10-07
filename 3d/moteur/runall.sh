#!/bin/bash
# usage : runall.sh <secondes disponibles> ; traite les exercices en attente, personnage par personnage
cd /tmp/b3d; START=$(date +%s); TOTAL=${1:-255}
for c in FA MA FS MS; do
  NOW=$(( $(date +%s) - START )); LEFT=$(( TOTAL - NOW )); [ $LEFT -lt 90 ] && break
  P=$(python3 -c "
import importlib.util, os
s = importlib.util.spec_from_file_location('specs', '/tmp/b3d/specs.py'); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
print(sum(1 for x in m.SPECS if x['char'] == '$c' and not os.path.exists('/tmp/b3d/ex3d/' + x['slug'] + '/OK')))")
  [ "$P" = "0" ] && continue
  timeout $(( LEFT + 5 )) blender -b -P batch3d.py -- $c /tmp/b3d/specs.py /tmp/b3d/ex3d $(( LEFT - 70 )) 14 10 full 2>&1 | grep -E "^(FAIT|ERREUR)"
done
# assemblage des vidéos et photos des exercices terminés
for d in /tmp/b3d/ex3d/*/; do s=$(basename $d); [ -f $d/OK ] && [ ! -f /tmp/b3d/out3d/$s.mp4 ] && PEND="$PEND $s"; done
[ -n "$PEND" ] && timeout 70 python3 post3d.py /tmp/b3d/ex3d /tmp/b3d/out3d $PEND 2>&1 | grep -E "^PRET|Error|Traceback" | head -6
echo "durée totale : $(( $(date +%s) - START )) s"
