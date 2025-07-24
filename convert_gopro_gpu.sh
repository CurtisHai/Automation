#!/bin/bash
file_name=$1
output_name=$2
ffmpeg -hwaccel opencl -v verbose -filter_complex '[0:0]format=yuv420p,hwupload[a] , [0:5]format=yuv420p,hwupload[b], [a][b]gopromax_opencl, hwdownload,format=yuv420p' -i $file_name -c:v libx264 -pix_fmt yuv420p -map_metadata 0 -map 0:a -map 0:3 $output_name