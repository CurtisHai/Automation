#!/bin/bash
# Convert GoPro .360 video using hardware acceleration if available
set -e
input="$1"
output="${2:-${input%.*}.mp4}"

ffmpeg -y -hwaccel opencl -i "$input" \
    -c:v h264 -pix_fmt yuv420p -map_metadata 0 \
    -c:a aac "$output"

if command -v exiftool >/dev/null; then
    exiftool -api LargeFileSupport=1 -overwrite_original \
        -XMP-GSpherical:Spherical=true \
        -XMP-GSpherical:Stitched=true \
        -XMP-GSpherical:ProjectionType=equirectangular "$output"
fi
