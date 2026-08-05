# Lesson 1 - Introduction to Network Devices

Before learning routing, switching, subnetting, or network security, it is important to understand the devices that make communication possible. Every packet that travels across a network passes through one or more of these devices.

---

# What is a Host?

A **Host** is any device that can send, receive, or process data over a network.

Every host has a unique identity (IP address) that allows other devices to communicate with it.

### Examples

- Laptop
- Desktop Computer
- Mobile Phone
- Printer
- Web Server
- Database Server
- Cloud Virtual Machine (AWS EC2, Azure VM)
- IoT Devices (Smart TVs, Cameras, Sensors)

> Think of a host as any endpoint capable of participating in network communication.

---

# Client

A **Client** is a host that **initiates communication** by sending a request to another device.

Clients consume services provided by servers.

### Examples

- Opening Google in your browser
- Mobile banking application
- Email application
- FTP client
- SSH client

### Example

When you visit:

```
https://example.com
```

Your browser acts as the **client**.

It sends an HTTP request asking for the webpage.

---

# Server

A **Server** is a host that **provides services** or resources to clients.

Unlike clients, servers continuously listen for incoming requests.

### Common Types of Servers

- Web Server
- DNS Server
- Mail Server
- Database Server
- FTP Server
- DHCP Server
- File Server

### Example

```
Browser  ------------->  Web Server
        HTTP Request

Browser  <-------------  Web Server
        HTML Response
```

The browser requests a webpage.

The server processes the request and sends the requested data back.

---

# Client-Server Communication

A simple communication flow looks like this:

```
+-----------+                     +------------+
|  Client   | ---- Request -----> |   Server   |
| (Browser) |                     | Apache/Nginx |
|           | <--- Response ----- |            |
+-----------+                     +------------+
```

Examples

| Client | Server |
|---------|--------|
| Browser | Web Server |
| Outlook | Mail Server |
| Mobile App | API Server |
| SSH Client | SSH Server |

---

# IP Address (Internet Protocol Address)

An **IP Address** is the logical address assigned to every host on a network.

It uniquely identifies a device and allows packets to reach the correct destination.

Think of it as the **postal address** of a device.

Without an IP address, devices cannot communicate across IP networks.

---

## IPv4

IPv4 uses **32 bits**.

Each bit can be either:

```
0
or
1
```

Those 32 bits are divided into **4 groups of 8 bits (octets).**

Example:

```
192.168.1.10
```

Binary representation

```
11000000.10101000.00000001.00001010
```

Each octet ranges from:

```
0 - 255
```

because

```
11111111 = 255
```

---

## IPv6

IPv6 was introduced because IPv4 addresses are limited.

IPv6 uses **128 bits**.

Example:

```
2001:db8::1
```

---

# Network

A **Network** is a collection of devices connected together so they can exchange information.

Networks can be:

- Home Network
- Office Network
- University Network
- Data Center
- Cloud Network
- Internet

A network may also contain multiple smaller networks called **subnets**.

Example

```
Company Network

│
├── HR Subnet
├── Finance Subnet
├── Development Subnet
└── Guest Wi-Fi
```

Each subnet isolates traffic while still allowing controlled communication.

---

# Repeater

A **Repeater** is a Layer 1 (Physical Layer) device.

Its job is simple:

- Receive a weak electrical or optical signal.
- Regenerate it.
- Forward the regenerated signal.

Repeaters **do not understand IP addresses or MAC addresses.**

They simply strengthen signals.

### Why is a repeater needed?

Signals weaken as they travel through cables.

This weakening is called **attenuation**.

A repeater restores the signal before forwarding it.

```
PC -------- Repeater -------- PC
```

---

# Hub

A **Hub** is essentially a **multi-port repeater**.

Like a repeater, it operates at **OSI Layer 1**.

When a hub receives data:

- It does NOT inspect the packet.
- It does NOT know the destination.
- It simply copies the data to **every connected port**.

Example

```
      Hub

   /   |   \
 PC1  PC2  PC3
```

If PC1 sends data,

both PC2 and PC3 receive it.

Only the intended recipient processes it.

Everyone else discards it.

---

## Problems with Hubs

- Large collision domains
- Poor performance
- Shared bandwidth
- No security
- Inefficient communication

Because of these limitations, hubs are rarely used today.

Switches replaced hubs.

---

# Bridge

A **Bridge** connects two separate network segments.

Unlike a hub, a bridge understands **MAC addresses**.

It operates at **OSI Layer 2 (Data Link Layer).**

A bridge learns which devices exist on each side and forwards traffic only when necessary.

Example

```
LAN A ---- Bridge ---- LAN B
```

Benefits

- Reduces collisions
- Improves performance
- Filters unnecessary traffic

Bridges were commonly used before switches became popular.

Modern switches are essentially multi-port bridges.

---

# Switch

A **Switch** is a Layer 2 networking device that connects multiple devices within the same Local Area Network (LAN).

Unlike hubs, switches intelligently forward frames only to the correct destination.

---

## How does a switch work?

Every network interface has a unique **MAC Address**.

A switch builds a **MAC Address Table (CAM Table)**.

Example

```
MAC Address           Port

AA:AA:AA:AA:AA:01      1
BB:BB:BB:BB:BB:02      2
CC:CC:CC:CC:CC:03      3
```

When data arrives,

the switch checks the destination MAC address.

If found,

the frame is forwarded only to the correct port.

Instead of broadcasting to everyone.

---

## Benefits

- Faster communication
- Dedicated bandwidth
- Fewer collisions
- Better performance
- More secure than hubs

---

# Switching

**Switching** is the process of forwarding Ethernet frames between devices inside the same network.

A switch makes forwarding decisions using:

- MAC Address
- MAC Address Table

Switching happens inside a LAN.

---

# Router

A **Router** connects different networks together.

Unlike switches, routers understand **IP addresses**.

Routers operate at **OSI Layer 3 (Network Layer).**

Examples

- Home Wi-Fi Router
- ISP Router
- Enterprise Core Router
- Cloud Virtual Router

---

## Why is a router needed?

Suppose you have:

```
192.168.1.0/24
```

and

```
10.10.10.0/24
```

These are two different networks.

Devices in one network cannot directly communicate with the other.

A router forwards packets between them.

```
Network A ---- Router ---- Network B
```

---

## How does a router work?

When a packet arrives,

the router checks:

- Destination IP Address
- Routing Table

It then determines the best path to forward the packet.

---

# Routing

**Routing** is the process of moving packets between different networks.

Routing decisions are based on:

- Destination IP Address
- Routing Table
- Routing Protocols

Examples of routing protocols include:

- OSPF
- RIP
- EIGRP
- BGP

---

# Switch vs Router

| Feature | Switch | Router |
|----------|---------|---------|
| OSI Layer | Layer 2 | Layer 3 |
| Uses | MAC Address | IP Address |
| Connects | Devices within same network | Different networks |
| Decision Based On | MAC Table | Routing Table |
| Performs | Switching | Routing |

---

# Summary

| Device | Primary Function | OSI Layer |
|----------|-----------------|-----------|
| Host | Sends and receives data | All Layers |
| Client | Requests services | Application |
| Server | Provides services | Application |
| Repeater | Regenerates signals | Layer 1 |
| Hub | Broadcasts signals to all ports | Layer 1 |
| Bridge | Connects LAN segments using MAC addresses | Layer 2 |
| Switch | Connects devices within a LAN | Layer 2 |
| Router | Connects different networks | Layer 3 |

---

# Key Takeaways

- Every communicating device is called a **Host**.
- Clients request services; servers provide them.
- Every host requires an **IP address** for communication.
- A **Repeater** strengthens signals.
- A **Hub** blindly forwards data to every device.
- A **Bridge** filters traffic using MAC addresses.
- A **Switch** forwards frames intelligently within a LAN.
- A **Router** forwards packets between different networks using IP addresses.
- Switching occurs **inside** a network, while routing occurs **between** different networks.
