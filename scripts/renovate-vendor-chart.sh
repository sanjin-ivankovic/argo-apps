#!/bin/sh
# Renovate postUpgradeTask for the vendored shared-data charts (postgresql,
# valkey): pull the new chart into <app>/charts/<name>-<new>/ and remove the
# old copy, so the bump MR passes validate:apps without a manual step.
# Needs only sh and helm (installTools in renovate.json); the registry allows
# anonymous pulls.
#
# Usage: scripts/renovate-vendor-chart.sh <app-dir> <registry/path/name> <new> <old>
set -eu

app=$1 package=$2 new=$3 old=$4
name=${package##*/}
dest="$app/charts/$name-$new"

rm -rf "$dest"
helm pull "oci://$package" --version "$new" --untar --untardir "$dest"
test -f "$dest/$name/Chart.yaml"
if [ "$old" != "$new" ]; then
  rm -rf "$app/charts/$name-$old"
fi
echo "vendored $name $new into $dest"
