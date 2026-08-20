# Linux Infrastructure Lab

> **A practical, enterprise-style Linux infrastructure lab using Ubuntu Server, KVM/QEMU, libvirt, Netplan, Linux bridges, SSH, Cockpit, and static networking.**

This guide documents the **current working architecture** of the Redinext lab from the beginning.

It is intentionally written as a learning and operations guide rather than a list of commands to copy blindly. Every major component explains:

- what it is,
- why it is used,
- where it sits in the architecture,
- how to configure it,
- how to verify it,
- and what commonly goes wrong.

The final network design uses an outer libvirt network on the physical CachyOS host and an inner Linux bridge on `redinext`. This keeps the lab simple while still giving the nested VMs a shared Layer-2 network.

---

# 1. What We Are Building

The lab uses **nested virtualization**.

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

The environment is suitable for learning:

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

The final design has **two virtualization/networking layers**.

The physical CachyOS host provides the **outer lab network**.

`redinext` then provides the **inner VM bridge**.

The important point is that the `10.10.10.0/24` network is intentionally carried from the physical host's libvirt network into `redinext`, and then through `br-lab` to `web01` and `db01`.

## 2.1 Physical Layer

```text
                         Home Router
                         192.168.0.1
                              │
                            Wi-Fi
                              │
                    ┌─────────▼─────────┐
                    │      CachyOS      │
                    │   Physical Host   │
                    │                   │
                    │ wlan0             │
                    │ 192.168.0.119     │
                    │                   │
                    │ KVM + QEMU        │
                    │ libvirt           │
                    └─────────┬─────────┘
                              │
                    libvirt network: labnet
                              │
                       ┌──────▼──────┐
                       │   virbr2    │
                       │ 10.10.10.1  │
                       │   gateway   │
                       └──────┬──────┘
                              │
                         vnet3 on
                         CachyOS
                              │
                    ┌─────────▼─────────┐
                    │     redinext      │
                    │   Ubuntu Server   │
                    │                   │
                    │ enp7s0            │
                    │       │           │
                    │       ▼           │
                    │     br-lab        │
                    │  10.10.10.10/24   │
                    │                   │
                    │ KVM + QEMU        │
                    │ libvirt           │
                    └─────────┬─────────┘
                              │
                       br-lab L2 bridge
                              │
                    ┌─────────┴─────────┐
                    │                   │
               ┌────▼─────┐       ┌────▼─────┐
               │  web01   │       │   db01   │
               │ Ubuntu   │       │ Ubuntu   │
               │ .10.10.20│       │ .10.10.30│
               └──────────┘       └──────────┘
```

There are therefore **two different bridge devices with different jobs**:

| Device | Where | Address | Purpose |
|---|---|---:|---|
| `virbr0` | CachyOS | `192.168.122.1/24` | libvirt default network; not part of our lab path |
| `virbr2` | CachyOS | `10.10.10.1/24` | `labnet` gateway/uplink for the nested lab |
| `br-lab` | redinext | `10.10.10.10/24` | Inner bridge connecting `redinext`, `web01`, and `db01` |

> **Important:** `virbr2` and `br-lab` are not the same Linux bridge. They are connected through `redinext`'s virtual NIC. `virbr2` is the outer libvirt network; `br-lab` is the inner bridge.

## 2.2 The Two NICs of redinext

In the completed setup, `redinext` can have two virtual NICs on the CachyOS host.

Check them with:

```bash
sudo virsh domiflist redinext
```

The relevant result looks conceptually like:

```text
Interface  Type     Source   Model   MAC
vnet2      network  default  virtio  <MAC>
vnet3      network  labnet  virtio  <MAC>
```

The corresponding guest-side interfaces are typically:

```text
redinext
├── enp1s0 → default libvirt network
│            192.168.122.0/24
│
└── enp7s0 → labnet
             10.10.10.0/24
             │
             ▼
           br-lab
```

The exact interface names can vary. Always verify with:

```bash
ip -br addr
```

and:

```bash
sudo virsh domiflist redinext
```

The **lab path** is the important one:

```text
CachyOS virbr2
      │
   vnet3
      │
redinext enp7s0
      │
   br-lab
      │
 ┌────┴────┐
web01    db01
.20        .30
```

## 2.3 Address Plan

| System | Interface / Device | Address | Purpose |
|---|---|---:|---|
| Home Router | LAN | `192.168.0.1/24` | Internet gateway |
| CachyOS | `wlan0` | `192.168.0.119/24` | Physical host |
| CachyOS | `virbr0` | `192.168.122.1/24` | libvirt default network |
| CachyOS | `virbr2` | `10.10.10.1/24` | `labnet` gateway |
| redinext | `br-lab` | `10.10.10.10/24` | L1 server/hypervisor |
| web01 | `enp1s0` | `10.10.10.20/24` | Web workload |
| db01 | `enp1s0` | `10.10.10.30/24` | Database/internal workload |

The critical lab addressing is:

```text
Network:  10.10.10.0/24
Gateway:  10.10.10.1
redinext: 10.10.10.10
web01:    10.10.10.20
db01:     10.10.10.30
```

---

# 3. Why We Changed the Original Network Design

The original design became unnecessarily complicated because we introduced multiple internal virtual networks and DNAT/port-forwarding rules.

The final design separates two requirements:

1. **Outer connectivity:** give the nested lab access to the physical host's network/Internet.
2. **Inner connectivity:** put `redinext`, `web01`, and `db01` on the same `10.10.10.0/24` Layer-2 segment.

We solve those requirements with two layers.

## Outer layer — CachyOS

CachyOS runs a libvirt network named:

```text
labnet
```

with:

```text
virbr2 = 10.10.10.1/24
```

This network provides the gateway and NAT toward the physical host's Wi-Fi connection.

The path is:

```text
web01/db01
    │
    ▼
10.10.10.1
    │
  virbr2
    │
libvirt NAT
    │
  CachyOS
    │
  wlan0
    │
Internet
```

## Inner layer — redinext

`redinext` receives a virtual NIC from `labnet`.

Inside `redinext`, that NIC is attached to:

```text
br-lab
```

The inner VMs also attach to `br-lab`.

Therefore:

```text
                10.10.10.0/24
                      │
                 ┌────┴────┐
                 │ br-lab  │
                 └────┬────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
      redinext       web01       db01
       .10            .20         .30
```

The three systems can communicate directly at Layer 2.

## What we removed

We do **not** use:

- DNAT for access between the lab systems
- a second internal NAT network inside `redinext`
- manual port-forwarding for normal lab communication
- separate subnets for `web01` and `db01`

## What we still use

We **do still use one NAT boundary**:

```text
CachyOS labnet/virbr2
```

That NAT is only the **outer Internet/uplink boundary**.

It is not an internal VM-to-VM NAT design.

> **Important terminology:** "No DNAT" does not mean "no NAT anywhere." The final design uses the standard libvirt NAT behavior on the outer `labnet` network, while the workload VMs share a simple Layer-2 network behind it.

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

The physical host is the foundation of the entire environment.

It runs:

- CachyOS Linux
- KVM
- QEMU
- libvirt
- the outer `labnet` network

Check the host:

```bash
cat /etc/os-release
uname -r
```

Check networking:

```bash
ip -br addr
ip route
```

For example:

```text
wlan0    UP    192.168.0.119/24
```

Verify Internet access before changing virtualization networking:

```bash
ping -c 3 1.1.1.1
ping -c 3 google.com
```

Do not begin virtualization troubleshooting until the physical host itself has working connectivity.

---

# 6. Verify Hardware Virtualization

Check CPU virtualization support:

```bash
lscpu | grep -i virtualization
```

Also check:

```bash
grep -E 'vmx|svm' /proc/cpuinfo | head
```

Intel systems normally expose:

```text
vmx
```

AMD systems normally expose:

```text
svm
```

Check KVM:

```bash
ls -l /dev/kvm
```

A working system should expose `/dev/kvm`.

## Why `/dev/kvm` matters

`/dev/kvm` is the interface used by user-space virtualization software to communicate with the Linux KVM subsystem.

The simplified model is:

```text
QEMU
  │
  ▼
/dev/kvm
  │
  ▼
Linux KVM
  │
  ▼
CPU virtualization extensions
```

---

# 7. Install KVM/libvirt on CachyOS

Install the required virtualization packages using the current CachyOS/Arch package names.

The exact package set can change with distribution versions, so verify package availability with:

```bash
pacman -Ss qemu
pacman -Ss libvirt
```

The core components are:

```text
QEMU
libvirt
virt-install
virt-viewer
```

Typical installation:

```bash
sudo pacman -Syu
sudo pacman -S qemu-desktop libvirt virt-install virt-viewer
```

Check versions:

```bash
qemu-system-x86_64 --version
virsh version
virt-install --version
```

## What these packages do

### QEMU

Provides the virtual machine/device model.

### libvirt

Provides the management API and infrastructure for defining and controlling VMs, networks and storage.

### virt-install

Creates/provisions libvirt-managed virtual machines.

### virt-viewer

Provides a graphical console client for VM displays.

---

# 8. Enable libvirt

Enable the libvirt services appropriate for the installed version.

First inspect:

```bash
systemctl list-unit-files | grep -E 'libvirt|virtqemud|virtnetworkd'
```

Then enable the relevant service(s).

On systems using the traditional daemon:

```bash
sudo systemctl enable --now libvirtd
```

Verify:

```bash
systemctl status libvirtd --no-pager
```

On modular libvirt installations, services such as `virtqemud` and `virtnetworkd` may be used instead.

The important thing is to verify the active libvirt stack rather than assuming one daemon name.

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

Group membership changes do not always affect the current shell immediately. A new login session is the safest way to verify them.

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

The physical CachyOS host provides the **outer network** for the nested infrastructure.

This is where the `10.10.10.0/24` network actually begins.

We created a libvirt network named:

```text
labnet
```

and assigned it the Linux bridge:

```text
virbr2
```

with:

```text
10.10.10.1/24
```

The exact bridge number is not important in general. On this installation it is `virbr2`.

## 11.1 Understand `virbr0` vs `virbr2`

After libvirt is installed, you may already have a default network:

```text
default
   │
virbr0
   │
192.168.122.1/24
```

This is the standard libvirt NAT network.

Our lab network is separate:

```text
labnet
   │
virbr2
   │
10.10.10.1/24
```

The two networks serve different purposes.

| Network | Bridge | Subnet | Role |
|---|---|---|---|
| `default` | `virbr0` | `192.168.122.0/24` | Default libvirt network |
| `labnet` | `virbr2` | `10.10.10.0/24` | Our nested infrastructure network |

Do not confuse:

```text
virbr0 ≠ virbr2
```

and do not assume the bridge number will be the same on another host.

## 11.2 Verify the network on CachyOS

List libvirt networks:

```bash
sudo virsh net-list --all
```

Inspect the lab network:

```bash
sudo virsh net-info labnet
```

Dump its configuration:

```bash
sudo virsh net-dumpxml labnet
```

Inspect the bridge directly:

```bash
ip -br addr show virbr2
```

Expected:

```text
virbr2    UP    10.10.10.1/24
```

The exact MAC address and other flags are not important for the basic design.

## 11.3 Example `labnet` configuration

A representative libvirt configuration is:

```xml
<network>
  <name>labnet</name>

  <forward mode='nat'/>

  <bridge name='virbr2' stp='on' delay='0'/>

  <ip address='10.10.10.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='10.10.10.100' end='10.10.10.200'/>
    </dhcp>
  </ip>
</network>
```

The actual persistent XML on your machine is authoritative. Inspect it with:

```bash
sudo virsh net-dumpxml labnet
```

Do not blindly replace an existing network definition simply because the bridge is named differently.

## 11.4 Why `virbr2` is the gateway

The address:

```text
10.10.10.1
```

belongs to the outer libvirt network.

It is therefore the default gateway used by systems that need to leave the `10.10.10.0/24` lab network.

For example:

```text
web01
10.10.10.20
      │
      │ default route
      ▼
10.10.10.1
      │
    virbr2
      │
   NAT/uplink
      │
   CachyOS
      │
    wlan0
      │
   Internet
```

This is why `web01` and `db01` can use:

```text
default via 10.10.10.1
```

without making `redinext` a router.

## 11.5 Attach redinext to `labnet`

On CachyOS:

```bash
sudo virsh domiflist redinext
```

The lab interface should appear conceptually as:

```text
Interface  Type     Source  Model
vnet3      network  labnet  virtio
```

The `vnet3` number is not guaranteed. It is simply the host-side interface created for that VM NIC.

Inside `redinext`, identify the corresponding interface:

```bash
ip -br addr
```

In our installation it became:

```text
enp7s0
```

That interface is then placed into the inner bridge:

```text
enp7s0
   │
   ▼
br-lab
```

The resulting path is:

```text
CachyOS
   │
virbr2 / labnet
10.10.10.1
   │
vnet3
   │
redinext enp7s0
   │
br-lab
10.10.10.10
   │
 ┌─┴─────────┐
web01       db01
.20          .30
```

## 11.6 Why the outer network uses NAT

The physical host connects to the Internet through Wi-Fi.

The outer libvirt network provides a controlled virtual Ethernet network and performs NAT toward the host's uplink.

This avoids trying to transparently bridge arbitrary guest MAC addresses directly through the Wi-Fi station interface.

The outer NAT boundary is therefore intentional:

```text
10.10.10.0/24
       │
    virbr2
       │
     NAT
       │
CachyOS wlan0
       │
   192.168.0.0/24
       │
   Home router
```

This is the only NAT boundary required for the current architecture.

## 11.7 Verify the complete outer path

On CachyOS:

```bash
ip -br addr show virbr2
```

```bash
sudo virsh domiflist redinext
```

```bash
ping -c 3 10.10.10.1
```

Then from `redinext`:

```bash
ip -br addr
```

```bash
ping -c 3 10.10.10.1
```

Then:

```bash
ping -c 3 1.1.1.1
```

If these work, the outer network is functioning before the inner VMs are introduced.

---

# 12. Create the redinext VM

`redinext` is the L1 Ubuntu Server VM.

A reasonable starting allocation on a 16 GB physical machine is:

| Resource | Suggested value |
|---|---:|
| vCPU | 4 |
| RAM | 6–8 GB |
| OS disk | 50–60 GB |
| Network | `labnet` |
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

Because `redinext` itself is a VM, it must be able to use virtualization extensions exposed by the outer hypervisor.

On CachyOS, inspect the VM CPU configuration:

```bash
sudo virsh dumpxml redinext | grep -A8 '<cpu'
```

Inside `redinext`:

```bash
lscpu | grep -i virtualization
```

Check:

```bash
ls -l /dev/kvm
```

A working nested setup should expose `/dev/kvm` inside `redinext`.

---

# 16. Install KVM/libvirt on redinext

Install the virtualization stack inside Ubuntu Server.

Typical packages include:

```bash
sudo apt update
sudo apt install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    bridge-utils
```

Depending on the Ubuntu release and intended workflow, additional packages may be useful, such as:

```bash
virt-viewer
```

Check:

```bash
virsh version
virt-install --version
qemu-system-x86_64 --version
```

## 16.1 Package Reference

### `qemu-kvm`

Provides QEMU with KVM acceleration support.

### `libvirt-daemon-system`

Provides system-level libvirt services.

### `libvirt-clients`

Provides tools such as:

```bash
virsh
```

### `virtinst`

Provides:

```bash
virt-install
```

### `bridge-utils`

Provides traditional bridge utilities. Modern Linux administration can also use `ip` and `bridge` directly.

> Do not install packages simply because they appear in a tutorial. Install the smallest set required for the architecture and verify what each package provides.

---

# 17. Understand the Virtualization Stack

The architecture is:

```text
Management tools
       │
       ▼
     libvirt
       │
       ▼
      QEMU
       │
       ▼
      KVM
       │
       ▼
CPU virtualization hardware
```

### KVM

Kernel subsystem that provides hardware-assisted virtualization.

### QEMU

User-space virtual machine monitor and device model.

### libvirt

Management API/framework.

### virsh

CLI client for libvirt.

### virt-install

VM provisioning tool.

This separation matters when troubleshooting.

---

# 18. Validate KVM on redinext

Run:

```bash
sudo virt-host-validate qemu
```

Then:

```bash
ls -l /dev/kvm
```

Then:

```bash
lsmod | grep kvm
```

You should see the relevant KVM modules.

If `/dev/kvm` is missing, stop here and troubleshoot nested virtualization before creating VMs.

---

# 19. Storage Design

Keep VM storage separate from the Ubuntu root filesystem when practical.

Example:

```text
/mnt/vmstore/
└── images/
    ├── web01.qcow2
    └── db01.qcow2
```

This makes:

- capacity management,
- backups,
- snapshots,
- disk replacement,
- monitoring

easier.

---

# 20. Identify the VM Storage Disk

Inspect block devices:

```bash
lsblk -f
```

Look for the dedicated disk/partition.

Do not format a disk until you have confirmed its identity.

Useful commands:

```bash
lsblk
lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINTS
sudo blkid
```

---

# 21. Mount the VM Storage

Create a mount point:

```bash
sudo mkdir -p /mnt/vmstore
```

Format the dedicated filesystem only after confirming the correct device.

Mount it:

```bash
sudo mount /dev/<device> /mnt/vmstore
```

Verify:

```bash
df -h /mnt/vmstore
```

---

# 22. Make VM Storage Persistent

Get the UUID:

```bash
sudo blkid /dev/<device>
```

Add an entry to:

```bash
sudo nano /etc/fstab
```

Prefer UUID-based mounting.

Example:

```text
UUID=<filesystem-uuid> /mnt/vmstore ext4 defaults,noatime 0 2
```

Test:

```bash
sudo mount -a
```

If there are no errors:

```bash
findmnt /mnt/vmstore
```

---

# 23. Create VM Storage Directories

```bash
sudo mkdir -p /mnt/vmstore/images
sudo mkdir -p /mnt/vmstore/iso
```

Verify:

```bash
ls -lah /mnt/vmstore
```

---

# 24. Create a libvirt Storage Pool

Define a directory-backed pool:

```bash
sudo virsh pool-define-as \
    nested-vms \
    dir \
    --target /mnt/vmstore/images
```

Start it:

```bash
sudo virsh pool-start nested-vms
```

Enable autostart:

```bash
sudo virsh pool-autostart nested-vms
```

Verify:

```bash
sudo virsh pool-list --all
```

---

# 25. Why Use a libvirt Storage Pool?

A storage pool gives libvirt a known storage location.

Instead of manually tracking:

```text
/mnt/vmstore/images/web01.qcow2
```

you can ask libvirt:

```bash
virsh pool-list --all
virsh vol-list nested-vms
```

This is particularly useful as the lab grows.

---

# 26. The Final Network Design Inside redinext

`redinext` is an L1 hypervisor, but it is **not the gateway for the lab subnet**.

The gateway remains:

```text
10.10.10.1
```

on the physical host's `virbr2`/`labnet`.

`redinext` provides the Layer-2 bridge that connects its own lab interface to the nested VMs.

The inner path is:

```text
CachyOS
  │
virbr2 / labnet
10.10.10.1
  │
vnet3
  │
redinext
enp7s0
  │
br-lab
10.10.10.10
  │
 ├── vnet0 → web01 → 10.10.10.20
 │
 └── vnet1 → db01  → 10.10.10.30
```

This is an important distinction:

```text
10.10.10.1  = outer lab gateway
10.10.10.10 = redinext host/bridge address
10.10.10.20 = web01
10.10.10.30 = db01
```

All four addresses belong to the same IPv4 subnet:

```text
10.10.10.0/24
```

The bridge allows Ethernet frames to move between the virtual NIC of `redinext` and the nested VM interfaces.

## 26.1 Why the gateway is not redinext

It would be possible to design `redinext` as a router, but that is unnecessary for this lab.

Our requirement is:

```text
web01 ↔ db01 ↔ redinext
```

on one shared subnet, plus Internet access.

The physical-host libvirt network already provides:

```text
10.10.10.1
```

as the gateway and NAT boundary.

Therefore `redinext` only needs to bridge the nested VMs into that Layer-2 network.

This avoids adding:

```text
IP forwarding
iptables routing rules
DNAT
second NAT
```

to `redinext`.

That is a deliberate simplification.

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

# 28. The Important Difference Between `br-lab` and `virbr2`

These two devices participate in the same overall lab path, but they have different responsibilities.

## `virbr2`

Location:

```text
CachyOS
```

Purpose:

```text
outer gateway + NAT
```

Address:

```text
10.10.10.1/24
```

It is created/managed by libvirt for the `labnet` network.

## `br-lab`

Location:

```text
redinext
```

Purpose:

```text
inner Layer-2 bridge
```

Address:

```text
10.10.10.10/24
```

It connects:

```text
redinext
web01
db01
```

The combined path is:

```text
             CachyOS
                │
       ┌────────▼────────┐
       │     virbr2      │
       │   10.10.10.1    │
       │   labnet/NAT    │
       └────────┬────────┘
                │
              vnet3
                │
          redinext enp7s0
                │
           ┌────▼────┐
           │ br-lab  │
           │ .10     │
           └────┬────┘
                │
          ┌─────┴─────┐
          │           │
        web01       db01
         .20          .30
```

So the lab has **one IP subnet but two virtualization layers**.

That is the key concept to retain.

---

# 29. Configure br-lab on redinext

The relevant uplink interface inside `redinext` is:

```text
enp7s0
```

It is connected to the outer `labnet` network on CachyOS.

Inside `redinext`, attach it to:

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

You should see conceptually:

```text
enp7s0 ... master br-lab
```

The Layer-3 address belongs to the bridge:

```text
br-lab 10.10.10.10/24
```

The member interface `enp7s0` should not independently hold the same address.

The bridge therefore looks like:

```text
enp7s0
   │
   └── master br-lab

br-lab
   └── 10.10.10.10/24
```

Because `br-lab` is connected through `enp7s0` to `virbr2`, the gateway:

```text
10.10.10.1
```

is reachable at Layer 2.

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

The important entries should resemble:

```text
10.10.10.0/24 dev br-lab src 10.10.10.10
default via 10.10.10.1 dev br-lab
```

The exact route metrics may differ.

At Layer 2, the path to the gateway is:

```text
br-lab
   │
enp7s0
   │
vnet3
   │
virbr2
   │
10.10.10.1
```

If the gateway cannot be reached, inspect each link in that chain before changing DNS or guest configuration.

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

# 40.1 Troubleshooting the Outer `virbr2` / `labnet` Path

If `web01` and `db01` have correct addresses but cannot reach:

```text
10.10.10.1
```

check the outer network first.

On CachyOS:

```bash
sudo virsh net-list --all
```

You should see:

```text
labnet    active    yes
```

Then:

```bash
sudo virsh net-info labnet
```

Expected conceptually:

```text
Name:       labnet
Active:     yes
Persistent: yes
Autostart:  yes
Bridge:     virbr2
```

Inspect the XML:

```bash
sudo virsh net-dumpxml labnet
```

Then:

```bash
ip -br addr show virbr2
```

Expected:

```text
virbr2    UP    10.10.10.1/24
```

Check `redinext`'s NIC attachment:

```bash
sudo virsh domiflist redinext
```

The lab NIC should reference:

```text
Source = labnet
```

Then inspect the host-side interface:

```bash
bridge link
```

and the bridge forwarding database:

```bash
bridge fdb show br virbr2
```

The exact `vnetX` number can vary.

Inside `redinext`:

```bash
ip -br addr
```

```bash
bridge link
```

The lab interface should be attached to:

```text
br-lab
```

This gives a precise troubleshooting chain:

```text
labnet definition
      ↓
virbr2
      ↓
redinext vnetX
      ↓
redinext enp7s0
      ↓
br-lab
      ↓
web01/db01 vnetX
      ↓
guest NIC
```

Do not modify DNAT or random firewall rules until this path has been verified.

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

Therefore this lab does not use DNAT for normal internal VM communication.

---

# 43. Install `web01`

Create the VM using `virt-install`.

A representative configuration:

```bash
sudo virt-install \
    --name web01 \
    --memory 2048 \
    --vcpus 2 \
    --disk path=/mnt/vmstore/images/web01.qcow2,size=20,format=qcow2 \
    --network bridge=br-lab,model=virtio \
    --os-variant ubuntu24.04 \
    --graphics vnc \
    --cdrom /mnt/vmstore/iso/ubuntu-server.iso
```

Adjust:

- memory,
- CPU count,
- disk size,
- ISO path,
- Ubuntu OS variant

to your environment.

Verify:

```bash
sudo virsh list --all
```

---

# 44. Install `db01`

Use the same model:

```bash
sudo virt-install \
    --name db01 \
    --memory 2048 \
    --vcpus 2 \
    --disk path=/mnt/vmstore/images/db01.qcow2,size=20,format=qcow2 \
    --network bridge=br-lab,model=virtio \
    --os-variant ubuntu24.04 \
    --graphics vnc \
    --cdrom /mnt/vmstore/iso/ubuntu-server.iso
```

Verify:

```bash
sudo virsh list --all
```

---

# 45. VM Lifecycle Management

List all VMs:

```bash
sudo virsh list --all
```

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

> `destroy` does not destroy the VM's disk. It immediately stops the VM. Use it only when a graceful shutdown is not possible.

Autostart:

```bash
sudo virsh autostart web01
```

Disable:

```bash
sudo virsh autostart --disable web01
```

---

# 46. Inspect VM Configuration

```bash
sudo virsh dominfo web01
```

```bash
sudo virsh domiflist web01
```

```bash
sudo virsh domblklist web01
```

```bash
sudo virsh dumpxml web01
```

The XML is especially useful when debugging:

- CPU configuration
- memory
- disks
- NICs
- bridges
- VNC/SPICE
- boot configuration

---

# 47. VNC Console

QEMU can expose a VM's graphical console through VNC.

Check:

```bash
sudo virsh domdisplay web01
sudo virsh domdisplay db01
```

For example:

```text
vnc://127.0.0.1:0
vnc://127.0.0.1:2
```

The display numbers map to ports:

```text
:0 → 5900
:1 → 5901
:2 → 5902
```

Do not expose VNC directly to the LAN unless there is a specific security requirement and appropriate authentication/protection.

A safer approach is an SSH tunnel.

Example:

```bash
ssh -L 5900:127.0.0.1:5900 vm@10.10.10.10
```

Then use a VNC/remote-viewer client locally.

---

# 48. Cockpit

Cockpit provides web-based Linux administration.

For virtualization:

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

Install:

```bash
sudo apt install -y cockpit cockpit-machines
```

Enable:

```bash
sudo systemctl enable --now cockpit.socket
```

Verify:

```bash
systemctl status cockpit.socket --no-pager
```

Cockpit is useful for:

- VM lifecycle
- console access
- storage
- network inspection
- system monitoring

SSH remains the primary administrative interface.

---

# 49. Firewall

Use UFW only after understanding the existing network.

Check:

```bash
sudo ufw status verbose
```

Enable only the services you actually need.

For SSH:

```bash
sudo ufw allow OpenSSH
```

Then:

```bash
sudo ufw enable
```

Verify:

```bash
sudo ufw status numbered
```

Do not blindly copy firewall rules from unrelated environments.

---

# 50. Web Server Example

On `web01`:

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
curl http://127.0.0.1
```

From another machine:

```bash
curl http://10.10.10.20
```

Verify listening sockets:

```bash
sudo ss -lntp
```

---

# 51. Database Server Example

On `db01`, install the database software required by the lab.

For example:

```bash
sudo apt update
sudo apt install -y postgresql
```

Check:

```bash
sudo systemctl status postgresql --no-pager
```

Do not expose database services unnecessarily.

The database should normally be reachable only by systems that need it.

---

# 52. Host and VM Monitoring

Useful commands:

```bash
uptime
free -h
df -h
lsblk
ss -tulpn
ip -br addr
ip route
```

For VMs:

```bash
virsh list
virsh dominfo web01
virsh domstats web01
```

For processes:

```bash
ps aux --sort=-%mem | head
```

---

# 53. Logs

Systemd logs:

```bash
journalctl -b
```

Service logs:

```bash
journalctl -u ssh
journalctl -u nginx
journalctl -u libvirtd
```

Kernel/network logs:

```bash
journalctl -k
```

When troubleshooting, prefer logs and observable state over assumptions.

---

# 54. Network Troubleshooting Framework

Use the following sequence.

## Layer 1 — Link

```bash
ip link
```

Is the interface:

```text
UP
```

?

## Layer 2 — Bridge

```bash
bridge link
bridge fdb show
```

Is the VM interface attached to the expected bridge?

## Layer 3 — Address

```bash
ip addr
```

Is the IP correct?

## Layer 3 — Routing

```bash
ip route
```

Is the default route correct?

## Neighbor discovery

```bash
ip neigh
```

Can the system resolve the gateway's MAC address?

## DNS

```bash
resolvectl status
```

or:

```bash
cat /etc/resolv.conf
```

## Application

```bash
ss -lntp
curl
nc
```

This prevents random troubleshooting.

---

# 55. Use `tcpdump` as Evidence

For example:

```bash
sudo tcpdump -ni br-lab arp
```

Or:

```bash
sudo tcpdump -ni br-lab host 10.10.10.20
```

You can determine:

- whether packets leave,
- whether replies return,
- whether ARP succeeds,
- whether DNS traffic exists,
- whether TCP handshakes occur.

This is more reliable than guessing.

---

# 56. Backups

Back up:

- VM XML definitions
- VM disks
- Netplan files
- libvirt network definitions
- important service configuration
- documentation

Export VM XML:

```bash
sudo virsh dumpxml web01 > web01.xml
sudo virsh dumpxml db01 > db01.xml
```

Export network XML:

```bash
sudo virsh net-dumpxml labnet > labnet.xml
```

Keep copies outside the VM storage directory.

---

# 57. Snapshots

Snapshots can be useful during experimentation.

Before a risky change:

```bash
sudo virsh snapshot-create-as web01 before-change
```

List:

```bash
sudo virsh snapshot-list web01
```

Snapshots are not a substitute for backups.

---

# 58. Change Management

Treat infrastructure changes like engineering changes.

Before modifying a system:

```text
1. Record current state
2. Identify expected result
3. Make one change
4. Verify
5. Document
```

Example:

```bash
ip -br addr
ip route
bridge link
```

Record the output.

Then modify the configuration.

Then run the same commands again.

This makes troubleshooting reproducible.

---

# 59. Common Problems

## VM has no IP

Check:

```bash
virsh domiflist <vm>
ip link
ip addr
```

Then:

```bash
ip neigh
```

## VM has an IP but cannot reach gateway

Check:

```bash
bridge link
bridge fdb show
```

On the outer host:

```bash
virsh domiflist redinext
virsh net-info labnet
ip -br addr show virbr2
```

## Internet does not work

Check in this order:

```text
Guest IP
↓
Default route
↓
10.10.10.1
↓
Outer virbr2/labnet
↓
CachyOS Internet
↓
DNS
```

Do not change DNS when the gateway itself is unreachable.

## VNC is blank

Check:

```bash
virsh domdisplay <vm>
virsh dumpxml <vm>
```

Also verify the guest graphics stack.

For server administration, SSH is preferable when available.

## Cockpit cannot manage VMs

Check:

```bash
systemctl status cockpit.socket
systemctl status libvirtd
virsh list --all
```

The underlying libvirt/QEMU stack should be verified before blaming Cockpit.

---

# 60. Security Considerations

This lab is intentionally designed to reduce unnecessary attack surface.

Principles:

- SSH instead of unnecessary remote desktops
- no unnecessary public VNC
- no DNAT for internal VM communication
- minimal firewall exposure
- separate lab subnet
- controlled VM storage
- regular updates
- least privilege
- documented changes
- backups

Remember that virtualization does not eliminate security boundaries.

The stack is:

```text
Guest OS
   │
Virtual devices
   │
QEMU
   │
libvirt
   │
Linux kernel/KVM
   │
Hardware
```

A vulnerability at any relevant boundary can have security implications.

---

# 61. Enterprise-Oriented Improvements

Once the basic lab is stable, the next steps can include:

## Identity

- centralized authentication
- LDAP/Active Directory
- SSH key management

## Monitoring

- Prometheus
- Grafana
- node exporters
- centralized logs

## Automation

- Ansible
- Terraform where appropriate
- Git-based configuration

## Networking

- VLANs
- dedicated management network
- firewall/router VM
- DNS
- DHCP reservations
- IPAM

## Security

- host hardening
- auditd
- fail2ban where appropriate
- vulnerability scanning
- network segmentation
- secrets management

## Reliability

- automated backups
- tested restores
- snapshot strategy
- configuration backups

Do not add these technologies simply to make the lab look "enterprise."

Add them when they solve a real problem.

---

# 62. Recommended Operating Model

A useful structure is:

```text
Layer 0
Physical host
    │
    └── CachyOS

Layer 1
Infrastructure VM
    │
    └── redinext

Layer 2
Workload VMs
    │
    ├── web01
    └── db01
```

Network:

```text
Physical network
192.168.0.0/24
        │
        ▼
CachyOS
        │
        ▼
labnet / virbr2
10.10.10.1
        │
        ▼
redinext / br-lab
10.10.10.10
        │
   ┌────┴────┐
   ▼         ▼
web01      db01
.20         .30
```

This is simple enough to understand and complex enough to teach real infrastructure concepts.

---

# 63. Reference Documentation

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
- [libvirt networking overview](https://wiki.libvirt.org/Networking.html)
- [libvirt virtual networking](https://wiki.libvirt.org/VirtualNetworking.html)
- [libvirt network XML format](https://libvirt.org/formatnetwork.html)
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

# 64. Final Engineering Checklist

Before calling the lab "complete", verify that you can explain all of the following without copying a command from this document.

### Virtualization

- What KVM does
- What QEMU does
- What libvirt does
- What `virsh` does
- What `virt-install` does
- What nested virtualization means
- Why `/dev/kvm` matters

### Networking

- What the outer `labnet` network does
- What `virbr2` is and why `10.10.10.1` is the gateway
- What a Layer-2 bridge is
- What `br-lab` does
- What the outer `vnet3` and inner `vnet0`/`vnet1` interfaces represent
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
- How to verify the outer `labnet` network

---

# 65. The Most Important Lesson

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
