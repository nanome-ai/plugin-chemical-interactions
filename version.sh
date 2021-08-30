if [ $# -eq 0 ]; then
	echo "No version bump. To bump version, pass major/minor/patch "
else
	bump2version $1 --allow-dirty
fi
