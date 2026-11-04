#!/bin/sh
# usage: drive.sh <variant>; one python process per doc (frees memory), resumable
v=$1
while IFS="$(printf '\t')" read -r id path; do
  f="/work/$v/chunks/$(echo "$id" | sed 's#/#__#').json"
  [ -f "$f" ] && continue
  python /work/parse_one.py "$v" "$id" "$path" 2>>"/work/$v/stderr.log" | grep --line-buffered -aE "^(postfix|prefix) |^FAILED" | tee -a "/work/$v/progress.log"
done < /work/docs.tsv
echo DONE >> "/work/$v/progress.log"
