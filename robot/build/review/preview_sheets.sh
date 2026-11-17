#!/bin/zsh
# preview_sheets.sh [BEAUTY_DIR SHEET_DIR [BG]]: one contact sheet per Move over a plain backdrop: first frame, each Hit
# frame (at most 4) and last frame, front Angle on the first row, side on the second. Defaults: the preview Clips over
# mid grey into robot/build/probe/preview/sheets. The package: robot/package/v1/beauty robot/build/probe/package/sheets.
# EXCHANGES=1: one sheet per Exchange instead, duel_wide on the first row, duel_low on the second.
cd "${0:A:h}/../../.."
P=robot/build/probe/preview; B=${1:-$P/beauty}; S=${2:-$P/sheets}; BG=${3:-0x808080}
rm -rf "${S:?}"; mkdir -p $S/tiles
python3 -c "import sys; sys.path.insert(0, 'robot/build'); import exchanges, moves
if sys.argv[1]:
    for e in exchanges.EXCHANGES.values():
        hits = {moves.beat_frame(s.beat) for s in e.hits} | {h['f'] for h in moves.hit_frames(e.android)}
        print(e.name, 'duel_wide,duel_low', 0, *sorted(hits)[:4], moves.move_frames(e.android) - 1)
else:
    for m in moves.MOVES.values():
        fr = [0] + sorted({h['f'] for h in moves.hit_frames(m)})[:4] + [moves.move_frames(m) - 1]
        print(m.name, 'front,side', *fr)" "$EXCHANGES" | while read m angles frames; do
  files=()
  for a in ${(s:,:)angles}; do
    [[ -f $B/${m}__$a.mov ]] || continue
    for f in ${=frames}; do
      t=$S/tiles/${m}__${a}_$(printf %04d $f).png
      ffmpeg -nostdin -v error -y -f lavfi -i color=c=${BG}:s=960x540 -i $B/${m}__$a.mov \
        -filter_complex "[1]select=eq(n\,$f),setpts=PTS-STARTPTS,scale=960:540[s];[0][s]overlay=shortest=1" -frames:v 1 $t
      files+=($t)
    done
  done
  (( ${#files} )) && zsh blender/review/named_sheet.sh $S/$m.png ${#${=frames}} "${files[@]}"
done
