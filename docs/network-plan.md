# Network plan

## Lab machines

| Machine | Role | Address |
|---|---|---|
| Windows PC (physical) | Admin and employee browsers, Windows agent, simulator | 192.168.56.1 |
| Linux VM (VirtualBox) | FastAPI server and SQLite database | 192.168.56.10 |

The addresses are examples. Check the real subnet of your VirtualBox Host-Only network and make sure it does not clash with your home or office network.

## VirtualBox configuration

| Network | Purpose | Settings |
|---|---|---|
| Host-Only network | Private lab LAN between the PC and the VM | `192.168.56.1/24`, DHCP server disabled |
| NAT adapter (Linux VM only) | Internet access for package installs | Default NAT |

Linux VM adapters: Adapter 1 is NAT, Adapter 2 is Host-Only.

## Linux static address (netplan)

```yaml
network:
  version: 2
  ethernets:
    enp0s3:
      dhcp4: true
    enp0s8:
      addresses: [192.168.56.10/24]
```

Interface names can differ (check with `ip a`). Apply with `sudo netplan apply`. A static address means the agent can always find the server.

## Ports and traffic

| From | To | Port | Purpose |
|---|---|---|---|
| Browsers and agents (PC) | Linux VM | 8000/tcp | Web UI and REST API over HTTP |
| PC | Linux VM | 22/tcp | SSH administration |
| PC and VM | each other | ICMP | Connectivity tests |

The PC needs an inbound ICMP rule if the VM must ping it:

```powershell
New-NetFirewallRule -DisplayName "Allow ICMPv4 In" -Protocol ICMPv4 -IcmpType 8 -Direction Inbound -Action Allow
```

## Connectivity checklist
- PC to VM: `ping 192.168.56.10`
- VM to PC: `ping 192.168.56.1`
- SSH from the PC: `ssh user@192.168.56.10`
- API reachable: open `http://192.168.56.10:8000/health` in the PC browser
- Internet from the VM (through NAT): `sudo apt update`

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser cannot open port 8000 but `curl localhost:8000` works on the VM | Uvicorn started without `--host 0.0.0.0`, or a firewall blocks port 8000 |
| Agent logs `Attempt 1/3 ... failed` | VM or API not running, or wrong `server_url` in `config.json` |
| Agent exits with "Server rejected the agent token" | `agent_token` does not match `AGENT_TOKEN` in `backend/.env` |
| `enp0s8` has no address | The netplan file is missing or badly indented |
