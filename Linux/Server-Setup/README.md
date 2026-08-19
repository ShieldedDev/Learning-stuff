# Redinext Linux Infrastructure Lab

> **A practical, enterprise-style Linux infrastructure lab using Ubuntu Server, KVM/QEMU, libvirt, Netplan, Linux bridges, SSH, Cockpit, and static networking.**

This guide documents the **current working architecture** of the Redinext lab from the beginning.

It is intentionally written as a learning and operations guide rather than a list of commands to copy blindly. Every major component explains:

- what it is,
- why it is used,
- where it sits in the architecture,
- how to configure it,
- how to verify it,
- and what commonly goes wrong.

The architecture was simplified during development. The earlier design used multiple nested NAT networks and DNAT/port-forwarding rules. Those pieces are **not part of the current design**. The final lab uses one shared `10.10.10.0/24` Layer-2 segment for `redinext`, `web01`, and `db01`.

---

# 1. What We Are Building

The lab uses **nested virtualization**.

There are two virtualization layers:

```text
Physical laptop
│
└── CachyOS Linux
    │
    └── KVM/QEMU + libvirt
        │
        └── redinext
            Ubuntu Server
            │
            └── KVM/QEMU + libvirt
                │
                ├── web01
                │
                └── db01
```

The physical machine is the **L0 host**.

`redinext` is the **L1 infrastructure server/hypervisor**.

`web01` and `db01` are **L2 workload VMs**.

This gives us a small environment that resembles the separation found in real infrastructure:

```text
Hypervisor / Infrastructure
        │
        ├── Web workload
        │
        └── Database / internal workload
```

The lab is suitable for learning:

- Linux administration
- virtualization
- network engineering
- server management
- web infrastructure
- SSH
- storage management
- firewalling
- monitoring
- troubleshooting
- security testing
- infrastructure automation

> **Important:** This is an enterprise-style learning architecture, not a production reference architecture. A real production environment would normally use dedicated hypervisors, redundant networking, centralized identity, monitoring, backups, configuration management, and controlled change management.

---

# 2. Final Architecture

## 2.1 Physical Layer

The physical machine runs CachyOS.

```text
                    Home/Lab Router
                       192.168.0.1
                            │
                         Wi-Fi
                            │
                    ┌───────▼────────┐
                    │    CachyOS     │
                    │ Physical Host  │
                    │                │
                    │ wlan0          │
                    │ 192.168.0.119  │
                    │                │
                    │ KVM + libvirt  │
                    └───────┬────────┘
                            │
                     Lab uplink network
                      10.10.10.0/24
                            │
                    10.10.10.1
                            │
                    ┌───────▼────────┐
                    │    redinext    │
                    │ Ubuntu Server   │
                    │                │
                    │ br-lab         │
                    │ 10.10.10.10    │
                    │                │
                    │ KVM + libvirt  │
                    └───────┬────────┘
                            │
                    ┌───────┴────────┐
                    │  br-lab        │
                    │ 10.10.10.0/24 │
                    └───────┬────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
         ┌──────▼──────┐        ┌──────▼──────┐
         │    web01    │        │    db01     │
         │ Ubuntu      │        │ Ubuntu      │
         │ 10.10.10.20 │        │ 10.10.10.30 │
         └─────────────┘        └─────────────┘
```

## 2.2 Address Plan

| System | Interface | Address | Purpose |
|---|---|---|---|
| Home/Lab Router | LAN | `192.168.0.1/24` | Internet gateway |
| CachyOS | `wlan0` | `192.168.0.119/24` | Physical host |
| Lab gateway on physical host | libvirt bridge/network | `10.10.10.1/24` | Uplink to `redinext` |
| redinext | `br-lab` | `10.10.10.10/24` | L1 hypervisor/server |
| web01 | `enp1s0` | `10.10.10.20/24` | Web workload |
| db01 | `enp1s0` | `10.10.10.30/24` | Internal workload |

The exact physical-host bridge name may be different on another installation. In this lab, the important contract is:

```text
Lab network: 10.10.10.0/24
Gateway:     10.10.10.1
redinext:    10.10.10.10
web01:       10.10.10.20
db01:        10.10.10.30
```

---

# 3. Why We Changed the Original Network Design

The first version of the lab used several independent networks and NAT/DNAT layers.

Conceptually, it looked like:

```text
Physical LAN
    │
    ▼
CatchyOS NAT
    │
    ▼
redinext NAT
    │
    ▼
VM network
```

That design introduced unnecessary routing and troubleshooting complexity.

For example, traffic could pass through:

```text
Client
  ↓
CatchyOS
  ↓
DNAT
  ↓
redinext
  ↓
DNAT
  ↓
VM
```

This made it harder to answer a simple question:

> "Can these three servers communicate with each other?"

The final design deliberately removes that complexity.

All three systems share:

```text
10.10.10.0/24
```

and are attached to the same Linux bridge:

```text
br-lab
```

The result is:

```text
redinext  ─┐
web01     ─┼── br-lab ── 10.10.10.0/24
db01      ─┘
```

No DNAT is required for communication between these systems.

No second internal NAT network is required.

No manual port-forwarding is required.

This is much easier to understand and troubleshoot.

> **Networking principle:** solve the simplest network problem that satisfies the requirement. Add routing, NAT, or DNAT only when the architecture actually requires it.

---

# 4. Important Networking Concept: Wi-Fi vs the Lab Bridge

The physical laptop connects to the Internet through Wi-Fi.

For example:

```text
wlan0
192.168.0.119/24
```

A normal Ethernet bridge directly attached to a Wi-Fi station interface is not a good assumption for a general-purpose lab. Wi-Fi client mode does not behave like a normal switched Ethernet port for arbitrary guest MAC addresses.

That does **not** mean Linux bridges are bad.

It means we should understand where the bridge exists.

Our important bridge is on `redinext`:

```text
enp7s0
   │
   ▼
br-lab
   │
   ├── web01
   └── db01
```

`enp7s0` is a virtual Ethernet interface presented to `redinext` by the outer virtualization layer.

Therefore the inner VMs are not being bridged directly onto `wlan0`.

This distinction is critical.

---

# 5. Layer 0 — Prepare the Physical CachyOS Host

The physical host is responsible for:

- CPU virtualization
- KVM
- QEMU
- libvirt
- the outer virtual network
- running the `redinext` VM

The physical host should **not** be treated as one of the workload servers.

---

# 6. Verify Hardware Virtualization

Check the CPU:

```bash
lscpu | grep -E 'Model name|Virtualization'
```

On Intel hardware, expect something similar to:

```text
Virtualization: VT-x
```

On AMD hardware, the virtualization extension will be different.

Also check:

```bash
ls -l /dev/kvm
```

Expected:

```text
crw-rw---- ... /dev/kvm
```

The exact permissions may vary.

Check loaded KVM modules:

```bash
lsmod | grep kvm
```

On Intel:

```text
kvm_intel
kvm
```

On AMD:

```text
kvm_amd
kvm
```

## Why `/dev/kvm` matters

KVM is a Linux kernel virtualization facility.

QEMU can run as a software emulator, but when QEMU uses KVM it can execute guest CPU instructions using hardware-assisted virtualization.

Conceptually:

```text
Guest OS
   │
QEMU
   │
KVM kernel interface
   │
CPU virtualization extensions
   │
Physical CPU
```

Without KVM acceleration, virtualization can be dramatically slower.

---

# 7. Install KVM/libvirt on CachyOS

CachyOS is Arch-based, so package names follow the Arch ecosystem.

A practical package set is:

```bash
sudo pacman -Syu
sudo pacman -S qemu-desktop libvirt virt-install virt-manager edk2-ovmf dnsmasq
```

## What these packages do

| Package | Purpose |
|---|---|
| `qemu-desktop` | QEMU virtualization/emulation components |
| `libvirt` | Virtualization management framework |
| `virt-install` | CLI tool for creating VMs |
| `virt-manager` | GUI management client |
| `edk2-ovmf` | UEFI firmware for VMs |
| `dnsmasq` | DHCP/DNS support used by libvirt networking |

The exact package set can change as Arch-based distributions evolve. Verify package names against the distribution's current repositories before installation.

---

# 8. Enable libvirt

Enable and start the service:

```bash
sudo systemctl enable --now libvirtd
```

Check:

```bash
systemctl status libvirtd --no-pager
```

Verify that `virsh` exists:

```bash
virsh --version
```

If you get:

```text
command not found
```

the libvirt client tooling is not installed or is not in the current environment.

---

# 9. Configure Administrative Access

Add your user to the relevant groups:

```bash
sudo usermod -aG libvirt "$USER"
sudo usermod -aG kvm "$USER"
```

Then log out and back in.

Verify:

```bash
groups
```

You should see the relevant groups.

> Group membership changes do not always affect the current shell immediately. A new login session is the safest way to verify them.

---

# 10. Validate the Hypervisor

Run:

```bash
sudo virt-host-validate qemu
```

This checks whether the system is suitable for QEMU/KVM.

Also verify:

```bash
ls -l /dev/kvm
lsmod | grep kvm
```

Do not proceed to complex VM creation if the virtualization layer itself is broken.

---

# 11. Create the Outer Lab Network

The physical host needs to provide a virtual network through which `redinext` can communicate with the rest of the lab.

The important network is:

```text
10.10.10.0/24
```

with:

```text
10.10.10.1
```

as the lab gateway.

The exact libvirt network name and bridge name are implementation details.

Check existing networks:

```bash
sudo virsh net-list --all
```

Inspect a network:

```bash
sudo virsh net-dumpxml <network-name>
```

Check the host:

```bash
ip -br addr
ip route
```

You should be able to identify:

```text
Physical Wi-Fi:
192.168.0.x/24

Lab network:
10.10.10.0/24
```

## Why use a separate lab subnet?

It gives us a deterministic network boundary:

```text
Home network
192.168.0.0/24

        │

Lab network
10.10.10.0/24
```

This keeps the infrastructure lab logically separate from the normal home LAN.

---


## 11.1 Example outer libvirt network

A simple outer NAT network can be defined on CachyOS as:

```xml
<network>
  <name>lab-uplink</name>

  <forward mode='nat'/>

  <bridge name='virbr2' stp='on' delay='0'/>

  <ip address='10.10.10.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='10.10.10.100' end='10.10.10.200'/>
    </dhcp>
  </ip>
</network>
```

Save this as:

```text
lab-uplink.xml
```

Define it:

```bash
sudo virsh net-define lab-uplink.xml
```

Start it:

```bash
sudo virsh net-start lab-uplink
```

Enable it at boot:

```bash
sudo virsh net-autostart lab-uplink
```

Verify:

```bash
sudo virsh net-list --all
```

Then:

```bash
ip -br addr
```

You should have a bridge associated with the lab network, for example:

```text
virbr2    UP    10.10.10.1/24
```

The bridge name does not have to be `virbr2`. If it already exists, choose another unused name.

### Why the outer network uses NAT

The physical host is connected through Wi-Fi. Instead of trying to transparently bridge arbitrary VM MAC addresses onto the Wi-Fi station interface, the outer libvirt network provides a normal virtual Ethernet network and performs NAT toward the physical host's Internet connection.

The important path is:

```text
redinext
   │
   ▼
10.10.10.0/24
   │
10.10.10.1
   │
outer libvirt NAT
   │
CachyOS
   │
wlan0
   │
Internet
```

This NAT is **not** the old VM-to-VM NAT design. It is only the outer uplink that gives the lab Internet access.

The nested workload network remains a single shared Layer-2 segment.

### Attach redinext to the outer network

When creating `redinext`, attach one of its virtual NICs to:

```text
lab-uplink
```

Check from CachyOS:

```bash
sudo virsh domiflist redinext
```

Inside `redinext`, identify the corresponding interface:

```bash
ip -br addr
```

In this lab it became:

```text
enp7s0
```

Initially it may receive an address from DHCP, such as:

```text
10.10.10.178/24
```

After the inner bridge is configured, the host address moves to:

```text
br-lab = 10.10.10.10/24
```

and `enp7s0` becomes the bridge member.


# 12. Create the redinext VM

`redinext` is the L1 Ubuntu Server VM.

A reasonable starting allocation on a 16 GB physical machine is:

| Resource | Suggested value |
|---|---:|
| vCPU | 4 |
| RAM | 6–8 GB |
| OS disk | 50–60 GB |
| Network | lab/uplink network |
| Firmware | UEFI or BIOS |

Do not allocate all physical RAM to the hypervisor VM.

For example:

```text
Physical RAM: 16 GB

CachyOS:       ~4–6 GB
redinext:      ~6–8 GB
web01:         ~1–2 GB
db01:          ~1–2 GB
```

The exact allocation depends on workload.

---

# 13. Install Ubuntu Server on redinext

Use an Ubuntu Server LTS release appropriate for the project.

During installation:

```text
Hostname: redinext
```

Install:

```text
OpenSSH Server
```

SSH is important because a server should not depend on a graphical desktop for normal administration.

After installation:

```bash
hostnamectl
ip -br addr
ip route
```

Verify basic connectivity before making static networking changes.

---

# 14. Why OpenSSH Is Installed

OpenSSH provides secure remote administration.

The server component is:

```text
sshd
```

Install it on Ubuntu with:

```bash
sudo apt update
sudo apt install -y openssh-server
```

Check:

```bash
sudo systemctl status ssh --no-pager
```

Test locally:

```bash
ss -lntp | grep ':22'
```

SSH should become the primary management method for a server.

A GUI is useful for occasional console access, but it should not be a dependency for routine administration.

---

# 15. Enable Nested KVM in redinext

Because `redinext` itself is a VM, it must be able to use virtualization extensions.

Inside `redinext`:

```bash
lscpu | grep -E 'Model name|Virtualization'
```

Check for Intel VMX:

```bash
grep -oE 'vmx' /proc/cpuinfo | head
```

Check KVM:

```bash
ls -l /dev/kvm
lsmod | grep kvm
```

For Intel nested virtualization:

```bash
cat /sys/module/kvm_intel/parameters/nested
```

Expected:

```text
Y
```

For AMD, use the corresponding `kvm_amd` module parameter.

## Why this checkpoint matters

The virtualization stack is:

```text
Physical CPU
   ↓
CachyOS
   ↓
KVM
   ↓
QEMU
   ↓
redinext
   ↓
KVM
   ↓
QEMU
   ↓
web01/db01
```

Every layer must work.

A nested VM may appear to boot while still having a broken or unstable nested KVM configuration.

---

# 16. Install KVM/libvirt on redinext

On Ubuntu:

```bash
sudo apt update
sudo apt install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    dnsmasq-base
```

Optional GUI/console tooling:

```bash
sudo apt install -y virt-viewer
```

Check:

```bash
systemctl status libvirtd --no-pager
```

Verify:

```bash
virsh --version
```

Add the administration user:

```bash
sudo adduser "$USER" libvirt
sudo adduser "$USER" kvm
```

Log out and back in.

Then:

```bash
groups
```

---

## 16.1 Package Reference

The following packages are used in the completed lab.

| Package | Layer | Why it is installed |
|---|---|---|
| `qemu-kvm` | Virtualization | QEMU with KVM acceleration for running VMs |
| `libvirt-daemon-system` | Virtualization | System libvirt daemon and integration |
| `libvirt-clients` | Virtualization | Client tools such as `virsh` |
| `virtinst` | Virtualization | `virt-install` and related CLI provisioning tools |
| `cpu-checker` | Diagnostics | Provides `kvm-ok` on Ubuntu |
| `dnsmasq-base` | Networking | Support components used by libvirt networking |
| `virt-viewer` | Management | Graphical VM console viewer |
| `cockpit` | Management | Web-based Linux administration interface |
| `cockpit-machines` | Management | Cockpit integration for libvirt/QEMU VMs |
| `openssh-server` | Remote administration | Provides the `sshd` service |
| `nginx` | Web workload | HTTP/HTTPS web server |
| `ufw` | Host firewall | Simplified firewall management interface |
| `netplan` | Networking | Declarative Ubuntu network configuration layer |

Most Ubuntu Server installations already include Netplan and the basic `iproute2` networking tools.

### Why we do not install everything

A production-style server should follow the principle of **minimum necessary software**.

For example:

```text
redinext:
    virtualization + management + SSH

web01:
    Nginx + SSH

db01:
    only the services required by its role
```

Installing a graphical desktop, database server, VNC server, file server, and development toolchain on every machine would increase the attack surface and make the architecture harder to understand.

# 17. Understand the Virtualization Stack

The packages are not interchangeable.

## KVM

KVM is the kernel-level virtualization mechanism.

```text
Linux kernel
└── KVM
```

It provides hardware-assisted virtualization.

## QEMU

QEMU is the userspace virtual machine emulator/virtualizer.

```text
QEMU
├── virtual CPU
├── virtual memory
├── virtual disks
├── virtual NIC
└── virtual display
```

When QEMU uses KVM, CPU virtualization is accelerated.

## libvirt

libvirt is the management layer.

Instead of manually running long QEMU commands, administrators can use:

```bash
virsh
```

and libvirt manages the VM definition and lifecycle.

The relationship is:

```text
virsh / virt-install / Cockpit / virt-manager
                    │
                 libvirt
                    │
                  QEMU
                    │
                   KVM
                    │
                 Linux
```

This separation is fundamental to understanding the lab.

---

# 18. Validate KVM on redinext

Install the diagnostic tool:

```bash
sudo apt install -y cpu-checker
```

Then:

```bash
kvm-ok
```

A successful result should indicate that KVM acceleration can be used.

Also run:

```bash
sudo virt-host-validate qemu
```

If this fails, stop here and troubleshoot the virtualization layer before creating nested VMs.

---

# 19. Storage Design

VM disks should not be mixed casually with the operating system filesystem.

The intended structure is:

```text
redinext
│
├── OS
│
└── /mnt/vmstore
    ├── images/
    │   ├── web01.qcow2
    │   └── db01.qcow2
    │
    └── iso/
        └── ubuntu-server.iso
```

This makes storage easier to understand, back up, monitor, and expand.

---

# 20. Identify the VM Storage Disk

Always identify disks before formatting them.

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
```

Do **not** assume that:

```text
/dev/vdb
```

is safe to format merely because a previous installation used that name.

Verify:

- disk size,
- device name,
- filesystem,
- mount point.

Only then format a new dedicated disk.

Example:

```bash
sudo mkfs.ext4 /dev/vdb
```

> **Danger:** `mkfs` destroys existing filesystem data on the selected device.

---

# 21. Mount the VM Storage

Create the mount point:

```bash
sudo mkdir -p /mnt/vmstore
```

Mount:

```bash
sudo mount /dev/vdb /mnt/vmstore
```

Verify:

```bash
df -h /mnt/vmstore
findmnt /mnt/vmstore
```

---

# 22. Make VM Storage Persistent

Get the UUID:

```bash
sudo blkid /dev/vdb
```

Add an entry to `/etc/fstab`:

```text
UUID=<UUID> /mnt/vmstore ext4 defaults 0 2
```

Test the configuration without rebooting:

```bash
sudo umount /mnt/vmstore
sudo mount -a
findmnt /mnt/vmstore
```

If `mount -a` fails, fix `/etc/fstab` before rebooting.

---

# 23. Create VM Storage Directories

```bash
sudo mkdir -p /mnt/vmstore/images
sudo mkdir -p /mnt/vmstore/iso
```

Place Ubuntu installation ISOs in:

```text
/mnt/vmstore/iso/
```

VM disks go under:

```text
/mnt/vmstore/images/
```

This avoids putting large VM images inside a user's home directory.

---

# 24. Create a libvirt Storage Pool

A directory-backed libvirt pool can point to the image directory:

```bash
sudo virsh pool-define-as nested-vms dir --target /mnt/vmstore/images
```

Start it:

```bash
sudo virsh pool-start nested-vms
```

Enable automatic startup:

```bash
sudo virsh pool-autostart nested-vms
```

Verify:

```bash
sudo virsh pool-list --all
```

Expected:

```text
Name         State    Autostart
nested-vms   active   yes
```

---

# 25. Why Use a libvirt Storage Pool?

A storage pool gives libvirt a known location for VM storage.

Without a pool, VM disks can be scattered across arbitrary directories.

With a pool:

```text
libvirt
   │
   └── nested-vms
       │
       └── /mnt/vmstore/images
```

This improves administration and makes commands easier to standardize.

---

# 26. The Final Network Design Inside redinext

This is the most important networking section.

`redinext` has two roles:

1. It is a server.
2. It is the hypervisor for `web01` and `db01`.

The nested VMs connect to:

```text
br-lab
```

The bridge has:

```text
10.10.10.10/24
```

The VM addresses are:

```text
web01 = 10.10.10.20/24
db01  = 10.10.10.30/24
```

The gateway is:

```text
10.10.10.1
```

---

# 27. Why We Use a Linux Bridge

A Linux bridge behaves like a software Ethernet switch.

Conceptually:

```text
             br-lab
        ┌──────┼──────┐
        │      │      │
     redinext web01  db01
```

The bridge forwards Ethernet frames between its ports.

A VM's interface is connected to the bridge through a host-side virtual interface such as:

```text
vnet0
vnet1
```

For example:

```text
web01
  │
  │ virtual NIC
  ▼
vnet0
  │
  ▼
br-lab
  │
  ├── redinext
  └── db01
```

---

# 28. The Important Difference Between `br-lab` and a libvirt NAT Network

A libvirt NAT network commonly looks like:

```text
VM
 │
virbr0
 │
NAT
 │
Host
 │
Internet
```

A bridge connection looks like:

```text
VM
 │
vnet0
 │
br-lab
 │
uplink
```

The latter gives the VMs a shared Layer-2 segment.

That is what we want for this lab.

---

# 29. Configure br-lab on redinext

The exact configuration depends on which interface provides the lab uplink.

In this lab, the relevant uplink interface is:

```text
enp7s0
```

and it is attached to:

```text
br-lab
```

Check the current state:

```bash
ip -br addr
```

and:

```bash
bridge link
```

You should see something conceptually similar to:

```text
enp7s0 ... master br-lab
```

The bridge carries the Layer-3 address:

```text
br-lab 10.10.10.10/24
```

The physical/virtual member interface normally does not carry the host's IP address directly.

---

# 30. Understand Bridge Membership

This is a common source of mistakes.

Correct:

```text
enp7s0
   │
   └── master br-lab

br-lab
   └── 10.10.10.10/24
```

Incorrect design:

```text
enp7s0 → 10.10.10.10
br-lab → 10.10.10.10
```

The host's IP belongs to the bridge in a bridged design.

---

# 31. Verify the Bridge

On `redinext`:

```bash
ip -br addr
```

Then:

```bash
bridge link
```

Then:

```bash
ip route
```

The important route should resemble:

```text
10.10.10.0/24 dev br-lab src 10.10.10.10
default via 10.10.10.1 dev br-lab
```

The exact route metrics can differ.

---

# 32. Configure Static Networking on Ubuntu Guests

Ubuntu uses Netplan as its network configuration layer.

The basic model is:

```text
Netplan YAML
    │
    ▼
NetworkManager or systemd-networkd
    │
    ▼
Linux network interfaces
```

For these server VMs, we use a single clear configuration and avoid leaving an older DHCP configuration active alongside the static configuration.

Ubuntu's current documentation describes static addresses, routes, and DNS using Netplan YAML.

---

# 33. Configure web01

First identify the interface:

```bash
ip -br addr
```

In this lab:

```text
enp1s0
```

Create or edit the authoritative Netplan configuration.

For example:

```bash
sudo nano /etc/netplan/01-network-manager-all.yaml
```

Use:

```yaml
network:
  version: 2
  renderer: NetworkManager

  ethernets:
    enp1s0:
      dhcp4: false
      dhcp6: false
      addresses:
        - 10.10.10.20/24
      routes:
        - to: default
          via: 10.10.10.1
      nameservers:
        addresses:
          - 10.10.10.1
          - 1.1.1.1
```

If an older configuration still contains:

```yaml
dhcp4: true
```

do not leave conflicting configurations active.

Back up first:

```bash
sudo cp -a /etc/netplan /etc/netplan.backup
```

Then disable the old configuration if necessary.

Validate:

```bash
sudo netplan generate
```

Apply carefully:

```bash
sudo netplan try
```

Confirm the configuration.

Verify:

```bash
ip -br addr
ip route
```

Expected:

```text
enp1s0    UP    10.10.10.20/24
```

---

# 34. Configure db01

Use the same configuration pattern, but change the address.

```yaml
network:
  version: 2
  renderer: NetworkManager

  ethernets:
    enp1s0:
      dhcp4: false
      dhcp6: false
      addresses:
        - 10.10.10.30/24
      routes:
        - to: default
          via: 10.10.10.1
      nameservers:
        addresses:
          - 10.10.10.1
          - 1.1.1.1
```

Validate:

```bash
sudo netplan generate
```

Apply:

```bash
sudo netplan try
```

Verify:

```bash
ip -br addr
ip route
```

Expected:

```text
enp1s0    UP    10.10.10.30/24
```

---

# 35. Why Static IPs?

Servers need predictable addresses.

Instead of:

```text
web01 → DHCP → unknown address
```

we have:

```text
web01 → 10.10.10.20
db01  → 10.10.10.30
```

That makes:

- SSH administration,
- service configuration,
- monitoring,
- firewall rules,
- DNS,
- security testing,
- documentation

much easier.

In larger environments, static addressing can be replaced or supplemented by DHCP reservations, IPAM, automation, and DNS. Static configuration is appropriate for this small controlled lab.

---

# 36. Attach web01 to br-lab

The VM should have one network interface connected to:

```text
br-lab
```

Check:

```bash
sudo virsh domiflist web01
```

Expected:

```text
Interface  Type    Source  Model   MAC
vnet0      bridge  br-lab  virtio  <MAC>
```

The MAC address must be unique.

---

# 37. Attach db01 to br-lab

Check:

```bash
sudo virsh domiflist db01
```

Expected:

```text
Interface  Type    Source  Model   MAC
vnet1      bridge  br-lab  virtio  <MAC>
```

The actual `vnet` number is not important.

The important fields are:

```text
Type   = bridge
Source = br-lab
Model  = virtio
```

---

# 38. `vnet0` and `vnet1` Explained

The VM does not directly plug into `br-lab`.

The host creates a virtual Ethernet endpoint:

```text
web01
  │
  ▼
vnet0
  │
  ▼
br-lab
```

For another VM:

```text
db01
  │
  ▼
vnet1
  │
  ▼
br-lab
```

When a VM is powered off, its `vnetX` interface may disappear.

When it starts, QEMU/libvirt creates the required host-side interface.

Therefore:

```bash
sudo virsh domiflist web01
```

may show:

```text
-    bridge    br-lab    virtio    ...
```

when the VM is off, but:

```text
vnet0    bridge    br-lab    virtio    ...
```

when it is running.

---

# 39. Verify the Bridge FDB

The bridge maintains a forwarding database.

Check it:

```bash
bridge fdb show br br-lab
```

This lets you inspect learned MAC addresses.

For a specific VM:

```bash
bridge fdb show br br-lab | grep -i '<VM-MAC>'
```

This is useful when troubleshooting Layer-2 connectivity.

---

# 40. Test the Network in the Correct Order

Do not start with DNS.

Start from the lowest useful layer.

## Test 1 — Guest address

On `web01`:

```bash
ip -br addr
```

Expected:

```text
enp1s0    UP    10.10.10.20/24
```

On `db01`:

```text
enp1s0    UP    10.10.10.30/24
```

## Test 2 — Local routing

```bash
ip route
```

## Test 3 — Neighbor discovery

```bash
ip neigh
```

## Test 4 — Gateway

From `web01`:

```bash
ping -c 3 10.10.10.1
```

## Test 5 — redinext

```bash
ping -c 3 10.10.10.10
```

## Test 6 — Other VM

From `web01`:

```bash
ping -c 3 10.10.10.30
```

From `db01`:

```bash
ping -c 3 10.10.10.20
```

## Test 7 — Internet IP

```bash
ping -c 3 1.1.1.1
```

## Test 8 — DNS

```bash
ping -c 3 google.com
```

## Test 9 — HTTPS

```bash
curl -I https://example.com
```

This sequence tells you which layer is failing.

---

# 41. ARP/Neighbor Troubleshooting

If:

```bash
ip neigh
```

shows:

```text
10.10.10.10 dev enp1s0 FAILED
```

or:

```text
10.10.10.1 dev enp1s0 INCOMPLETE
```

the problem is likely below DNS.

Do not immediately modify DNS configuration.

First inspect:

```bash
ip link
bridge link
ip route
```

On `redinext`:

```bash
bridge fdb show br br-lab
```

And capture ARP:

```bash
sudo tcpdump -ni br-lab arp
```

Then generate traffic from the guest:

```bash
ping -c 3 10.10.10.10
```

If no ARP request appears on the bridge, investigate the VM NIC/bridge attachment.

If the request appears but no reply returns, investigate the bridge, host IP configuration, firewall, or gateway.

---

# 42. Why We Do Not Use DNAT Here

DNAT is useful when a service must be published across a network boundary.

Example:

```text
Internet
  │
  ▼
Public IP:8080
  │
 DNAT
  │
  ▼
Internal VM:80
```

That is not necessary for:

```text
web01 ↔ db01
```

because both systems already live on the same subnet.

Adding DNAT would only introduce another failure point.

Therefore this guide intentionally does **not** include the previous DNAT/port-forwarding rules.

---

# 43. Firewall Philosophy

A server should not expose services merely because they are installed.

First identify listening services:

```bash
ss -lntup
```

Then decide which services should be reachable.

For example:

```text
web01:
22/tcp   SSH
80/tcp   HTTP
443/tcp  HTTPS
```

`db01` should expose only services that it actually needs.

---

# 44. UFW on Ubuntu

Ubuntu's common host firewall frontend is UFW.

Check:

```bash
sudo ufw status verbose
```

Install if required:

```bash
sudo apt install -y ufw
```

Before enabling a firewall remotely, ensure SSH is permitted.

For example:

```bash
sudo ufw allow OpenSSH
```

Then enable:

```bash
sudo ufw enable
```

Check:

```bash
sudo ufw status numbered
```

> **Important:** Firewall policy should be designed from the required traffic, not copied blindly. A bad rule can disconnect you from a remote server.

---

# 45. Do Not Mix Firewall Frameworks Casually

Modern Linux systems may use:

```text
nftables
```

while tools such as:

```text
iptables
```

may operate through compatibility layers.

Inspect the active firewall configuration before modifying it:

```bash
sudo nft list ruleset
```

and:

```bash
sudo ufw status verbose
```

If libvirt is managing VM networking, it may also install firewall-related rules.

Do not blindly flush all firewall tables.

That can break:

- VM networking,
- DNS/DHCP,
- host security,
- forwarding,
- libvirt connectivity.

---

# 46. Install Cockpit for Web-Based Management

Cockpit is optional.

The command-line tools remain the primary administration interface.

On Ubuntu:

```bash
sudo apt update
sudo apt install -y cockpit
```

Enable it:

```bash
sudo systemctl enable --now cockpit.socket
```

For VM management:

```bash
sudo apt install -y cockpit-machines
```

Check:

```bash
systemctl status cockpit.socket --no-pager
```

Cockpit uses libvirt/QEMU for its VM management functionality.

---

# 47. What Cockpit Does

Cockpit provides a web-based administration interface for:

- system information,
- services,
- logs,
- storage,
- networking,
- terminal access,
- virtual machines.

The VM functionality is backed by libvirt/QEMU.

Conceptually:

```text
Browser
   │
   ▼
Cockpit
   │
   ▼
libvirt
   │
   ▼
QEMU/KVM
```

Cockpit is therefore a management interface, not a replacement for libvirt.

---

# 48. Accessing Cockpit

Cockpit normally listens on:

```text
TCP/9090
```

Check:

```bash
sudo ss -lntp | grep 9090
```

Access it from a trusted management network:

```text
https://10.10.10.10:9090
```

The exact browser URL depends on how the management network is routed.

Do not expose Cockpit directly to the public Internet unless there is a deliberate security architecture around it.

---

# 49. VM Console and VNC

For graphical VM console access, QEMU can expose a VNC display.

Check:

```bash
sudo virsh domdisplay web01
sudo virsh domdisplay db01
```

Example:

```text
vnc://127.0.0.1:0
vnc://127.0.0.1:2
```

The display number corresponds to the TCP port:

```text
:0 → 5900
:1 → 5901
:2 → 5902
```

The actual ports are determined by the current VM configuration.

---

# 50. Why We Prefer QEMU/libvirt VNC for VM Console Access

A VNC console provided by the hypervisor is different from installing a VNC desktop server inside Ubuntu.

### Hypervisor console

```text
VNC client
   │
   ▼
QEMU
   │
   ▼
Guest display
```

It can show:

- firmware,
- bootloader,
- kernel startup,
- login screen,
- graphical desktop.

It does not depend on the guest's normal remote-desktop stack.

### Guest VNC server

```text
VNC client
   │
   ▼
Guest VNC server
   │
   ▼
GNOME/Xorg/Wayland
```

That introduces additional guest-side dependencies.

For a server lab, the hypervisor console is generally the simpler recovery mechanism.

---

# 51. Secure VNC Access Through SSH

Do not expose QEMU VNC ports unnecessarily.

If QEMU listens only on:

```text
127.0.0.1
```

the VNC socket is local to `redinext`.

From your management workstation, create an SSH tunnel:

```bash
ssh -L 5900:127.0.0.1:5900 vm@10.10.10.10
```

Then use a VNC-capable viewer against:

```text
127.0.0.1:5900
```

For another VM:

```bash
ssh -L 5902:127.0.0.1:5902 vm@10.10.10.10
```

This produces:

```text
Management workstation
        │
        │ encrypted SSH
        ▼
     redinext
        │
        ▼
     QEMU VNC
        │
        ▼
       VM
```

This is preferable to opening raw VNC ports across the network.

---

# 52. virt-viewer

Install:

```bash
sudo apt install -y virt-viewer
```

`virt-viewer` provides a virtualization-focused graphical console client.

It can be used instead of a generic VNC client when appropriate.

On a desktop workstation, install the client there rather than installing a full graphical desktop on the server solely to run the viewer.

---

# 53. Why We Avoid a Full Desktop on redinext

`redinext` is an infrastructure server.

A desktop environment introduces:

- additional packages,
- additional processes,
- additional memory use,
- additional attack surface,
- additional troubleshooting complexity.

The preferred management stack is:

```text
SSH
virsh
Cockpit
journalctl
systemctl
ip
ss
tcpdump
```

Use the VM console when you actually need the VM display.

---

# 54. Create web01

A basic `virt-install` workflow is:

```bash
sudo virt-install \
  --name web01 \
  --memory 2048 \
  --vcpus 2 \
  --disk pool=nested-vms,size=15,format=qcow2,bus=virtio \
  --cdrom /mnt/vmstore/iso/ubuntu-server.iso \
  --network bridge=br-lab,model=virtio \
  --osinfo detect=on \
  --graphics vnc \
  --noautoconsole
```

The exact Ubuntu ISO filename and supported `--osinfo` value depend on the release installed.

Check supported OS variants:

```bash
virt-install --osinfo list
```

If the installer media or `virt-install` version requires a different installation method, follow the current Ubuntu/libvirt guidance rather than forcing a `--location` workflow.

---

# 55. Create db01

Use the same pattern:

```bash
sudo virt-install \
  --name db01 \
  --memory 2048 \
  --vcpus 2 \
  --disk pool=nested-vms,size=20,format=qcow2,bus=virtio \
  --cdrom /mnt/vmstore/iso/ubuntu-server.iso \
  --network bridge=br-lab,model=virtio \
  --osinfo detect=on \
  --graphics vnc \
  --noautoconsole
```

Adjust RAM, CPU, and disk size according to the workload.

---

# 56. Important `virt-install` Options

| Option | Meaning |
|---|---|
| `--name` | VM name |
| `--memory` | RAM allocation |
| `--vcpus` | virtual CPU allocation |
| `--disk` | virtual disk |
| `--network` | VM network attachment |
| `--cdrom` | installation media |
| `--osinfo` | guest OS information |
| `--graphics` | graphical console |
| `--noautoconsole` | do not automatically attach the console |

The most important networking option in this lab is:

```text
--network bridge=br-lab,model=virtio
```

It connects the VM to the existing `br-lab`.

---

# 57. Verify the VM

List VMs:

```bash
sudo virsh list --all
```

Get detailed information:

```bash
sudo virsh dominfo web01
```

Inspect the disk:

```bash
sudo virsh domblklist web01
```

Inspect the network:

```bash
sudo virsh domiflist web01
```

Inspect the complete XML:

```bash
sudo virsh dumpxml web01
```

The XML is the persistent definition libvirt uses for the VM.

---

# 58. Basic VM Lifecycle

Start:

```bash
sudo virsh start web01
```

Shutdown gracefully:

```bash
sudo virsh shutdown web01
```

Force stop:

```bash
sudo virsh destroy web01
```

> `destroy` is equivalent to removing power, not deleting the VM.

Autostart:

```bash
sudo virsh autostart web01
```

Disable autostart:

```bash
sudo virsh autostart web01 --disable
```

---

# 59. Important Difference: `shutdown` vs `destroy`

### `shutdown`

Requests a normal guest shutdown.

```text
Guest OS
   ↓
systemd
   ↓
services stop
   ↓
power off
```

### `destroy`

Immediately stops the VM from the hypervisor side.

```text
QEMU process
   ↓
stopped
```

Use `shutdown` for normal operations.

Use `destroy` only when the guest is unresponsive or a controlled hard power-off is required.

---

# 60. SSH Administration

Once `web01` has:

```text
10.10.10.20
```

connect with:

```bash
ssh dev@10.10.10.20
```

For `db01`:

```bash
ssh dbuser@10.10.10.30
```

Use the actual accounts created during installation.

Check the SSH service:

```bash
sudo systemctl status ssh --no-pager
```

---

# 61. Configure web01 as a Web Server

Install Nginx:

```bash
sudo apt update
sudo apt install -y nginx
```

Check:

```bash
sudo systemctl status nginx --no-pager
```

Test locally:

```bash
curl -I http://127.0.0.1
```

Check the listener:

```bash
ss -lntp | grep ':80'
```

---

# 62. Understand the Nginx Test

If:

```bash
curl -I http://127.0.0.1
```

returns:

```text
HTTP/1.1 200 OK
```

then:

- the local network stack works,
- TCP works,
- port 80 is listening,
- Nginx accepted the request,
- Nginx produced an HTTP response.

If it returns:

```text
403 Forbidden
```

the request still reached Nginx.

That is not primarily a routing problem.

---

# 63. Nginx 403 Troubleshooting

Inspect:

```bash
sudo tail -30 /var/log/nginx/error.log
```

Check:

```bash
sudo ls -la /var/www/html
```

Check every directory component:

```bash
namei -l /var/www/html/index.html
```

If the error indicates that the file cannot be read, inspect ownership and permissions.

For a simple static file:

```bash
sudo chmod 644 /var/www/html/index.html
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Retest:

```bash
curl -I http://127.0.0.1
```

---

# 64. `db01` as an Internal Server

The name `db01` identifies its intended role in this lab.

Keep its externally reachable services minimal.

Possible future services include:

- PostgreSQL
- MariaDB
- MySQL
- Redis
- SFTP
- SMB
- application backend services

Do not install services simply because the package exists.

The principle is:

```text
Requirement
    ↓
Service
    ↓
Listening port
    ↓
Firewall rule
    ↓
Monitoring/logging
```

---

# 65. Server Management Baseline

On every Ubuntu server, learn these commands.

## Identity

```bash
hostnamectl
whoami
id
```

## Processes

```bash
ps aux
top
```

## Memory

```bash
free -h
```

## Storage

```bash
lsblk
df -h
findmnt
```

## Network

```bash
ip -br addr
ip route
ip neigh
```

## Listening services

```bash
ss -lntup
```

## Services

```bash
systemctl status <service>
```

## Logs

```bash
journalctl -u <service>
```

## Kernel messages

```bash
journalctl -k
```

These are foundational Linux administration skills.

---

# 66. Libvirt Management Commands

## VMs

```bash
sudo virsh list --all
```

## Information

```bash
sudo virsh dominfo web01
sudo virsh dominfo db01
```

## Interfaces

```bash
sudo virsh domiflist web01
sudo virsh domiflist db01
```

## Disks

```bash
sudo virsh domblklist web01
sudo virsh domblklist db01
```

## Display

```bash
sudo virsh domdisplay web01
sudo virsh domdisplay db01
```

## XML

```bash
sudo virsh dumpxml web01
```

## Network

```bash
sudo virsh net-list --all
sudo virsh net-info <network>
sudo virsh net-dumpxml <network>
```

## Storage pools

```bash
sudo virsh pool-list --all
sudo virsh pool-info nested-vms
```

---

# 67. Attaching a VM Interface to br-lab

If a VM needs to be attached to the bridge:

```bash
sudo virsh attach-interface \
    web01 \
    bridge \
    br-lab \
    --model virtio \
    --config
```

The `--config` option changes the persistent VM configuration.

For a running VM, live and persistent changes are distinct. Check the current state with:

```bash
sudo virsh domiflist web01
```

If you are unsure whether a change is live, inspect the domain XML and VM state rather than repeatedly attaching interfaces.

---

# 68. Avoid Duplicate VM NICs

A common troubleshooting mistake is repeatedly running:

```bash
virsh attach-interface ...
```

and accidentally creating multiple NICs.

Check:

```bash
sudo virsh domiflist web01
```

A simple server VM should normally have one lab NIC unless there is a specific architectural reason for multiple interfaces.

If you see:

```text
52:54:00:...
52:54:00:...
```

twice, determine whether both interfaces are intentional.

Duplicate NICs can create:

- multiple routes,
- multiple DHCP leases,
- confusing interface names,
- asymmetric routing,
- incorrect default routes,
- difficult ARP troubleshooting.

---

# 69. MAC Addresses

A bridge and a VM NIC should normally have different MAC addresses.

For example:

```text
br-lab:
82:20:d7:87:fd:ac

web01 NIC:
52:54:00:8b:f6:14
```

This is normal.

Think of the bridge as a switch and the VM NIC as a host attached to that switch.

Do not attempt to make their MAC addresses identical.

---

# 70. Troubleshooting a VM With No Network

Use this sequence.

## On the guest

```bash
ip -br addr
ip link
ip route
ip neigh
```

## On redinext

```bash
sudo virsh domiflist web01
bridge link
bridge fdb show br br-lab
```

## Check the bridge address

```bash
ip addr show br-lab
```

## Check routing

```bash
ip route
ip route get 10.10.10.20
```

## Capture traffic

```bash
sudo tcpdump -ni br-lab arp
```

Then generate traffic from the guest:

```bash
ping -c 3 10.10.10.10
```

This gives evidence about whether the packet reaches the bridge.

---

# 71. Troubleshooting With `ip neigh`

Neighbor states are useful.

```text
REACHABLE
```

The neighbor is known and reachable.

```text
STALE
```

The cached information exists but has not recently been confirmed.

```text
INCOMPLETE
```

ARP/neighbor resolution is still waiting for a response.

```text
FAILED
```

Neighbor resolution failed.

For example:

```text
10.10.10.10 dev enp1s0 FAILED
```

means the guest could not resolve the Layer-2 neighbor.

Do not start changing DNS when this is the error.

---

# 72. Packet Capture Methodology

`tcpdump` is one of the most valuable troubleshooting tools in this lab.

Capture ARP:

```bash
sudo tcpdump -ni br-lab arp
```

Capture ICMP:

```bash
sudo tcpdump -ni br-lab icmp
```

Capture HTTP:

```bash
sudo tcpdump -ni br-lab 'tcp port 80'
```

Capture SSH:

```bash
sudo tcpdump -ni br-lab 'tcp port 22'
```

Capture everything between two hosts:

```bash
sudo tcpdump -ni br-lab host 10.10.10.20
```

The goal is not to "run tcpdump until something works."

The goal is to answer:

```text
Did the packet leave?
Did it reach the interface?
Did the destination respond?
Where did the packet disappear?
```

---

# 73. Troubleshooting by Layers

Use this model:

```text
Layer 7  Application
         Nginx / SSH / DNS

Layer 4  TCP / UDP
         ports / sockets

Layer 3  IP
         address / routing

Layer 2  Ethernet
         MAC / ARP / bridge

Layer 1  Link
         interface state
```

Example:

```text
google.com fails
```

Do not immediately assume DNS.

Test:

```bash
ping -c 3 1.1.1.1
```

If that works:

```bash
ping -c 3 google.com
```

If the IP works but the name fails, investigate DNS.

---

# 74. Common Failure: `virsh: command not found`

Install the client tooling.

On Ubuntu:

```bash
sudo apt install -y libvirt-clients
```

and the VM creation tooling:

```bash
sudo apt install -y virtinst
```

Verify:

```bash
virsh --version
virt-install --version
```

---

# 75. Common Failure: Libvirt Network Is Inactive

Check:

```bash
sudo virsh net-list --all
```

If the required network is inactive:

```bash
sudo virsh net-start <network>
```

For automatic startup:

```bash
sudo virsh net-autostart <network>
```

However, this applies only to libvirt-managed networks.

`br-lab` in this architecture is an externally managed Linux bridge. Do not confuse it with a libvirt NAT network.

---

# 76. Common Failure: VM Interface Shows `-`

If:

```bash
sudo virsh domiflist web01
```

shows:

```text
-    bridge    br-lab    virtio
```

while the VM is shut down, that can be normal.

After starting:

```bash
sudo virsh start web01
```

check again.

A running VM should normally show a host-side interface such as:

```text
vnet0
```

Then:

```bash
bridge link
```

should show that interface attached to:

```text
br-lab
```

---

# 77. Common Failure: No Internet but Local Network Works

Test:

```bash
ping -c 3 10.10.10.10
```

Then:

```bash
ping -c 3 10.10.10.1
```

Then:

```bash
ping -c 3 1.1.1.1
```

Then:

```bash
ping -c 3 google.com
```

Interpretation:

| Result | Likely area |
|---|---|
| `.10` fails | local VM/bridge |
| `.10` works, `.1` fails | gateway/uplink |
| `.1` works, `1.1.1.1` fails | routing/NAT/upstream |
| `1.1.1.1` works, `google.com` fails | DNS |
| all work | network is probably healthy |

---

# 78. Common Failure: GUI Blank Screen

For infrastructure servers, the GUI is not the primary administration path.

Check the VM from the host:

```bash
sudo virsh domdisplay web01
```

Check the VM's graphics XML:

```bash
sudo virsh dumpxml web01 | grep -A10 -B2 '<graphics'
```

Check the virtual GPU:

```bash
sudo virsh dumpxml web01 | grep -A8 '<video'
```

Inside the guest:

```bash
lspci -k | grep -A3 -Ei 'vga|3d|display'
```

If the server's graphical environment is broken, use:

```text
SSH
virsh console
Cockpit
QEMU VNC
```

rather than repeatedly reinstalling the desktop.

---

# 79. Common Failure: GNOME Consumes Resources

A server does not require GNOME merely because it is a VM.

Check resource usage:

```bash
free -h
ps -eo pid,comm,%cpu,%mem --sort=-%mem | head
```

A graphical environment consumes memory and CPU and introduces more software.

For infrastructure work, a server installation is generally preferable.

---

# 80. Backups and Snapshots

VM storage is data.

Before major changes:

```bash
sudo virsh snapshot-list web01
```

For supported configurations, snapshots can be used carefully.

Do not treat snapshots as a complete backup strategy.

A backup should provide:

- independent storage,
- known retention,
- integrity checks,
- restoration testing.

A snapshot stored on the same disk does not protect against disk failure.

---

# 81. Basic Operational Discipline

Before changing anything:

```text
1. What is broken?
2. What should the expected state be?
3. Which layer owns the problem?
4. What command proves the current state?
5. What exactly am I changing?
6. How will I verify it?
7. How will I undo it?
```

This is more important than memorizing commands.

---

# 82. Change One Thing at a Time

Avoid this:

```text
Change Netplan
Change firewall
Restart libvirt
Change bridge
Restart NetworkManager
Reboot
```

If the problem disappears, you do not know which change fixed it.

Prefer:

```text
Observe
  ↓
Hypothesis
  ↓
One change
  ↓
Test
  ↓
Record result
```

This is the same methodology used in real infrastructure troubleshooting.

---

# 83. Final Validation Checklist

## Physical host

```bash
lscpu | grep Virtualization
ls -l /dev/kvm
lsmod | grep kvm
systemctl status libvirtd --no-pager
```

## redinext

```bash
hostnamectl
ip -br addr
ip route
ls -l /dev/kvm
kvm-ok
sudo virt-host-validate qemu
```

## Bridge

```bash
ip addr show br-lab
bridge link
bridge fdb show br br-lab
```

## VMs

```bash
sudo virsh list --all
sudo virsh domiflist web01
sudo virsh domiflist db01
```

## web01

```bash
ip -br addr
ip route
ping -c 3 10.10.10.10
ping -c 3 10.10.10.30
curl -I http://127.0.0.1
```

## db01

```bash
ip -br addr
ip route
ping -c 3 10.10.10.10
ping -c 3 10.10.10.20
```

## Management

```bash
systemctl status ssh --no-pager
systemctl status cockpit.socket --no-pager
```

---

# 84. Final Architecture Summary

The finished lab should look like:

```text
                         INTERNET
                            │
                     Home/Lab Router
                      192.168.0.1
                            │
                         Wi-Fi
                            │
                    ┌───────▼────────┐
                    │    CachyOS     │
                    │ Physical Host  │
                    │ 192.168.0.x    │
                    │                │
                    │ KVM + libvirt  │
                    └───────┬────────┘
                            │
                     Lab uplink
                    10.10.10.0/24
                            │
                     10.10.10.1
                            │
                    ┌───────▼────────┐
                    │    redinext    │
                    │ Ubuntu Server  │
                    │ 10.10.10.10    │
                    │                │
                    │ br-lab         │
                    │ KVM + libvirt  │
                    │ Cockpit        │
                    │ SSH            │
                    └───────┬────────┘
                            │
                       br-lab L2
                    10.10.10.0/24
                            │
                 ┌──────────┴──────────┐
                 │                     │
          ┌──────▼──────┐       ┌──────▼──────┐
          │    web01    │       │    db01     │
          │10.10.10.20  │       │10.10.10.30  │
          │             │       │             │
          │    Nginx    │       │ Internal    │
          │    SSH      │       │ Services    │
          └─────────────┘       └─────────────┘
```

The key design decision is:

```text
ONE SHARED LAB SUBNET
10.10.10.0/24

redinext  → 10.10.10.10
web01     → 10.10.10.20
db01      → 10.10.10.30

all attached to:

br-lab
```

This is deliberately simpler than the original multi-NAT/DNAT architecture.

---

# 85. Recommended Next Steps

Once the base infrastructure is stable, build functionality in layers.

## Phase 1 — Linux Administration

- [ ] Users and groups
- [ ] File ownership
- [ ] Permissions
- [ ] ACLs
- [ ] systemd
- [ ] journald
- [ ] SSH keys
- [ ] SSH hardening
- [ ] Bash administration

## Phase 2 — Virtualization

- [ ] VM templates
- [ ] snapshots
- [ ] cloning
- [ ] storage pools
- [ ] resource limits
- [ ] VM autostart
- [ ] Cockpit
- [ ] virt-viewer

## Phase 3 — Networking

- [ ] Linux bridges
- [ ] VLANs
- [ ] routing
- [ ] nftables
- [ ] DNS
- [ ] DHCP
- [ ] network segmentation
- [ ] packet capture

## Phase 4 — Web Infrastructure

- [ ] Nginx virtual hosts
- [ ] HTTPS
- [ ] TLS certificates
- [ ] reverse proxying
- [ ] access/error logs
- [ ] security headers
- [ ] service hardening

## Phase 5 — Database/Internal Services

- [ ] PostgreSQL or MariaDB
- [ ] database users
- [ ] authentication
- [ ] service binding
- [ ] firewall restrictions
- [ ] backups
- [ ] restore testing

## Phase 6 — Operations

- [ ] monitoring
- [ ] centralized logs
- [ ] automated backups
- [ ] configuration management
- [ ] health checks
- [ ] alerting
- [ ] disaster recovery testing

## Phase 7 — Security

- [ ] SSH hardening
- [ ] service enumeration
- [ ] firewall testing
- [ ] network segmentation validation
- [ ] vulnerability assessment
- [ ] attack-path analysis
- [ ] hardening verification
- [ ] incident-response exercises

---

# 86. Reference Documentation

Use primary documentation whenever possible.

## Ubuntu Server

- [Ubuntu Server documentation](https://documentation.ubuntu.com/server/)
- [Ubuntu virtualization documentation](https://ubuntu.com/server/docs/how-to/virtualisation/)
- [Ubuntu libvirt guide](https://documentation.ubuntu.com/server/how-to/virtualisation/libvirt/)
- [Ubuntu QEMU guide](https://ubuntu.com/server/docs/how-to/virtualisation/qemu/)
- [Ubuntu VM tooling](https://ubuntu.com/server/docs/how-to/virtualisation/virtual-machine-manager/)
- [Ubuntu networking](https://documentation.ubuntu.com/server/explanation/networking/configuring-networks/)
- [Ubuntu OpenSSH](https://documentation.ubuntu.com/server/how-to/security/openssh-server/)
- [Ubuntu firewall/UFW](https://documentation.ubuntu.com/server/how-to/security/firewalls/)

## Netplan

- [Netplan documentation](https://netplan.readthedocs.io/)
- [Netplan static IP configuration](https://netplan.readthedocs.io/en/stable/using-static-ip-addresses/)

## libvirt

- [libvirt documentation](https://www.libvirt.org/docs/)
- [libvirt networking](https://www.libvirt.org/formatnetwork.html)
- [libvirt domain XML](https://www.libvirt.org/formatdomain.html)
- [virsh reference](https://www.libvirt.org/manpages/virsh.html)

## QEMU

- [QEMU documentation](https://www.qemu.org/docs/master/)
- [QEMU VNC](https://www.qemu.org/docs/master/system/qemu-manpage.html)
- [QEMU virtio-GPU](https://www.qemu.org/docs/master/system/devices/virtio/virtio-gpu.html)

## Arch/CachyOS

- [ArchWiki — Libvirt](https://wiki.archlinux.org/title/Libvirt)
- [CachyOS documentation](https://wiki.cachyos.org/)

## Cockpit

- [Cockpit Virtual Machines](https://cockpit-project.org/guide/latest/feature-virtualmachines)

---

# 87. Final Engineering Checklist

Before calling the lab "complete", verify that you can explain all of the following without copying a command from this document:

### Virtualization

- What KVM does
- What QEMU does
- What libvirt does
- What `virsh` does
- What `virt-install` does
- What nested virtualization means
- Why `/dev/kvm` matters

### Networking

- What a Layer-2 bridge is
- What `br-lab` does
- What `vnet0` and `vnet1` are
- Why the VM MAC and bridge MAC are different
- Why ARP must work before normal IPv4 communication
- What a default route does
- What DNS does
- Why the old DNAT design was unnecessary

### Linux

- How systemd manages services
- Where logs are stored
- How permissions work
- How SSH works
- How to inspect processes
- How to inspect sockets
- How to inspect routes

### Operations

- How to start and stop a VM
- How to inspect VM XML
- How to inspect VM disks
- How to inspect VM interfaces
- How to troubleshoot a broken network
- How to use `tcpdump`
- How to verify a change
- How to back out a change

---

# 88. The Most Important Lesson

The goal of this lab is not to memorize:

```bash
virsh ...
ip ...
systemctl ...
netplan ...
```

The goal is to understand the system underneath those commands.

When something fails, ask:

```text
What should the system look like?
        ↓
What actually exists?
        ↓
Which layer is different?
        ↓
What evidence proves it?
        ↓
What is the smallest safe change?
        ↓
How do I verify the result?
```

That is the transferable skill.

The same reasoning applies to:

- Linux servers
- virtualization
- enterprise networks
- cloud infrastructure
- DevOps
- penetration testing
- incident response
- security engineering

A good infrastructure engineer does not merely know commands.

A good infrastructure engineer knows **why the command is necessary, what it changes, what can break, and how to prove whether it worked.**
