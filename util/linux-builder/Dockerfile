FROM ubuntu:18.04

# GitHub-hosted runners intermittently fail the legacy Bionic mirrors over
# plain HTTP. Keep the compatibility image, but use TLS and retry package
# index/download requests so a partial apt index cannot masquerade as
# missing build dependencies.
RUN sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
        -e 's|http://security.ubuntu.com/ubuntu|https://security.ubuntu.com/ubuntu|g' \
        /etc/apt/sources.list && \
    apt-get -o Acquire::Retries=5 update && \
    apt-cache show build-essential >/dev/null && \
    DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 -y upgrade && \
    DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 install -y \
        libusb-1.0-0-dev libudev-dev ruby ruby-dev rubygems build-essential \
        desktop-file-utils wget unzip zlib1g-dev liblzma-dev libssl-dev git \
        imagemagick file libfuse2 && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/AppImage/pkg2appimage/archive/38603d92359a48189c35debad9005e8e902e6070.zip && \
    unzip *.zip && \
    gem install dotenv -v 2.8.1 && \
    gem install --no-document fpm -v 1.16.0 && \
    fpm --version

COPY . /vial-gui

RUN /vial-gui/util/setup_python36.sh
