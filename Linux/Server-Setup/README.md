# Redinext Linux Infrastructure Lab

A practical nested-virtualization lab for building and operating a small Linux infrastructure environment with **KVM/libvirt, Ubuntu Server, networking, storage, Nginx, SSH, NAT, port forwarding, and troubleshooting**.

> **Important:** This README documents the architecture and procedures built during this lab. Network addresses and interface names are specific to this environment and should be adapted before reuse elsewhere.

---

## 1. Lab Objective

The goal of this lab is to simulate a small infrastructure environment similar to what a junior Linux/infrastructure engineer might build and maintain for a client.

The environment demonstrates:

- Linux server installation and administration
- KVM/QEMU virtualization
- libvirt VM management
- Nested virtualization
- Dedicated VM storage
- Virtual networks
- Routing and NAT
- Network segmentation
- SSH administration
- Nginx deployment
- SFTP/SMB server planning
- Port forwarding / DNAT
- Troubleshooting with `ip`, `ss`, `tcpdump`, `iptables`, `journalctl`, and `virsh`
- Separation between management infrastructure and workloads

The lab deliberately uses **nested virtualization**:

```text
Physical Machine
    │
    └── CatchyOS / Arch-based Linux
          │
          └── KVM + libvirt
                │
                └── redinext (Ubuntu Server)
                      │
                      ├── KVM + libvirt
                      │
                      ├── WEB01
                      │
                      └── DB01
```

---

# 2. Final Architecture

## 2.1 High-level topology

```text
                         HOME / LAB ROUTER
                           192.168.0.1
                                │
                             Wi-Fi LAN
                                │
                  ┌──────────────▼──────────────┐
                  │           CatchyOS          │
                  │     Physical Linux Host     │
                  │                             │
                  │ wlan0: 192.168.0.119/24     │
                  │                             │
                  │libvirt virbr2: 10.10.10.1/24│
                  └─────────────┬───────────────┘
                                │
                         10.10.10.1/24
                                │
                       ┌────────▼────────┐
                       │     redinext    │
                       │   Ubuntu Server │
                       │                 │
                       │ enp1s0          │
                       │ 10.10.1.10/24   │
                       │                 │
                       │ virbr0          │
                       │ 10.10.2.1/24    │
                       ────────┬─────────┘
                                │
                         10.10.2.0/24
                                │
                    ┌───────────┴───────────┐
                    │                       │
             ┌──────▼──────┐         ┌──────▼──────┐
             │    WEB01    │         │     DB01    │
             │ Ubuntu      │         │ Ubuntu      │
             │ Server      │         │ Server      │
             │             │         │             │
             │10.10.10.10  │         │ 10.10.10.20 │
             │ Nginx       │         │ SFTP/SMB    │
             └─────────────┘         └─────────────┘
```

## 2.2 Address plan

| System | Interface | Address | Purpose |
|---|---|---:|---|
| Router | LAN | `192.168.0.1/24` | Physical network gateway |
| CatchyOS | `wlan0` | `192.168.0.119/24` | Physical Linux host |
| CatchyOS | `virbr0` | `10.10.10.1/24` | L1 libvirt gateway |
| redinext | `enp1s0` | `10.10.1.10/24` | WAN/upstream side |
| redinext | `virbr0` | `10.10.1.1/24` | Internal server gateway |
| WEB01 | `enp1s0` | `10.10.2.10/24` | Web server |
| FILE01 | `enp1s0` | `10.10.2.202/24` | Internal file server |

> `FILE01` was part of the planned architecture. WEB01 was the first workload successfully installed and tested.

---

# 3. Why This Architecture

The lab deliberately separates three layers.

## Layer 0 — Physical host

**CatchyOS**

Responsible for:

- Physical hardware access
- Wi-Fi connectivity
- KVM
- QEMU
- libvirt
- First virtual network
- Hosting the Ubuntu Server hypervisor

## Layer 1 — Infrastructure host

**redinext**

Responsible for:

- Ubuntu Server administration
- KVM/libvirt
- Nested VM storage
- Internal virtual networking
- Routing/NAT between networks
- Hosting application/file workloads


# 3. Wi-Fi Design Constraint

The physical host is connected through:

```text
wlan0 → 192.168.0.119/24
```

and **not Ethernet**.

The Ethernet interface:

```text
eno1
```

was present but down.

A normal Linux bridge that transparently places VM MAC addresses directly on a Wi-Fi station interface is not a reliable design. Therefore, this lab uses **routed/NAT virtual networks** instead of trying to create a transparent Wi-Fi bridge.

This is an important infrastructure lesson:

> An IP subnet, a routed network, a NAT network, and a Layer-2 bridge are not interchangeable concepts.

---

# 4. Layer 0 — Prepare CatchyOS

CatchyOS is the physical Arch-based Linux host.

## 4.1 Verify CPU virtualization

```bash
lscpu | grep -E 'Model name|Virtualization'
```

Expected:

```text
Virtualization: VT-x
```

## 4.2 Verify KVM

```bash
ls -l /dev/kvm
lsmod | grep kvm
```

Expected on Intel:

```text
/dev/kvm
kvm_intel
kvm
```

The lab hardware used:

```text
12th Gen Intel Core i5-12450H
```

with VT-x exposed directly to CatchyOS.

## 4.3 Check the network

```bash
ip -br addr
```

The host used:

```text
wlan0    UP    192.168.0.119/24
virbr2   UP    10.10.10.1/24
```

---

# 5. Install KVM/libvirt on CatchyOS

The exact package set can vary with the Arch-based distribution, but the lab used the following virtualization stack:

```bash
sudo pacman -Syu qemu-desktop libvirt virt-install virt-manager edk2-ovmf dnsmasq
```

Enable libvirt:

```bash
sudo systemctl enable --now libvirtd
```

Add the administration user to the relevant groups:

```bash
sudo usermod -aG libvirt "$USER"
sudo usermod -aG kvm "$USER"
```

Log out and back in afterward.

Verify:

```bash
groups
```

Then:

```bash
sudo virt-host-validate qemu
```

Important checks should report `PASS`, especially:

```text
hardware virtualization
/dev/kvm
/dev/kvm accessible
```

### Note about `kvm-ok`

`kvm-ok` is commonly available on Debian/Ubuntu through `cpu-checker`. It is **not the normal Arch-native diagnostic**. On CatchyOS, use:

```bash
lscpu
ls -l /dev/kvm
lsmod | grep kvm
sudo virt-host-validate qemu
```

---

# 6. Libvirt Network on CatchyOS

The first libvirt network was changed to:

```text
10.10.10.0/24
```

with:

```text
CatchyOS virbr2= 10.10.10.1
redinext         = 10.10.10.10
```

Verify:

```bash
sudo virsh net-list --all
ip -br addr show virbr2
```

The network must be active before creating a VM.

A common VM creation failure encountered during the lab was:

```text
Requested operation is not valid:
network 'default' is not active
```

Fix:

```bash
sudo virsh net-start default
sudo virsh net-autostart default
```

Always verify:

```bash
sudo virsh net-list --all
```

---

# 7. Storage Design

A separate storage device was used for nested VM storage.

The important design principle was:

```text
redinext OS disk
    ↓
Ubuntu Server

separate VM disk
    ↓
/mnt/vmstore
    ↓
nested VM images
```

This avoids filling the OS filesystem with VM disks.

## 7.1 Verify the additional disk

Inside `redinext`:

```bash
lsblk -f
```

The additional disk became:

```text
/dev/vdb
```

with a target size of **50 GB**.

## 7.2 Format as ext4

Only after verifying that `/dev/vdb` is actually the new 50 GB disk:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
```

Then:

```bash
sudo mkfs.ext4 /dev/vdb
```

## 7.3 Mount point

```bash
sudo mkdir -p /mnt/vmstore
sudo mount /dev/vdb /mnt/vmstore
```

Verify:

```bash
df -h /mnt/vmstore
```

## 7.4 Make the mount persistent

Get the UUID:

```bash
sudo blkid /dev/vdb
```

Add an entry to `/etc/fstab`:

```text
UUID=<UUID> /mnt/vmstore ext4 defaults 0 2
```

Test before rebooting:

```bash
sudo umount /mnt/vmstore
sudo mount -a
findmnt /mnt/vmstore
```

A reboot should not be used as the first test of an unverified `fstab`.

---

# 8. Nested VM Storage Pool

Directory structure:

```text
/mnt/vmstore/
├── images/
│   ├── web01.qcow2
│   └── db01.qcow2
└── iso/
    └── ubuntu-24.04.x-live-server-amd64.iso
```

Create it:

```bash
sudo mkdir -p /mnt/vmstore/images
sudo mkdir -p /mnt/vmstore/iso
```

The libvirt storage pool can then be created as:

```bash
sudo virsh pool-define-as nested-vms dir --target /mnt/vmstore/images
sudo virsh pool-start nested-vms
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

# 9. Ubuntu Server Installation as L1 Hypervisor

The Ubuntu Server VM (`redinext`) was installed on CatchyOS and then configured as a second KVM/libvirt host.

## Recommended resources

For a 16 GB physical machine:

```text
redinext:
    vCPU: 4–8
    RAM: 6–9 GB
    OS disk: ~60 GB
```

The exact allocation used during testing was higher than the original plan in one iteration. Resource allocation should leave enough RAM for the physical OS and nested guests.

## During Ubuntu installation

Use:

```text
Hostname: redinext
```

Install:

```text
OpenSSH Server
```

Initially use DHCP to validate installation/networking before applying static configuration.

---

# 10. Validate Nested KVM inside redinext

This step is critical.

Do not start creating nested VMs until the L1 guest can actually use KVM.

Check:

```bash
lscpu | grep -E 'Model name|Virtualization'
```

Check for Intel VT-x exposure:

```bash
grep -oE 'vmx' /proc/cpuinfo | head
```

Check KVM:

```bash
ls -l /dev/kvm
lsmod | grep kvm
```

Check nested mode:

```bash
cat /sys/module/kvm_intel/parameters/nested
```

Expected:

```text
Y
```

Then on Ubuntu:

```bash
sudo apt update
sudo apt install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    bridge-utils \
    cpu-checker \
    dnsmasq-base
```

Enable libvirt:

```bash
sudo systemctl enable --now libvirtd
```

Add the user:

```bash
sudo usermod -aG libvirt vm
sudo usermod -aG kvm vm
```

Re-login.

Validate:

```bash
kvm-ok
sudo virt-host-validate qemu
```

Expected:

```text
INFO: /dev/kvm exists
KVM acceleration can be used
```

### Why this checkpoint matters

Earlier, KVM was attempted inside an Ubuntu VM hosted by VirtualBox and the nested guest repeatedly experienced kernel panics and host freezes. Moving the first KVM layer directly onto the physical CatchyOS host removed that problematic VirtualBox → KVM dependency.

Lesson:

> "KVM detected" is not the same as "nested KVM is stable."

Always validate the entire virtualization layer before adding another layer of guests.

---

# 11. L1 Network — redinext

The outer libvirt network became:

```text
CatchyOS virbr2:
    10.10.10.1/24

redinext:
    10.10.10.10/24
```

Inside `redinext`, verify:

```bash
ip -br addr
ip route
```

The upstream/default gateway should point toward:

```text
10.10.10.1
```

Then validate:

```bash
ping -c 3 10.10.10.1
ping -c 3 8.8.8.8
ping -c 3 google.com
```

These tests separate:

1. local L2/L3 reachability,
2. routed Internet connectivity,
3. DNS resolution.

---

# 12. Internal Network — redinext

The second libvirt network was changed to:

```text
10.10.10.0/24
```

with:

```text
redinext br-lab = 10.10.10.10
WEB01            = 10.10.10.20
DB01           = 10.10.10.30
```

Verify on redinext:

```bash
ip -br addr
sudo virsh net-list --all
```

Verify the guest:

```bash
ip -br addr
ip route
```

Expected WEB01 gateway:

```text
10.10.10.20
```

---

# 13 Create WEB01

Example CLI provisioning:

```bash
sudo virt-install \
  --name web01 \
  --memory 2048 \
  --vcpus 2 \
  --disk pool=nested-vms,size=15,format=qcow2,bus=virtio \
  --cdrom /mnt/vmstore/iso/ubuntu-24.04.4-live-server-amd64.iso \
  --network network=default,model=virtio \
  --os-variant ubuntu24.04 \
  --graphics none \
  --console pty,target_type=serial \
  --noautoconsole
```

### Important installer lesson

The Ubuntu `live-server` ISO did **not** behave like a traditional install tree when used with:

```text
--location <local-live-server-iso>
```

This produced:

```text
Couldn't find kernel for install tree
```

Therefore do not blindly copy a `--location` example intended for a different Ubuntu installer media layout.

For this lab, the installation was ultimately completed through the available VM console/installation workflow.

---

# 14. Accessing Headless VMs

For a running VM:

```bash
sudo virsh list --all
```

Start:

```bash
sudo virsh start web01
```

Get DHCP lease:

```bash
sudo virsh net-dhcp-leases default
```

Console:

```bash
sudo virsh console web01
```

Exit console:

```text
Ctrl + ]
```

Once SSH is installed, **SSH is the preferred administration method**.

Example:

```bash
ssh dev@10.10.10.20
```

---

# 15. WEB01 Configuration

WEB01 was configured as an Ubuntu web server.

Install SSH:

```bash
sudo apt update
sudo apt install -y openssh-server
```

Verify:

```bash
sudo systemctl status ssh --no-pager
```

Install Nginx:

```bash
sudo apt install -y nginx
```

Verify:

```bash
sudo systemctl status nginx --no-pager
```

Local test:

```bash
curl -I http://127.0.0.1
```

Expected:

```text
HTTP/1.1 200 OK
Server: nginx/1.18.0 (Ubuntu)
```

---

# 16. Nginx 403 Troubleshooting

A `403 Forbidden` was initially returned even though networking was working.

The decisive evidence was in:

```text
/var/log/nginx/error.log
```

The useful error was:

```text
open() "/var/www/html/index.html" failed (13: Permission denied)
```

This means the request reached Nginx correctly, but Nginx could not read the web content.

## Diagnose

```bash
sudo ls -la /var/www/html
namei -l /var/www/html/index.html
sudo tail -30 /var/log/nginx/error.log
```

Verify file permissions:

```bash
sudo chmod 644 /var/www/html/index.html
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I http://127.0.0.1
```

### Important troubleshooting principle

A response like:

```text
HTTP/1.1 403 Forbidden
Server: nginx
```

already proves that:

- the TCP connection worked,
- port 80 was reached,
- Nginx accepted the connection,
- the failure is higher in the stack.

Do not restart routers or rewrite firewall rules when the application itself is returning an HTTP status.

---

# 17. Testing the Network Layer by Layer

A reliable troubleshooting sequence was used repeatedly.

## Host → redinext

```bash
ping -c 3 10.10.10.10
```

## redinext → WEB01

```bash
ping -c 3 10.10.10.10
curl -I http://10.10.10.20
```

## WEB01 local service

```bash
curl -I http://127.0.0.1
```

## Route inspection

```bash
ip route
```

## Listening services

```bash
ss -tulpn
```

## VM state

```bash
sudo virsh list --all
```

## VM address

```bash
sudo virsh net-dhcp-leases default
```

The rule is:

> Test the closest layer first, then move outward.

---

# 18. Two-Level NAT and Port Forwarding

The current network has two NAT/router boundaries:

```text
192.168.0.0/24
       │
       ▼
CatchyOS
10.10.10.1
       │
       ▼
redinext
10.10.10.10
       │
       ▼
WEB01
10.10.10.20
```

This means Internet/LAN exposure can require more than one forwarding stage.

For example, an attempted HTTP exposure used:

```text
LAN client
192.168.0.x
    ↓
CatchyOS 192.168.0.119:8080
    ↓ DNAT
redinext 10.10.10.10:8080
    ↓ DNAT
WEB01 10.10.10.20:80
```

The first DNAT was configured conceptually as:

```bash
sudo iptables -t nat -A PREROUTING \
    -i wlan0 \
    -p tcp --dport 8080 \
    -j DNAT --to-destination 10.10.1.10:8080
```

and forwarding:

```bash
sudo iptables -A FORWARD \
    -i wlan0 \
    -o virbr0 \
    -p tcp \
    -d 10.10.1.10 \
    --dport 8080 \
    -m conntrack --ctstate NEW,ESTABLISHED,RELATED \
    -j ACCEPT
```

On redinext the second DNAT was:

```bash
sudo iptables -t nat -A PREROUTING \
    -i enp1s0 \
    -p tcp --dport 8080 \
    -j DNAT --to-destination 10.10.2.10:80
```

with forwarding:

```bash
sudo iptables -A FORWARD \
    -i enp1s0 \
    -o virbr0 \
    -p tcp \
    -d 10.10.2.10 \
    --dport 80 \
    -m conntrack --ctstate NEW,ESTABLISHED,RELATED \
    -j ACCEPT
```

## Why the first attempt was difficult

The CatchyOS forwarding chain had:

```text
FORWARD policy DROP
```

and also UFW chains.

Packet counters were used to establish whether a rule was actually matching:

```bash
sudo iptables -t nat -L PREROUTING -n -v
sudo iptables -L FORWARD -n -v
```

Traffic capture was then used:

```bash
sudo tcpdump -ni wlan0 'tcp port 8080'
```

This proved that the LAN client was reaching CatchyOS.

That is an important diagnostic technique:

> Packet counters and packet captures tell you where traffic stops; error messages alone often do not.

---

# 20. Important NAT Rule Warning

Do **not** repeatedly append more and more `iptables` rules while troubleshooting.

That produces duplicate rules and makes the packet path ambiguous.

Before rebuilding a test ruleset:

```bash
sudo iptables -t nat -L -n -v --line-numbers
sudo iptables -L FORWARD -n -v --line-numbers
```

If a complete test reset is required, carefully preserve the libvirt-generated NAT configuration or rebuild the required NAT rules afterward.

The lab encountered confusion because libvirt automatically creates its own NAT chains, for example:

```text
LIBVIRT_PRT
```

These rules are needed for the VM network's Internet access.

Never blindly delete libvirt's networking rules on a production host.

---

# 21. Routing and NAT — Conceptual Model

The lab demonstrates the difference between **routing** and **NAT**.

## Routing

Routing answers:

> Where should this packet go?

Example:

```text
10.10.2.10 → 10.10.2.1
```

## NAT

NAT changes addressing.

Example:

```text
10.10.2.10
    ↓ MASQUERADE
10.10.1.10
```

for traffic leaving the internal VM network.

### Why NAT exists here

WEB01 and FILE01 live behind redinext's internal network:

```text
10.10.2.0/24
```

so redinext can masquerade their outbound traffic toward its upstream network.

---

# 22. Testing Internet Access

For each server, test:

## Layer 3

```bash
ping -c 3 8.8.8.8
```

## DNS

```bash
ping -c 3 google.com
```

## HTTP/HTTPS

```bash
curl -I https://example.com
```

If:

```text
8.8.8.8 works
google.com fails
```

then the problem is probably DNS.

If:

```text
10.10.x.x works
8.8.8.8 fails
```

then investigate routing/NAT.

If:

```text
gateway fails
```

investigate the local virtual network first.

---

# 23. FILE01 Design

FILE01 is intended to be an isolated internal server.

Address:

```text
10.10.2.202/24
```

Gateway:

```text
10.10.2.1
```

Services:

```text
SSH/SFTP    TCP/22
SMB         TCP/445
```

Planned filesystem structure:

```text
/srv/shares/
├── engineering/
├── management/
└── public/
```

The service should use:

- Linux users
- Linux groups
- file ownership
- permissions
- ACLs where required
- SSH/SFTP
- Samba

The design goal is:

```text
LAN → FILE01
    DENY

redinext → FILE01
    ALLOW

WEB01 → FILE01
    only explicitly required services
```

while still allowing FILE01 outbound Internet access for updates.

---

# 24. Why FILE01 Is Isolated

The lab deliberately separates application and file workloads.

WEB01 is Internet-facing/application-facing.

FILE01 holds sensitive/shared data.

A compromise of WEB01 should **not automatically grant access to the file server**.

This creates a basic security boundary:

```text
             WEB01
        internet-facing
              │
              │ restricted
              ▼
           FILE01
        internal only
```

This principle is more important than the individual commands:

> Expose only what needs to be exposed.

---

# 25. Public Website Exposure

Because the physical host currently reaches the Internet through Wi-Fi and there is no router administration available, traditional inbound port forwarding from the public Internet may not be possible.

A practical alternative is an **outbound tunnel**, such as Cloudflare Tunnel.

Conceptually:

```text
Internet
    │
    ▼
Public hostname
    │
    ▼
Cloudflare Tunnel
    │
    ▼
redinext
    │
    ▼
WEB01
10.10.2.10:80
```

This avoids requiring inbound access through the home router.

A temporary development tunnel can be used for testing; a stable custom hostname requires a domain/managed DNS setup.

> Public exposure should be limited to WEB01's web service. Do not expose SMB, SFTP, or hypervisor management ports to the Internet.

---

# 26. Troubleshooting Lessons

## VM won't start

Check:

```bash
sudo virsh list --all
sudo virsh dominfo <vm>
```

Then:

```bash
sudo virsh dumpxml <vm>
```

Check storage:

```bash
sudo virsh domblklist <vm>
```

Check network:

```bash
sudo virsh net-list --all
```

---

## `virt-install: command not found`

On Ubuntu:

```bash
sudo apt install -y virtinst
```

`virt-install` is provided by `virtinst`.

---

## ISO permission denied

Avoid placing libvirt installer media under a user's private home directory when QEMU cannot traverse the directory.

Use:

```text
/mnt/vmstore/iso/
```

or a libvirt-managed boot directory.

A failure such as:

```text
Could not open ... Permission denied
```

is a filesystem permission/path-access issue, not a QEMU/KVM failure.

---

## Libvirt network inactive

Check:

```bash
sudo virsh net-list --all
```

Start:

```bash
sudo virsh net-start default
sudo virsh net-autostart default
```

---

## VM storage unexpectedly tiny

Always check:

```bash
lsblk
sudo qemu-img info <image>
```

A VM disk attachment can exist while the backing file is the wrong size.

Never format the disk based only on the device name.

Verify:

```text
vdb = expected size
```

before:

```bash
mkfs.ext4 /dev/vdb
```

---

## Serial console is blank

The Ubuntu `live-server` installer and `virt-install --location` are not universally interchangeable.

The failed method:

```text
--location /path/to/live-server.iso
```

returned:

```text
Couldn't find kernel for install tree
```

This happens because the local live-server ISO isn't being exposed as a traditional install tree by that method.

For headless server VMs, choose an installation method that explicitly supports the desired console path, and test the console before proceeding.

---

## GUI freezes

For infrastructure servers, avoid depending on graphical environments.

Prefer:

```text
SSH
virsh
systemctl
journalctl
ip
ss
tcpdump
```

over desktop administration.

This also reduces the attack surface and makes the environment closer to real server operations.

---

# 27. Core Commands to Learn

## VM lifecycle

```bash
sudo virsh list --all
sudo virsh start <vm>
sudo virsh shutdown <vm>
sudo virsh destroy <vm>
sudo virsh undefine <vm>
```

## VM information

```bash
sudo virsh dominfo <vm>
sudo virsh domblklist <vm>
sudo virsh domiflist <vm>
sudo virsh dumpxml <vm>
```

## Network

```bash
ip -br addr
ip route
ip neigh
ss -tulpn
```

## Libvirt networks

```bash
sudo virsh net-list --all
sudo virsh net-info <network>
sudo virsh net-dumpxml <network>
sudo virsh net-dhcp-leases <network>
```

## Storage

```bash
sudo virsh pool-list --all
sudo virsh pool-info <pool>
sudo virsh vol-list <pool>
lsblk -f
df -h
findmnt
```

## Services

```bash
systemctl status <service>
systemctl restart <service>
systemctl enable <service>
journalctl -u <service>
```

## Network troubleshooting

```bash
ping
curl
ss
tcpdump
ip route
```

## Firewall/NAT inspection

```bash
sudo iptables -L -n -v
sudo iptables -t nat -L -n -v
```

On newer systems, also understand the nftables backend:

```bash
sudo nft list ruleset
```

---

# 28. Troubleshooting Methodology

The most important skill learned from this project is not a particular command.

It is the troubleshooting method:

```text
1. Define the expected traffic/path
              │
              ▼
2. Identify each network boundary
              │
              ▼
3. Test the nearest layer first
              │
              ▼
4. Capture packets/counters
              │
              ▼
5. Change one thing
              │
              ▼
6. Re-test
              │
              ▼
7. Document the result
```

For example:

```text
LAN client
    │
    ▼
CatchyOS
    │
    ▼
redinext
    │
    ▼
WEB01
    │
    ▼
Nginx
```

If the client receives:

```text
HTTP/1.1 403 Forbidden
Server: nginx
```

the network path has already reached the application.

If the client receives:

```text
Connection refused
```

investigate the listening socket/service.

If the client times out:

```text
timeout
```

investigate routing, firewall, NAT, or packet delivery.

---

# 29. What This Lab Demonstrates

After completing the environment, you should be able to explain:

### Linux

- filesystem hierarchy
- users/groups
- permissions
- services
- systemd
- logs
- packages
- SSH
- process management

### Virtualization

- KVM
- QEMU
- libvirt
- `virsh`
- `virt-install`
- qcow2
- virtual disks
- virtual NICs
- virtual networks
- nested virtualization

### Networking

- L2 vs L3
- IP addressing
- subnets
- gateways
- routing
- NAT
- DNAT
- MASQUERADE
- virtual bridges
- DHCP
- DNS
- TCP/UDP
- port forwarding

### Infrastructure services

- Nginx
- OpenSSH
- SFTP
- Samba/SMB

### Security

- segmentation
- least privilege
- service exposure
- firewall policies
- attack-surface reduction
- separation of management and workloads

---

# 30. Final Lessons

The most important lessons from building this environment were:

1. **Do not blindly reinstall or reconfigure when something fails.**
2. **Identify which layer is broken first.**
3. **A successful TCP connection proves more than a successful ping.**
4. **A HTTP error proves the request reached the web server.**
5. **Packet counters and `tcpdump` are often better evidence than assumptions.**
6. **Keep hypervisor and workloads separated.**
7. **Separate OS storage from VM storage.**
8. **Avoid exposing internal services unnecessarily.**
9. **Don't use Wi-Fi bridging when the underlying medium does not support the required L2 semantics reliably.**
10. **Use a repeatable architecture and document every change.**

---

# 31. Recommended Next Phases

## Phase 1 — Linux Administration

- [ ] Users and groups
- [ ] File permissions and ACLs
- [ ] systemd
- [ ] journald
- [ ] SSH hardening
- [ ] Bash administration scripting

## Phase 2 — Storage

- [ ] ext4
- [ ] LVM
- [ ] mount management
- [ ] fstab
- [ ] backups
- [ ] snapshots

## Phase 3 — Networking

- [ ] routing
- [ ] NAT
- [ ] DNAT
- [ ] nftables
- [ ] DNS
- [ ] DHCP
- [ ] network segmentation

## Phase 4 — WEB01

- [ ] Nginx
- [ ] HTTPS
- [ ] virtual hosts
- [ ] access/error logs
- [ ] security headers
- [ ] service hardening

## Phase 5 — FILE01

- [ ] OpenSSH/SFTP
- [ ] Samba
- [ ] users/groups
- [ ] ACLs
- [ ] share permissions
- [ ] audit/logging

## Phase 6 — Operations

- [ ] monitoring
- [ ] centralized logging
- [ ] automated backups
- [ ] health checks
- [ ] configuration management
- [ ] disaster recovery testing

---

# 32. Quick Reference Architecture

```text
                    ┌─────────────────────┐
                    │   Physical Router   │
                    │     192.168.0.1     │
                    └──────────┬──────────┘
                               │
                          Wi-Fi / LAN
                               │
                    ┌──────────▼──────────┐
                    │      CatchyOS       │
                    │  wlan0 192.168.0.119 │
                    │                     │
                    │  virbr0 10.10.1.1   │
                    │  KVM + libvirt       │
                    └──────────┬──────────┘
                               │
                         10.10.1.0/24
                               │
                    ┌──────────▼──────────┐
                    │      redinext       │
                    │ Ubuntu Server       │
                    │ enp1s0 10.10.1.10   │
                    │ virbr0 10.10.2.1    │
                    │ KVM + libvirt       │
                    └──────────┬──────────┘
                               │
                         10.10.2.0/24
                         ┌─────┴─────┐
                         │           │
                  ┌──────▼─────┐ ┌───▼──────┐
                  │   WEB01    │ │  FILE01  │
                  │ 10.10.2.10 │ │10.10.2.202│
                  │    Nginx   │ │ SFTP/SMB │
                  └────────────┘ └──────────┘
```

---

## Repository Purpose

This lab is intended to be treated as an engineering project rather than a collection of copy-pasted commands.

Every change should answer:

```text
What am I changing?
Why am I changing it?
Which layer does it affect?
What could break?
How will I verify it?
How will I revert it?
```

That mindset is the most transferable skill from this project into real Linux infrastructure, cloud, DevOps, and security work.
