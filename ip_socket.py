import socket
import ipaddress
import time

nodes = {
    'PC1': '192.168.1.10', 'PC2': '192.168.1.20',
    'PC3': '192.168.1.30', 'PC4': '192.168.2.10',
    'PC5': '192.168.3.20', 'PC6': '192.168.3.30'
}

networks = {
    '192.168.1.0/24': 'R1',
    '192.168.2.0/24': 'R2',
    '192.168.3.0/24': 'R3'
}

routes = {
    'R1': {'192.168.1.0/24': 'DIRECT',
           '192.168.2.0/24': 'R2', '192.168.3.0/24': 'R2'},
    'R2': {'192.168.1.0/24': 'R1',
           '192.168.2.0/24': 'DIRECT', '192.168.3.0/24': 'R3'},
    'R3': {'192.168.1.0/24': 'R2',
           '192.168.2.0/24': 'R2', '192.168.3.0/24': 'DIRECT'}
}

def net(ip):
    return str(ipaddress.ip_network(ip + '/24', strict=False))

def route(src, dst):
    path = [src]
    hops = 0

    if net(src) == net(dst):
        return path + [dst], hops, 'DELIVERED'

    router = networks.get(net(src))
    if not router:
        return path, hops, 'DROPPED'

    path.append(router)

    while True:
        hops += 1
        time.sleep(0.005)
        next_hop = routes[router].get(net(dst))

        print(router, "lookup ->", next_hop)

        if next_hop is None:
            return path, hops, 'DROPPED'

        if next_hop == 'DIRECT':
            dest = next((n for n, ip in nodes.items()
                         if ip == dst), None)
            if dest:
                path.append(dest)
                return path, hops, 'DELIVERED'
            return path, hops, 'DROPPED'

        path.append(next_hop)
        router = next_hop

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('localhost', 5000))
s.listen(5)

print("IP Routing Server running...")

while True:
    c, addr = s.accept()
    data = c.recv(1024).decode().split()

    source, destination = data
    start = time.time()

    path, hops, status = route(nodes[source], destination)

    delay = (time.time() - start) * 1000

    reply = (f"Path: {' -> '.join(path)}\n"
             f"Hop Count: {hops}\n"
             f"Status: {status}\n"
             f"Delay: {delay:.2f} ms")

    print(reply)
    c.sendall(reply.encode())
    c.close()



import socket

tests = [
    ('TC1', 'PC1', '192.168.1.20'),
    ('TC2', 'PC1', '192.168.2.10'),
    ('TC3', 'PC2', '192.168.3.20'),
    ('TC4', 'PC6', '192.168.1.30'),
    ('TC5', 'PC1', '192.168.4.10')
]

for tid, source, destination in tests:
    s = socket.socket()
    s.connect(('localhost', 5000))
    s.sendall(f"{source} {destination}".encode())

    result = s.recv(1024).decode()
    print(f"\n--- {tid} ---")
    print("Source:", source)
    print("Destination:", destination)
    print(result)

    s.close()