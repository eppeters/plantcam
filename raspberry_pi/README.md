# Raspberry Pi Setup for the AWS IoT Timelapse

Included here is an Ansible provisioning playbook that essentially implements
the instructions in [this AWS guide](https://docs.aws.amazon.com/greengrass/latest/developerguide/setup-filter.rpi.html)
after the Pi is ready for remote SSH access.

To use this playbook, follow the guide above until you have fresh Raspbian
install that already has configured wifi, passwordless SSH access (i.e. using
an SSH key), and a user called "pi" (the default Raspbian non-root user) with
passwordless sudo.

Then, install the requirements listed in the parent directory's
`requirements.txt`, and edit `inventory.yaml` to replace the
`greengrass-timelapse-0-onprem` host's IP address with the IP address of your
Pi on your network.

Finally, run `ansible-playbook -i inventory.yaml provision.yaml`. By the end of
it, you should have a setup Raspberry Pi. If you don't, please file an issue
with the full output of the `ggc_depedency_check.sh` script (you can obtain the
output by running the above `ansible-playbook` command again with an additional
`-vvv` option).

## Good things to do

While you're using `raspi-config` to configure your Pi with a
keyboard/mouse/monitor, and before you have SSH access, you may want to do the
following steps in addition to those recommended in the AWS guide above. These
are either recommended or required for using the timelapse IoT solution.

1. Turn on the camera peripheral support.
3. Choose a memorable/recognizable hostname (I used greengrass-timelapse-0).
4. Set the correct default locale for you.
5. Set a high-entropy password for the pi user.
6. Configure WiFi access.
7. Turn off passworded SSH.
8. Ensure the "pi" user can elevate privileges via sudo without a password.
