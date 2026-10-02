FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

RUN apt-get update && apt-get install -y \
    systemd \
    systemd-sysv \
    openssh-server \
    sudo \
    docker.io \
    logrotate \
    fail2ban \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash testuser \
    && echo 'testuser:test' | chpasswd \
    && echo 'testuser ALL=(ALL) NOPASSWD:ALL' \
       > /etc/sudoers.d/testuser \
    && usermod -aG docker testuser \
    && chmod 0440 /etc/sudoers.d/testuser

RUN mkdir -p /run/sshd /etc/docker /etc/systemd/system/docker.service.d \
    && ssh-keygen -A \
    && sed -i 's/^session[[:space:]]\+required[[:space:]]\+pam_loginuid.so/session optional pam_loginuid.so/' /etc/pam.d/sshd

COPY docker/sshd_config /etc/ssh/sshd_config

COPY docker/docker.service.override \
    /etc/systemd/system/docker.service.d/override.conf

RUN sshd -t \
    && systemctl mask \
        systemd-udevd.service \
        systemd-udevd-kernel.socket \
        systemd-udevd-control.socket \
        getty@.service \
        console-getty.service \
    && systemctl enable docker \
    && systemctl enable containerd \
    && systemctl enable ssh \
    && systemctl enable fail2ban

STOPSIGNAL SIGRTMIN+3

CMD ["/sbin/init"]
