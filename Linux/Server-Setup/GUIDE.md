# KVM, QEMU and libvirt: A Practical Guide to Linux Virtualization

> A technical but beginner-friendly research note for understanding how
> Linux virtualization actually works, how KVM, QEMU and libvirt fit
> together, and how they cooperate to create and manage virtual
> machines.

------------------------------------------------------------------------

## 1. Why learn this?

When people start working with Linux virtualization, they often
encounter commands such as:

``` bash
virsh list --all
virt-install ...
qemu-system-x86_64 ...
ls -l /dev/kvm
```

It is easy to memorize these commands without understanding what is
underneath them.

That becomes a problem when something breaks.

For example:

-   Why does `/dev/kvm` matter?
-   Why is KVM not the same thing as QEMU?
-   Why can QEMU run without KVM?
-   Why does libvirt exist if QEMU can already create VMs?
-   What creates `vnet0`?
-   What is a `virtio` network card?
-   Why does `virsh` control a QEMU VM?
-   Why does a VM appear as a `qemu-system-x86_64` process?
-   Where does the virtual CPU actually execute?
-   What happens when a guest executes a privileged CPU instruction?
-   What is a VM exit?
-   What is nested virtualization?
-   Where do virtual disks, NICs, GPUs and VNC actually come from?

The purpose of this document is to answer those questions from the
bottom up.

------------------------------------------------------------------------

# 2. The short answer

The easiest way to remember the stack is:

``` text
                Linux virtualization stack

┌──────────────────────────────────────────────────────────┐
│                    Management layer                      │
│                                                          │
│       Cockpit / virt-manager / virsh / virt-install     │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                         libvirt                          │
│                                                          │
│   Defines and manages VMs, networks, storage, devices   │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                          QEMU                            │
│                                                          │
│     User-space virtual machine monitor / device model   │
│                                                          │
│   Virtual disk • NIC • GPU • chipset • firmware • etc.  │
└──────────────────────────┬───────────────────────────────┘
                           │
                           │ /dev/kvm + KVM ioctls
                           ▼
┌──────────────────────────────────────────────────────────┐
│                           KVM                            │
│                                                          │
│            Linux kernel virtualization subsystem         │
│                                                          │
│      vCPU execution • VM memory • VM exits • CPU state  │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    CPU virtualization                    │
│                                                          │
│            Intel VT-x / AMD-V / ARM virtualization       │
└──────────────────────────────────────────────────────────┘
```

The important distinction is:

> **KVM provides hardware-assisted virtualization through the Linux
> kernel. QEMU provides the virtual machine and virtual hardware in user
> space. libvirt provides a management and API layer over virtualization
> technologies such as QEMU/KVM.**

QEMU's own documentation describes system emulation as providing a
virtual model of a machine and says that QEMU can use KVM as a
virtualization accelerator. The Linux kernel documentation describes KVM
as a kernel virtualization subsystem exposed through an API centered
around file descriptors and ioctls. libvirt provides APIs and management
objects for domains, networks, storage and other virtualization
resources. \[1\]\[2\]\[3\]

------------------------------------------------------------------------

# 3. What is virtualization?

At the simplest level, virtualization means creating a software-defined
computer that behaves sufficiently like a physical computer that an
operating system can run inside it.

A physical computer contains:

``` text
CPU
RAM
Storage
Network card
GPU/display
USB devices
Firmware
Interrupt controllers
Timers
```

A virtual machine presents corresponding virtual resources:

``` text
vCPU
vRAM
Virtual disk
Virtual NIC
Virtual GPU
Virtual firmware
Virtual devices
Virtual interrupt/timer facilities
```

The guest operating system normally behaves as though it owns a machine.

For example:

``` text
Ubuntu guest
     │
     ├── sees 2 vCPUs
     ├── sees 4 GB RAM
     ├── sees /dev/vda
     ├── sees an Ethernet adapter
     └── sees a virtual display
```

Those resources are not independent physical devices. They are provided
by the virtualization stack.

------------------------------------------------------------------------

# 4. Virtualization vs emulation

These terms are related but not identical.

## 4.1 Emulation

Emulation means software reproduces the behavior of another hardware
architecture or device.

For example:

``` text
x86 host
   │
   ▼
software emulates ARM CPU
   │
   ▼
ARM operating system
```

The emulator can translate guest instructions into operations the host
can execute.

This is flexible but can be expensive.

QEMU's TCG (Tiny Code Generator) is an example of software CPU
emulation.

------------------------------------------------------------------------

## 4.2 Hardware-assisted virtualization

With hardware-assisted virtualization:

``` text
Guest x86 code
      │
      ▼
physical x86 CPU
```

The CPU executes most guest instructions directly rather than QEMU
translating every instruction.

Intel provides VT-x and AMD provides AMD-V virtualization extensions.

Linux KVM uses these CPU virtualization mechanisms.

This is why KVM-backed virtualization can approach native execution
speed for many workloads.

------------------------------------------------------------------------

## 4.3 QEMU can do both

QEMU can operate without KVM using software emulation.

Conceptually:

``` text
QEMU + TCG
    │
    └── software CPU emulation
```

Or on Linux:

``` text
QEMU + KVM
    │
    ├── QEMU provides VM/device model
    └── KVM accelerates CPU virtualization
```

This distinction is fundamental.

> **QEMU is not simply "the software that makes KVM work." QEMU and KVM
> perform different jobs.**

------------------------------------------------------------------------

# 5. What is KVM?

KVM stands for:

> **Kernel-based Virtual Machine**

KVM is part of the Linux kernel virtualization infrastructure.

It allows Linux to use the CPU's hardware virtualization capabilities to
execute guest virtual CPUs.

The Linux kernel exposes KVM through a device such as:

``` bash
/dev/kvm
```

You can check it with:

``` bash
ls -l /dev/kvm
```

Typical output:

``` text
crw-rw---- 1 root kvm ... /dev/kvm
```

The important part is not the exact permissions but the existence of the
device.

------------------------------------------------------------------------

# 6. What does `/dev/kvm` actually mean?

It is tempting to think:

> `/dev/kvm` is the VM.

It is not.

It is an interface between user-space programs and the kernel's KVM
subsystem.

A simplified flow is:

``` text
QEMU
  │
  │ open("/dev/kvm")
  ▼
KVM kernel subsystem
  │
  │ ioctls
  ▼
Virtual machine state
```

The Linux KVM API is based on file descriptors and ioctl operations.

For example, the KVM API allows software to:

-   obtain a KVM handle,
-   create a virtual machine,
-   create virtual CPUs,
-   configure VM state,
-   configure devices,
-   run vCPUs,
-   handle VM exits.

The kernel documentation describes this through operations such as:

``` text
open("/dev/kvm")
       │
       ▼
KVM_CREATE_VM
       │
       ▼
KVM_CREATE_VCPU
       │
       ▼
KVM_RUN
```

This is a conceptual model rather than a normal command sequence you
manually execute. QEMU normally performs these operations for you.

------------------------------------------------------------------------

# 7. What does KVM actually virtualize?

KVM is primarily responsible for the CPU virtualization machinery and
related low-level VM execution.

A simplified model:

``` text
             KVM
              │
      ┌───────┼────────┐
      │       │        │
     VM     vCPU      memory
      │       │        │
      ▼       ▼        ▼
   VM state  CPU     guest RAM
```

KVM provides the kernel-side mechanisms needed to run guest CPUs using
hardware virtualization.

It does not by itself provide a complete PC-compatible machine with:

-   SATA/SCSI/NVMe controllers,
-   network cards,
-   VGA devices,
-   USB controllers,
-   firmware,
-   disks,
-   a graphical console.

That is where QEMU becomes important.

------------------------------------------------------------------------

# 8. What is QEMU?

QEMU is a generic open-source machine emulator and virtualizer.

In system-emulation mode, QEMU provides a model of an entire machine.

For example:

``` text
QEMU virtual machine

┌───────────────────────────────┐
│ Virtual CPU                   │
│ Virtual RAM                   │
│                               │
│ Virtual chipset               │
│ Virtual PCI devices           │
│ Virtual NIC                   │
│ Virtual disk controller       │
│ Virtual GPU                   │
│ Virtual USB                   │
│ Virtual firmware              │
└───────────────────────────────┘
```

QEMU can emulate many different architectures and machine types.

Its system-emulation documentation covers CPU, memory, device models,
networking, storage, display, USB and other virtual hardware. \[4\]

------------------------------------------------------------------------

# 9. QEMU's two important operating modes

## 9.1 QEMU + TCG

``` text
Guest CPU instructions
          │
          ▼
       QEMU TCG
          │
          ▼
Host CPU instructions
```

This is software emulation.

It is useful when:

-   the guest architecture differs from the host,
-   hardware virtualization is unavailable,
-   architecture emulation is required.

It is generally slower than hardware-assisted virtualization.

------------------------------------------------------------------------

## 9.2 QEMU + KVM

On a Linux x86 host:

``` text
Guest OS
   │
   ▼
QEMU
   │
   ├── virtual devices
   │
   └── KVM
         │
         ▼
      CPU hardware
```

QEMU handles the machine model.

KVM allows the guest CPU to execute using hardware virtualization.

This is the configuration normally meant when people say:

> "I am running a KVM/QEMU virtual machine."

------------------------------------------------------------------------

# 10. What does QEMU provide?

QEMU can model many components of a virtual machine.

## CPU

QEMU defines the CPU model presented to the guest while KVM handles
accelerated execution where applicable.

## Memory

QEMU allocates and maps guest memory while KVM provides the kernel
mechanisms required for guest memory virtualization.

## Storage

QEMU can expose virtual disks such as:

``` text
qcow2 image
raw image
block device
network storage
```

For example:

``` text
web01.qcow2
```

may appear inside the guest as:

``` text
/dev/vda
```

The guest does not need to know that `/dev/vda` ultimately corresponds
to a file on the host.

------------------------------------------------------------------------

# 11. QEMU networking

A guest may see:

``` text
enp1s0
```

or another network interface.

That interface is virtual.

QEMU can connect it to different networking backends.

A common Linux arrangement is:

``` text
Guest
  │
  │ virtual NIC
  ▼
QEMU
  │
  ▼
tap/vnet interface
  │
  ▼
Linux bridge
  │
  ▼
physical or virtual network
```

In our lab:

``` text
web01
  │
  │ enp1s0
  ▼
QEMU
  │
  ▼
vnet0
  │
  ▼
br-lab
  │
  ▼
redinext
```

The `vnet0` interface is therefore a host-side networking object
associated with the running VM.

------------------------------------------------------------------------

# 12. What is VirtIO?

VirtIO is a family of standardized paravirtualized device interfaces
designed for efficient virtualization.

Examples include:

``` text
virtio-net   → virtual network device
virtio-blk   → virtual block device
virtio-scsi  → virtual SCSI infrastructure
virtio-gpu   → virtual graphics
```

Instead of pretending to be a very old physical device with all of its
hardware quirks, a virtual machine can use a virtualization-aware device
interface.

Conceptually:

``` text
Traditional emulation:

Guest
  │
  ▼
emulated old hardware
  │
  ▼
QEMU
```

Versus:

``` text
VirtIO:

Guest
  │
  ▼
VirtIO driver
  │
  ▼
virtualization-aware backend
```

This reduces unnecessary emulation overhead and is why VirtIO devices
are commonly used in KVM/QEMU environments.

QEMU's documentation specifically discusses VirtIO devices and
mechanisms such as vhost-user for offloading portions of VirtIO
processing. \[5\]

------------------------------------------------------------------------

# 13. What is libvirt?

libvirt is a virtualization management API and framework.

It is **not** the hypervisor itself.

This distinction is critical.

Think of the components this way:

``` text
KVM
→ low-level Linux virtualization

QEMU
→ VM process + machine/device model

libvirt
→ management/API layer
```

libvirt can manage virtualization technologies through drivers.

For our Linux KVM environment, the relevant driver is the QEMU driver.

------------------------------------------------------------------------

# 14. Why was libvirt created?

Imagine managing VMs directly with QEMU commands.

A command can become very large:

``` bash
qemu-system-x86_64 \
  -enable-kvm \
  -m 4096 \
  -smp 2 \
  -drive file=web01.qcow2,format=qcow2 \
  -netdev tap,... \
  -device virtio-net,... \
  -display ...
```

This works, but managing dozens or hundreds of machines manually becomes
difficult.

You need consistent handling for:

-   VM definitions,
-   startup/shutdown,
-   storage,
-   networking,
-   devices,
-   snapshots,
-   lifecycle,
-   authentication,
-   remote management.

libvirt provides an abstraction for these operations.

------------------------------------------------------------------------

# 15. libvirt's mental model

libvirt manages objects such as:

``` text
Host
 │
 ├── Domains
 │     ├── web01
 │     └── db01
 │
 ├── Networks
 │     └── br-lab
 │
 ├── Storage pools
 │     └── nested-vms
 │
 └── Volumes
       ├── web01.qcow2
       └── db01.qcow2
```

libvirt calls virtual machines **domains**.

Therefore:

``` bash
virsh list --all
```

is essentially asking libvirt:

> "Show me the domains you know about."

------------------------------------------------------------------------

# 16. What is `virsh`?

`virsh` is a command-line client for libvirt.

It is not the hypervisor.

It communicates with libvirt.

For example:

``` bash
sudo virsh list --all
```

Conceptually:

``` text
virsh
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
CPU
```

Common commands:

``` bash
virsh list --all
virsh start web01
virsh shutdown web01
virsh destroy web01
virsh dominfo web01
virsh domiflist web01
virsh domblklist web01
virsh dumpxml web01
```

------------------------------------------------------------------------

# 17. What is `virt-install`?

`virt-install` is a command-line provisioning tool that creates
libvirt-managed virtual machines.

For example:

``` bash
sudo virt-install \
    --name web01 \
    --memory 2048 \
    --vcpus 2 \
    --disk size=15 \
    --network bridge=br-lab \
    --os-variant ubuntu24.04
```

Conceptually:

``` text
virt-install
      │
      ▼
libvirt
      │
      ▼
domain definition
      │
      ▼
QEMU
      │
      ▼
KVM
```

`virt-install` is therefore a provisioning tool, not a hypervisor.

------------------------------------------------------------------------

# 18. What is the VM XML?

libvirt represents a VM using a domain definition, commonly stored as
XML.

You can inspect it:

``` bash
sudo virsh dumpxml web01
```

A simplified example:

``` xml
<domain type='kvm'>
  <name>web01</name>

  <memory unit='MiB'>2048</memory>

  <vcpu>2</vcpu>

  <devices>

    <disk type='file'>
      ...
    </disk>

    <interface type='bridge'>
      <source bridge='br-lab'/>
      <model type='virtio'/>
    </interface>

    <graphics type='vnc'>
      ...
    </graphics>

  </devices>
</domain>
```

This definition describes the virtual machine.

It says things such as:

-   VM name,
-   memory,
-   vCPU count,
-   disks,
-   network interfaces,
-   graphics,
-   devices,
-   firmware,
-   boot configuration.

libvirt provides XML schemas and APIs for domains, networks, storage and
related resources. \[6\]

------------------------------------------------------------------------

# 19. What happens when you start a VM?

Suppose you execute:

``` bash
sudo virsh start web01
```

A simplified sequence is:

``` text
1. virsh sends request
          │
          ▼
2. libvirt receives request
          │
          ▼
3. libvirt reads web01 domain definition
          │
          ▼
4. libvirt launches/configures QEMU
          │
          ▼
5. QEMU opens/configures KVM
          │
          ▼
6. KVM creates VM/vCPU state
          │
          ▼
7. QEMU creates virtual devices
          │
          ▼
8. Guest firmware starts
          │
          ▼
9. Guest OS boots
```

The result is a running QEMU process.

You can observe it:

``` bash
ps aux | grep qemu-system
```

------------------------------------------------------------------------

# 20. What actually runs the VM?

This is one of the most important questions.

If you run:

``` bash
ps aux | grep qemu
```

you may see:

``` text
qemu-system-x86_64 ...
```

So is QEMU the VM?

Not exactly.

A more accurate mental model is:

``` text
QEMU process
│
├── virtual machine/device model
│
├── virtual disk handling
│
├── virtual networking
│
├── display/console
│
└── KVM interface
       │
       ▼
   Linux kernel
       │
       ▼
     CPU
```

QEMU is the user-space VMM/device model.

KVM is the kernel-side virtualization mechanism.

Together they provide the virtual machine.

------------------------------------------------------------------------

# 21. What happens when the guest CPU executes instructions?

Consider:

``` text
Guest application
       │
       ▼
Guest Linux kernel
       │
       ▼
Guest CPU instruction
```

Most ordinary guest instructions can execute directly on the physical
CPU under virtualization.

But some operations require intervention by the virtualization layer.

This is where the concept of a **VM exit** matters.

------------------------------------------------------------------------

# 22. What is a VM exit?

A VM exit occurs when the guest is executing in a virtualized CPU
context and an event requires control to return to the host/hypervisor.

Conceptually:

``` text
Guest execution
      │
      ▼
CPU executes guest code
      │
      │
      ├── normal instruction
      │       │
      │       ▼
      │    continue
      │
      └── virtualization-sensitive event
              │
              ▼
           VM exit
              │
              ▼
             KVM
              │
              ▼
        QEMU if needed
              │
              ▼
        resume guest
```

Examples can include certain privileged operations, interrupt-related
events, device accesses and other configured VM-exit conditions.

The exact behavior depends on CPU architecture and virtualization
configuration.

------------------------------------------------------------------------

# 23. Why doesn't every instruction cause a VM exit?

If every guest instruction caused:

``` text
guest → KVM → QEMU → guest
```

virtualization would be extremely expensive.

Hardware virtualization is designed so that large amounts of guest
execution can happen directly on the processor.

The CPU maintains virtualization state and transitions between guest and
host contexts efficiently.

This is one of the fundamental reasons hardware-assisted virtualization
is practical.

------------------------------------------------------------------------

# 24. CPU virtualization in simplified form

For an x86 system:

``` text
                    Physical CPU
                         │
              Intel VT-x / AMD-V
                         │
          ┌──────────────┴──────────────┐
          │                             │
     Host execution              Guest execution
          │                             │
     Linux kernel                  guest OS
          │                             │
          └────────── VM exit ──────────┘
                         │
                         ▼
                        KVM
                         │
                         ▼
                       QEMU
```

This is a simplified conceptual model; the exact implementation involves
hardware VM-control structures, privilege levels, memory virtualization,
interrupts and architecture-specific mechanisms.

------------------------------------------------------------------------

# 25. Guest physical memory vs host physical memory

A guest thinks it has physical memory.

For example:

``` text
web01:

0x00000000 ────────────────┐
                           │
Guest physical memory      │ 4 GB
                           │
0xFFFFFFFF ────────────────┘
```

But that memory is ultimately backed by host memory.

Conceptually:

``` text
Guest virtual address
        │
        ▼
Guest physical address
        │
        ▼
Host physical memory
```

Modern x86 CPUs provide hardware-assisted memory virtualization
mechanisms.

Intel uses technologies such as Extended Page Tables (EPT).

AMD uses Nested Page Tables (NPT/RVI).

KVM coordinates the relevant kernel mechanisms while QEMU manages the
VM's user-space representation.

------------------------------------------------------------------------

# 26. vCPU vs physical CPU

Suppose:

``` text
Host:
8 physical/logical CPUs

VM:
2 vCPUs
```

The VM does not receive two dedicated physical CPUs by default.

Instead:

``` text
web01 vCPU0 ─┐
web01 vCPU1 ─┤
              ├── host scheduler / KVM
db01 vCPU0  ─┤
db01 vCPU1  ─┘
                    │
                    ▼
              physical CPUs
```

The host kernel schedules virtual CPU execution.

This is why allocating too many vCPUs can hurt performance.

More vCPUs does not automatically mean more performance.

------------------------------------------------------------------------

# 27. What is a VM memory allocation?

If we configure:

``` text
web01 = 2048 MiB
```

we are defining the guest's available memory.

The host must have enough memory to support:

``` text
Host OS
+
QEMU overhead
+
web01
+
db01
+
other VMs
```

For a small lab:

``` text
Physical host
16 GB RAM

redinext
6–10 GB

web01
2 GB

db01
2 GB

Host overhead
remaining memory
```

Exact allocation should be based on workload rather than blindly
following a fixed number.

------------------------------------------------------------------------

# 28. Storage virtualization

Suppose:

``` text
/mnt/vmstore/images/web01.qcow2
```

exists on the host.

The guest may see:

``` text
/dev/vda
```

The path is hidden behind the virtual disk controller.

Conceptually:

``` text
Guest filesystem
       │
       ▼
Guest block device
/dev/vda
       │
       ▼
VirtIO block device
       │
       ▼
QEMU
       │
       ▼
qcow2
       │
       ▼
Host filesystem
       │
       ▼
Physical SSD
```

This is an excellent example of abstraction.

The guest does not need to understand the host filesystem.

------------------------------------------------------------------------

# 29. What is qcow2?

`qcow2` is a QEMU disk-image format.

It supports features such as:

-   copy-on-write behavior,
-   snapshots,
-   sparse allocation,
-   backing files,
-   metadata.

A VM might therefore have:

``` text
web01.qcow2
db01.qcow2
```

These are not necessarily the same as physical disks.

They are virtual disk representations managed by QEMU.

You can inspect an image using:

``` bash
qemu-img info web01.qcow2
```

------------------------------------------------------------------------

# 30. Storage pools in libvirt

libvirt adds another management abstraction.

Instead of manually tracking every image, you can define a storage pool:

``` text
nested-vms
      │
      ▼
/mnt/vmstore/images
      │
      ├── web01.qcow2
      └── db01.qcow2
```

Useful commands:

``` bash
virsh pool-list --all
virsh pool-info nested-vms
virsh vol-list nested-vms
```

This separates:

``` text
Where storage exists
```

from:

``` text
How a VM uses the storage
```

------------------------------------------------------------------------

# 31. Virtual networking architecture

A VM network has several layers.

For our lab:

``` text
web01
  │
  │ enp1s0
  ▼
virtual NIC
  │
  ▼
QEMU
  │
  ▼
vnet0
  │
  ▼
br-lab
  │
  ├── redinext
  │
  └── db01 via vnet1
```

The guest sees:

``` text
enp1s0
```

The host sees:

``` text
vnet0
```

The Linux bridge sees:

``` text
vnet0
enp7s0
```

This is why troubleshooting must inspect both sides.

------------------------------------------------------------------------

# 32. Why does `vnet0` exist only while the VM is running?

When the VM is stopped:

``` bash
virsh list --all
```

may show:

``` text
web01 shut off
```

and the host may have no `vnet0`.

When QEMU starts the VM, the networking backend creates the host-side
interface:

``` text
web01
  │
  ▼
QEMU
  │
  ▼
vnet0
```

Therefore:

``` bash
virsh domiflist web01
```

may show the configured interface even when the VM is stopped, while:

``` bash
bridge link
```

only shows the actual host-side interface when it exists.

This distinction was directly relevant when troubleshooting our lab
network.

------------------------------------------------------------------------

# 33. Why did our bridge troubleshooting matter?

We configured:

``` text
br-lab = 10.10.10.10/24
```

and wanted:

``` text
web01 = 10.10.10.20
db01  = 10.10.10.30
```

The intended topology was:

``` text
                    br-lab
                      │
          ┌───────────┼───────────┐
          │           │           │
       redinext     vnet0       vnet1
       .10          │           │
                    ▼           ▼
                  web01       db01
                  .20          .30
```

When `vnet0` was missing from the running bridge, the VM's ARP traffic
could not reach the bridge correctly.

The symptom:

``` text
10.10.10.10 dev enp1s0 FAILED
```

was therefore more useful than simply saying:

> "The VM cannot ping."

The `ip neigh` result indicated an L2 neighbor-resolution failure.

------------------------------------------------------------------------

# 34. Why the bridge MAC and VM MAC are different

A Linux bridge is a Layer-2 forwarding device.

It has its own MAC:

``` text
br-lab
82:20:d7:87:fd:ac
```

The VM has another MAC:

``` text
web01
52:54:00:8b:f6:14
```

That is correct.

Conceptually:

``` text
                 br-lab
              bridge MAC
                  │
          ┌───────┴───────┐
          │               │
        vnet0            vnet1
          │               │
       web01            db01
       VM MAC            VM MAC
```

A bridge learns where destination MAC addresses are reachable.

This is why:

``` bash
bridge fdb show br br-lab
```

is useful when diagnosing virtual Ethernet connectivity.

------------------------------------------------------------------------

# 35. What is a hypervisor?

A hypervisor is software/firmware that enables and manages the execution
of virtual machines.

There are two broad categories.

## Type 1

Often called bare-metal hypervisors.

``` text
Hardware
   │
   ▼
Hypervisor
   │
   ├── VM
   ├── VM
   └── VM
```

Examples include:

-   VMware ESXi
-   Microsoft Hyper-V in its hypervisor role
-   Xen

------------------------------------------------------------------------

## Type 2

Traditionally described as hosted hypervisors.

``` text
Hardware
   │
   ▼
Host OS
   │
   ▼
Virtualization software
   │
   └── VM
```

Desktop products such as VirtualBox are commonly described this way.

Linux KVM does not fit neatly into the simplistic "Type 2" model.

KVM is integrated into the Linux kernel, and Linux itself becomes the
virtualization host.

A more useful description is:

> **KVM turns the Linux kernel into a hardware-assisted virtualization
> platform.**

QEMU then provides the user-space VM/device model, and libvirt manages
it.

------------------------------------------------------------------------

# 36. KVM is not "just a program"

A common beginner mistake is:

``` text
KVM = application
```

More accurately:

``` text
KVM = Linux kernel virtualization subsystem
```

You may see kernel modules such as:

``` bash
lsmod | grep kvm
```

On Intel:

``` text
kvm_intel
kvm
```

On AMD:

``` text
kvm_amd
kvm
```

The exact module configuration depends on the CPU architecture.

------------------------------------------------------------------------

# 37. What is hardware virtualization?

Modern CPUs contain hardware support for virtualization.

On Intel:

``` text
VT-x
```

On AMD:

``` text
AMD-V
```

These features allow the CPU to execute guest operating systems under
controlled virtualization state.

Without appropriate hardware virtualization support, KVM acceleration
may not be available.

Check:

``` bash
lscpu | grep -i virtualization
```

And:

``` bash
ls -l /dev/kvm
```

------------------------------------------------------------------------

# 38. What is nested virtualization?

Nested virtualization means:

``` text
Physical hardware
      │
      ▼
L0 hypervisor/host
      │
      ▼
L1 virtual machine
      │
      ▼
L1 runs another hypervisor
      │
      ▼
L2 virtual machine
```

Our lab uses this architecture:

``` text
Physical laptop
       │
     CachyOS
       │
       │ KVM/libvirt
       ▼
   redinext
       │
       │ KVM/libvirt
       ▼
 ┌──────────────┐
 │ web01        │
 │ db01         │
 └──────────────┘
```

Here:

``` text
CachyOS = L0 host
redinext = L1 guest/hypervisor
web01/db01 = L2 guests
```

The L1 guest needs virtualization extensions exposed to it.

For Intel systems, you may inspect:

``` bash
cat /sys/module/kvm_intel/parameters/nested
```

A nested configuration may report:

``` text
Y
```

Nested virtualization introduces additional complexity and overhead, so
it should be enabled deliberately.

------------------------------------------------------------------------

# 39. Why KVM can be nested

Conceptually:

``` text
Physical CPU
    │
    ▼
L0 KVM
    │
    ▼
redinext sees virtualization capability
    │
    ▼
L1 KVM
    │
    ▼
L2 VM
```

The L0 layer must expose enough virtualization functionality to the L1
guest.

The Linux KVM documentation explicitly includes support and
documentation for running nested guests. \[7\]

------------------------------------------------------------------------

# 40. What is libvirtd?

Historically, many Linux systems used a service called:

``` text
libvirtd
```

Modern libvirt versions may use more modular daemons such as:

``` text
virtqemud
virtnetworkd
virtstoraged
```

The exact service architecture depends on the distribution and libvirt
version.

The important concept is:

``` text
libvirt daemon/service
        │
        ▼
libvirt API
        │
        ▼
QEMU/KVM
```

Do not build your understanding around one daemon name. Build it around
the libvirt API and its drivers.

------------------------------------------------------------------------

# 41. What is a libvirt connection?

libvirt can manage local or remote virtualization hosts.

A connection identifies:

-   which host,
-   which hypervisor,
-   which privilege context.

For example:

``` text
qemu:///system
```

generally refers to the system-level local QEMU/libvirt instance.

A remote connection may use a URI involving SSH.

This abstraction is one reason management software can work with
different virtualization backends.

------------------------------------------------------------------------

# 42. Cockpit's position in the stack

Cockpit is not another hypervisor.

For VM management, Cockpit can use libvirt.

Conceptually:

``` text
Browser
   │
   ▼
Cockpit
   │
   ▼
libvirt
   │
   ▼
QEMU
   │
   ▼
KVM
```

Therefore, if Cockpit has a problem displaying a VM console, that does
not automatically mean:

``` text
KVM is broken
```

The failure may be in:

``` text
Cockpit
browser
console protocol
QEMU graphics configuration
guest graphics stack
```

This layered model is extremely useful during troubleshooting.

------------------------------------------------------------------------

# 43. VNC and SPICE in this architecture

A VM can have a virtual display.

For example, libvirt XML may contain:

``` xml
<graphics type='vnc' ... />
```

QEMU then provides a VNC endpoint for the virtual display.

The path becomes:

``` text
Browser/VNC client
       │
       ▼
QEMU VNC server
       │
       ▼
virtual display
       │
       ▼
guest OS
```

This is different from installing a VNC server inside Ubuntu.

### QEMU VNC

Provides the VM console.

### Guest VNC server

Provides a remote desktop session from inside the guest OS.

These should not be confused.

------------------------------------------------------------------------

# 44. Why SSH is often better for servers

For infrastructure servers:

``` text
SSH
```

is usually preferable to maintaining a full desktop environment.

A server can be administered using:

``` bash
ssh user@10.10.10.20
```

Then:

``` bash
systemctl
journalctl
ip
ss
tcpdump
virsh
apt
```

This reduces dependencies and usually reduces attack surface.

A graphical console is still valuable for:

-   OS installation,
-   boot troubleshooting,
-   broken networking,
-   broken SSH,
-   kernel issues,
-   display-manager testing.

------------------------------------------------------------------------

# 45. The complete architecture of our lab

Our final environment can be represented as:

``` text
                    Physical Laptop
                          │
                          ▼
                      CachyOS
                          │
                    KVM + libvirt
                          │
                          ▼
                    ┌───────────┐
                    │ redinext  │
                    │ Ubuntu    │
                    │ Server    │
                    └─────┬─────┘
                          │
                       libvirt
                          │
                        QEMU
                    ┌─────┴─────┐
                    │           │
                  web01       db01
                  Ubuntu      Ubuntu
                    │           │
                  vnet0       vnet1
                    └─────┬─────┘
                          │
                       br-lab
```

With:

``` text
redinext = 10.10.10.10
web01    = 10.10.10.20
db01     = 10.10.10.30
```

------------------------------------------------------------------------

# 46. The stack in one table

  -----------------------------------------------------------------------
  Component               What it is              Main responsibility
  ----------------------- ----------------------- -----------------------
  CPU virtualization      Hardware feature        Provides virtualization
                                                  extensions

  KVM                     Linux kernel subsystem  Hardware-assisted
                                                  VM/vCPU execution

  QEMU                    User-space VMM/device   Provides virtual
                          model                   machine and devices

  libvirt                 Management              Defines and manages
                          API/framework           VMs, networks, storage

  virsh                   CLI client              Controls libvirt

  virt-install            Provisioning tool       Creates libvirt-managed
                                                  VMs

  virt-manager            GUI client              Manages libvirt
                                                  resources

  Cockpit                 Web management          Provides web-based
                          interface               host/VM management

  VirtIO                  Virtual device          Efficient guest↔host
                          interfaces              I/O

  qcow2                   Disk image format       Stores virtual disk
                                                  data

  Linux bridge            L2 network device       Connects VM/host
                                                  interfaces

  vnetX                   Host-side VM interface  Connects QEMU
                                                  networking to Linux
                                                  networking
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 47. A useful analogy

Think about a physical data center.

### Hardware

``` text
Physical server
```

### KVM

``` text
CPU virtualization machinery
```

### QEMU

``` text
Creates the virtual machine's hardware model
```

### libvirt

``` text
Infrastructure management/control plane
```

### virsh

``` text
Command-line management console
```

### virt-install

``` text
VM provisioning utility
```

### Cockpit

``` text
Web management console
```

The analogy is imperfect, but it helps separate responsibilities.

------------------------------------------------------------------------

# 48. What happens when you run `virsh start web01`?

Let's trace it end-to-end.

``` text
$ virsh start web01
```

### Step 1

`virsh` is a client.

``` text
virsh
```

sends a request to libvirt.

### Step 2

libvirt identifies:

``` text
domain = web01
driver = QEMU
```

### Step 3

libvirt reads the VM definition.

### Step 4

libvirt prepares required resources:

``` text
disk
network
devices
console
graphics
```

### Step 5

QEMU is started.

### Step 6

QEMU communicates with KVM.

### Step 7

KVM creates the required VM/vCPU state.

### Step 8

QEMU presents virtual hardware.

### Step 9

The guest firmware starts.

### Step 10

The guest OS boots.

At the host level, the final result is approximately:

``` text
libvirt
   │
   └── qemu-system-x86_64
             │
             └── /dev/kvm
```

------------------------------------------------------------------------

# 49. Why the architecture is modular

This architecture separates concerns.

Suppose the VM cannot ping another machine.

You can investigate:

``` text
Guest configuration
       ↓
Virtual NIC
       ↓
QEMU
       ↓
vnet0
       ↓
Linux bridge
       ↓
Host routing
       ↓
Firewall
       ↓
Physical network
```

Suppose the VM will not boot.

Investigate:

``` text
libvirt definition
       ↓
QEMU
       ↓
disk
       ↓
firmware
       ↓
KVM
       ↓
CPU
```

Suppose Cockpit cannot show the console.

Investigate:

``` text
Browser
   ↓
Cockpit
   ↓
libvirt
   ↓
QEMU graphics
   ↓
VM display
```

The value of understanding the architecture is therefore not merely
theoretical.

It gives you a troubleshooting map.

------------------------------------------------------------------------

# 50. Commands for learning the stack

## KVM

``` bash
ls -l /dev/kvm
lsmod | grep kvm
lscpu | grep -i virtualization
```

## QEMU

``` bash
ps aux | grep qemu-system
qemu-system-x86_64 --version
qemu-img --version
qemu-img info web01.qcow2
```

## libvirt

``` bash
virsh version
virsh list --all
virsh dominfo web01
virsh dumpxml web01
virsh domiflist web01
virsh domblklist web01
```

## Networks

``` bash
ip -br addr
ip route
ip neigh
bridge link
bridge fdb show
ss -tulpn
```

## Storage

``` bash
virsh pool-list --all
virsh pool-info nested-vms
virsh vol-list nested-vms
lsblk -f
df -h
```

------------------------------------------------------------------------

# 51. Practical experiment: see the QEMU process

Start a VM:

``` bash
sudo virsh start web01
```

Then:

``` bash
ps aux | grep '[q]emu-system'
```

Observe the QEMU command line.

Then:

``` bash
sudo virsh dominfo web01
```

Compare the information.

Then:

``` bash
sudo virsh dumpxml web01
```

Look for:

``` xml
<memory>
<vcpu>
<disk>
<interface>
<graphics>
```

You are now looking at the same VM from three different layers:

``` text
process
  ↓
libvirt domain
  ↓
QEMU virtual machine
```

------------------------------------------------------------------------

# 52. Practical experiment: observe the virtual NIC

Start:

``` bash
sudo virsh start web01
```

Then:

``` bash
sudo virsh domiflist web01
```

Find:

``` text
vnet0
```

Then:

``` bash
ip link show vnet0
```

Then:

``` bash
bridge link
```

Then:

``` bash
bridge fdb show br br-lab
```

You can now observe:

``` text
VM
 ↓
QEMU
 ↓
vnet0
 ↓
br-lab
```

This is much more useful than memorizing the name `vnet0`.

------------------------------------------------------------------------

# 53. Practical experiment: observe a VM's disk

Run:

``` bash
sudo virsh domblklist web01
```

You might see:

``` text
Target   Source
vda      /mnt/vmstore/images/web01.qcow2
```

Then:

``` bash
qemu-img info /mnt/vmstore/images/web01.qcow2
```

Now compare:

``` text
Guest:
    /dev/vda

Host:
    web01.qcow2
```

The virtualization layer maps one abstraction to another.

------------------------------------------------------------------------

# 54. Practical experiment: inspect the domain XML

Run:

``` bash
sudo virsh dumpxml web01 > web01.xml
```

Read the file.

Identify:

``` text
<name>
<memory>
<vcpu>
<disk>
<interface>
<graphics>
```

Then change nothing.

The goal of this exercise is simply to learn how a virtual machine is
represented declaratively.

------------------------------------------------------------------------

# 55. What should you remember?

If you forget everything else, remember this:

``` text
CPU hardware
    │
    ▼
KVM
    │
    ▼
QEMU
    │
    ▼
libvirt
    │
    ▼
virsh / virt-install / Cockpit / virt-manager
```

But for technical accuracy, the control relationship is better pictured
as:

``` text
                Management tools
       ┌──────────┬───────────┬───────────┐
       │          │           │           │
     virsh   virt-install  Cockpit   virt-manager
       │          │           │           │
       └──────────┴─────┬─────┴───────────┘
                        │
                     libvirt
                        │
                     QEMU
                        │
                      KVM
                        │
               CPU virtualization
                        │
                     hardware
```

The critical distinction is:

> **KVM executes and virtualizes CPU/memory operations in the Linux
> kernel. QEMU models the machine and its devices in user space. libvirt
> manages the virtualization stack through an API.**

------------------------------------------------------------------------

# 56. Common misconceptions

## "KVM is a VM manager."

Not primarily.

KVM is the Linux kernel virtualization subsystem.

Use libvirt or another management layer to manage VMs conveniently.

------------------------------------------------------------------------

## "QEMU is only an emulator."

No.

QEMU supports both software emulation and virtualization acceleration.

With KVM:

``` text
QEMU + KVM
```

is a very common high-performance virtualization stack.

------------------------------------------------------------------------

## "libvirt creates the CPU virtualization."

No.

libvirt manages virtualization resources.

KVM provides the Linux kernel virtualization functionality.

------------------------------------------------------------------------

## "virsh is the hypervisor."

No.

`virsh` is a command-line client for libvirt.

------------------------------------------------------------------------

## "virt-install is the hypervisor."

No.

It is a provisioning tool.

------------------------------------------------------------------------

## "A qcow2 file is a real disk."

It is a virtual disk image.

The guest sees a virtual block device.

------------------------------------------------------------------------

## "vnet0 is the VM's Ethernet card."

Not exactly.

The guest has a virtual NIC such as `enp1s0`.

`vnet0` is a host-side virtual network interface associated with the
VM's networking path.

------------------------------------------------------------------------

## "The bridge MAC and VM MAC should match."

No.

They should normally be distinct.

------------------------------------------------------------------------

# 57. Security perspective

Understanding this stack is also important for security.

A VM is not magically isolated simply because it is called a VM.

The attack surface includes:

``` text
Guest OS
   │
virtual devices
   │
QEMU
   │
libvirt
   │
Linux kernel
   │
hardware
```

Potential security boundaries include:

-   guest-to-host interfaces,
-   virtual device emulation,
-   QEMU process isolation,
-   libvirt access controls,
-   storage permissions,
-   network segmentation,
-   device passthrough,
-   host kernel security.

This is why virtualization security is not simply:

> "The VM is isolated."

A better question is:

> **Which boundary is responsible for isolating which resource?**

------------------------------------------------------------------------

# 58. Why this matters for cybersecurity

For offensive-security and defensive-security work, understanding the
virtualization stack helps with:

### Infrastructure enumeration

You can identify:

``` text
KVM
QEMU
libvirt
VirtIO
virtual bridges
```

### Host/guest boundary analysis

You understand:

``` text
guest
 ↓
virtual device
 ↓
QEMU
 ↓
kernel
```

### Network security

You understand:

``` text
VM NIC
 ↓
vnet
 ↓
bridge
 ↓
host
 ↓
uplink
```

### Privilege boundaries

You can reason about:

``` text
guest root
≠
host root
```

and understand why virtualization escape vulnerabilities are
significant.

### Lab construction

You can create isolated environments for:

``` text
AD labs
malware analysis
network security testing
web security testing
exploit development
Linux kernel research
```

without needing separate physical machines for every system.

------------------------------------------------------------------------

# 59. Final mental model

Think of KVM/QEMU/libvirt as three different jobs.

### KVM

**"I make the Linux kernel capable of running virtual CPUs using
hardware virtualization."**

### QEMU

**"I provide the virtual machine and make it look like a computer with
CPU, memory, disks, network cards, display and other devices."**

### libvirt

**"I provide a consistent management interface for defining, starting,
stopping and configuring those virtual machines and their related
resources."**

Then:

### virsh

**"I am a command-line client that talks to libvirt."**

### virt-install

**"I help provision new libvirt-managed VMs."**

### Cockpit / virt-manager

**"I provide graphical management interfaces over the virtualization
management layer."**

------------------------------------------------------------------------

# 60. References and further reading

Prefer primary documentation when learning virtualization.

1.  **Linux Kernel --- KVM documentation**\
    https://www.kernel.org/doc/html/latest/virt/kvm/

2.  **Linux Kernel --- KVM API**\
    https://www.kernel.org/doc/html/latest/virt/kvm/api.html

3.  **QEMU --- About QEMU**\
    https://www.qemu.org/docs/master/about/

4.  **QEMU --- System Emulation**\
    https://www.qemu.org/docs/master/system/

5.  **QEMU --- Virtualization Accelerators and VirtIO**\
    https://www.qemu.org/docs/master/system/introduction.html

6.  **libvirt --- Documentation**\
    https://www.libvirt.org/docs/

7.  **libvirt --- API Concepts**\
    https://libvirt.org/api.html

8.  **libvirt --- Domain XML format**\
    https://libvirt.org/formatdomain.html

9.  **libvirt --- Network XML format**\
    https://libvirt.org/formatnetwork.html

10. **Ubuntu Server --- Virtualisation**\
    https://documentation.ubuntu.com/server/how-to/virtualisation/

11. **ArchWiki --- KVM**\
    https://wiki.archlinux.org/title/KVM

12. **ArchWiki --- libvirt**\
    https://wiki.archlinux.org/title/Libvirt

------------------------------------------------------------------------

# 61. Suggested learning sequence

Do not try to memorize the entire stack at once.

Study it in this order:

``` text
1. CPU virtualization
       ↓
2. Intel VT-x / AMD-V
       ↓
3. KVM
       ↓
4. /dev/kvm and KVM API
       ↓
5. QEMU
       ↓
6. QEMU + KVM
       ↓
7. virtual devices
       ↓
8. VirtIO
       ↓
9. libvirt
       ↓
10. virsh
       ↓
11. virt-install
       ↓
12. libvirt networking
       ↓
13. virtual storage
       ↓
14. VM lifecycle
       ↓
15. nested virtualization
       ↓
16. virtualization security
```

The goal is not to become good at:

``` bash
virsh start web01
```

The goal is to understand **what happens after you execute it**.

Once you understand the stack, the commands become tools rather than
magic.
