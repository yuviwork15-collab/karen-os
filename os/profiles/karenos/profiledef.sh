#!/usr/bin/env bash
# Karen OS - archiso profile definition
# shellcheck disable=SC2034

buildmodes=('iso')
iso_name="karenos"
iso_label="KARENOS_2026"
iso_publisher="Karen OS"
iso_application="Karen OS Live Desktop - low-end optimized Arch Linux"
iso_version="1.0.0"
install_dir="karenos"
arch="x86_64"
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-noappend')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--long' '-8')
pacman_conf="pacman.conf"
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/opt/karen-linux/karen_shell.py"]="0:0:755"
  ["/opt/karen-linux/karen-welcome.py"]="0:0:755"
  ["/opt/karen-linux/karen-installer.py"]="0:0:755"
  ["/usr/local/bin/karen-bootstrap.sh"]="0:0:755"
)