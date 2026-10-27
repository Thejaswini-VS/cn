import simpy
import ipaddress

LINK_DELAY = 0.010
PROCESS_DELAY = 0.005
INTERVAL = 0.100
PACKETS = 5

# 1. Network nodes
nodes = {
    'PC1': {'ip': '192.168.1.10', 'type': 'End Node'},
    'PC2': {'ip': '192.168.1.20', 'type': 'End Node'},
    'PC3': {'ip': '192.168.1.30', 'type': 'End Node'},
    'PC4': {'ip': '192.168.2.10', 'type': 'End Node'},
    'PC5': {'ip': '192.168.3.20', 'type': 'End Node'},
    'PC6': {'ip': '192.168.3.30', 'type': 'End Node'},
    'R1':  {'ip': '192.168.1.1', 'type': 'Router'},
    'R2':  {'ip': '192.168.2.1', 'type': 'Router'},
    'R3':  {'ip': '192.168.3.1', 'type': 'Router'}
}

networks = {
    '192.168.1.0/24': 'R1',
    '192.168.2.0/24': 'R2',
    '192.168.3.0/24': 'R3'
}

# 2. Routing tables
routes = {
    'R1': {
        '192.168.1.0/24': 'DIRECT',
        '192.168.2.0/24': 'R2',
        '192.168.3.0/24': 'R2'
    },
    'R2': {
        '192.168.1.0/24': 'R1',
        '192.168.2.0/24': 'DIRECT',
        '192.168.3.0/24': 'R3'
    },
    'R3': {
        '192.168.1.0/24': 'R2',
        '192.168.2.0/24': 'R2',
        '192.168.3.0/24': 'DIRECT'
    }
}


def get_network(ip):
    return str(ipaddress.ip_network(ip + '/24', strict=False))


# 3. Communication link
class Link:
    def __init__(self, env):
        self.env = env

    def transmit(self, packet, source, destination):
        entry = self.env.now
        yield self.env.timeout(LINK_DELAY)
        exit_time = self.env.now

        packet['link_times'].append(
            (source, destination, entry, exit_time)
        )


# 4. Router
class Router:
    def __init__(self, env, name, table):
        self.env = env
        self.name = name
        self.table = table

    def forward(self, packet):
        packet['hop_count'] += 1

        print(f"{self.env.now:.3f}s: {self.name} received "
              f"{packet['id']}")

        yield self.env.timeout(PROCESS_DELAY)

        destination_net = get_network(packet['destination'])
        next_hop = self.table.get(destination_net)

        print(f"{self.env.now:.3f}s: {self.name} "
              f"lookup -> {next_hop or 'NO ROUTE'}")

        return next_hop


# 5. Packet routing
def route_packet(env, packet, source, destination,
                 links, routers, results):

    start = packet['generation_time']
    src_net = get_network(source)
    dst_net = get_network(destination)

    packet['path'] = [packet['source']]
    packet['hop_count'] = 0
    packet['link_times'] = []

    # Same-network communication
    if src_net == dst_net:
        yield env.process(
            links.transmit(packet, packet['source'], packet['destination'])
        )

        packet['path'].append(packet['destination'])
        packet['status'] = 'DELIVERED'

    else:
        # Send packet to the first router
        router = networks.get(src_net)

        if router is None:
            packet['status'] = 'DROPPED'
            results.append(packet)
            return

        yield env.process(
            links.transmit(packet, packet['source'], router)
        )
        packet['path'].append(router)

        while True:
            next_hop = yield env.process(
                routers[router].forward(packet)
            )

            # No matching route
            if next_hop is None:
                packet['status'] = 'DROPPED'
                print(f"{env.now:.3f}s: {packet['id']} DROPPED")
                break

            # Destination network directly connected
            if next_hop == 'DIRECT':
                destination_node = next(
                    (name for name, info in nodes.items()
                     if info['ip'] == packet['destination']
                     and info['type'] == 'End Node'),
                    None
                )

                if destination_node is None:
                    packet['status'] = 'DROPPED'
                    break

                yield env.process(
                    links.transmit(
                        packet, router, destination_node
                    )
                )

                packet['path'].append(destination_node)
                packet['status'] = 'DELIVERED'
                break

            # Forward to the next router
            yield env.process(
                links.transmit(packet, router, next_hop)
            )

            router = next_hop
            packet['path'].append(router)

    packet['delivery_time'] = env.now
    packet['delay'] = env.now - start

    print(f"{env.now:.3f}s: {packet['id']} "
          f"{packet['status']} | "
          f"Path: {' -> '.join(packet['path'])}")

    results.append(packet)


# 6. Packet generation
def generate(env, test_id, source, destination,
             links, routers, results):

    for i in range(1, PACKETS + 1):
        packet = {
            'id': f'{test_id}-P{i}',
            'source': source,
            'destination': destination,
            'payload': 'Data packet of 512 bytes',
            'generation_time': env.now,
            'hop_count': 0,
            'path': [],
            'link_times': [],
            'status': 'PENDING'
        }

        print(f"\n{packet['id']} generated "
              f"at {env.now:.3f}s")

        env.process(
            route_packet(
                env, packet,
                nodes[source]['ip'], destination,
                links, routers, results
            )
        )

        yield env.timeout(INTERVAL)


# 7. Run a test case
def run_test(test_id, source, destination):

    env = simpy.Environment()
    links = Link(env)

    routers = {
        name: Router(env, name, routes[name])
        for name in routes
    }

    results = []

    env.process(
        generate(
            env, test_id, source, destination,
            links, routers, results
        )
    )

    env.run()

    delivered = sum(
        p['status'] == 'DELIVERED' for p in results
    )
    dropped = len(results) - delivered

    print(f"\n--- {test_id} RESULTS ---")
    print("Source      :", source)
    print("Destination :", destination)

    if results:
        first = results[0]

        print("Path        :", " -> ".join(first['path']))
        print("Hop Count   :", first['hop_count'])
        print("Status      :", first['status'])

    print("Packets Sent:", len(results))
    print("Delivered   :", delivered)
    print("Dropped     :", dropped)

    delays = [
        p['delay'] * 1000
        for p in results
        if p['status'] == 'DELIVERED'
    ]

    if delays:
        print("Average Delay:",
              round(sum(delays) / len(delays), 2), "ms")
    else:
        print("Average Delay: N/A")


# 8. Five required scenarios
tests = [
    ('TC1', 'PC1', '192.168.1.20'),
    ('TC2', 'PC1', '192.168.2.10'),
    ('TC3', 'PC2', '192.168.3.20'),
    ('TC4', 'PC6', '192.168.1.30'),
    ('TC5', 'PC1', '192.168.4.10')
]

print("SIMPY IP ROUTING SIMULATION")

for test_id, source, destination in tests:
    run_test(test_id, source, destination)