#!/usr/bin/env bash

# This is an install script to set up MSVC ABI compatible build environment.
# It must be executed from a vcenv.cmd shell to properly access Visual Studio command-line tools.
# The MSVC c++ compiler, clang and the Windows SDK must be installed.
#
# change in configure.user:
#
# USE_MS_ABI=yes
# WITH_SCAVE_PYTHON_BINDINGS=no
# WITH_BACKTRACE=no
# If you do not need 3D visualization:
# WITH_OSG=no 

if [[ "$MS_ABI" != "yes" ]]; then
  echo "Error: This script can be executed only in a shell started by 'vcenv.cmd'"
  exit 1
fi

if [[ "$(uname -o)" == *"Msys"* ]]; then
        packages="autoconf2.72 bash bash-completion bison bzip2 ccache coreutils curl \
        dash diffutils dos2unix doxygen file filesystem findutils flex gawk gcc-libs \
        git grep gzip inetutils info less lndir make man-db mintty msys2-keyring \
        msys2-launcher msys2-runtime ncurses p7zip pacman pacman-mirrors pactoys-git \
        patch pax-git perl pkgfile rebase sed tar tftp-hpa time tzcode unzip \
        util-linux which zip \
        $MINGW_PACKAGE_PREFIX-pkgconf \
        $MINGW_PACKAGE_PREFIX-python \
        $MINGW_PACKAGE_PREFIX-python-pip \
        $MINGW_PACKAGE_PREFIX-python-numpy \
        $MINGW_PACKAGE_PREFIX-python-matplotlib \
        $MINGW_PACKAGE_PREFIX-python-pandas \
        $MINGW_PACKAGE_PREFIX-python-seaborn \
        $MINGW_PACKAGE_PREFIX-python-scipy \
        $MINGW_PACKAGE_PREFIX-python-ipython"

        pacman -S --needed --noconfirm $packages
        pacman -Scc --noconfirm
fi

# Install dependencies.
# You MUST add '--x-feature=3d' to install OpenSceneGraph if you specified WITH_OSG=yes in configure.user)
vcpkg install --triplet=x64-windows-release --host-triplet=x64-windows-release --clean-after-build
mv vcpkg_installed/x64-windows-release /opt/visualc
find /opt/visualc/ -type f -iname '*.pdb' -delete

source setenv
