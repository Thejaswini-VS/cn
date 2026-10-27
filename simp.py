
import simpy

def generate(env, pending, total, size, rate):
    for seq in range(1, total // size + 1):
        yield env.timeout(size / rate)
        yield pending.put((seq, size))


def transmit(env, chan, pack):
    yield env.timeout(0.1)
    yield chan.put(pack)


def client(env, pending, chan, ackchan, window, stats):
    outstanding = {}
    rwnd = 8

    def receive_ack(env):
        nonlocal rwnd
        while True:
            kind, seq, rwnd = yield ackchan.get()
            if kind == 'ACK':
                for s in list(outstanding):
                    if s <= seq:
                        del outstanding[s]

    env.process(receive_ack(env))

    for _ in range(stats['total']):
        pack = yield pending.get()
        seq, size = pack

        while sum(outstanding.values()) + size > min(window, rwnd):
            yield env.timeout(0.05)

        outstanding[seq] = size
        stats['sent'] += 1
        env.process(transmit(env, chan, pack))

    while outstanding or stats['received'] < stats['total']:
        yield env.timeout(0.05)


def server(env, chan, queue, ackchan, buffer_size, stats):
    occupancy = 0

    def process(env):
        nonlocal occupancy
        while True:
            seq, size = yield queue.get()
            yield env.timeout(size / 4)
            occupancy -= size
            yield ackchan.put(('WINDOW', None, buffer_size - occupancy))

    env.process(process(env))

    while True:
        seq, size = yield chan.get()

        while occupancy + size > buffer_size:
            yield env.timeout(0.05)

        occupancy += size
        stats['received'] += 1
        yield queue.put((seq, size))
        yield ackchan.put(('ACK', seq, buffer_size - occupancy))

env = simpy.Environment()
pending = simpy.Store(env)
chan = simpy.Store(env)
queue = simpy.Store(env)
ackchan = simpy.Store(env)

stats = {'total': 10, 'sent': 0, 'received': 0}

env.process(generate(env, pending, 10, 1, 2))
env.process(server(env, chan, queue, ackchan, 8, stats))
env.process(client(env, pending, chan, ackchan, 4, stats))

env.run(until=20)

print("Segments sent:", stats['sent'])
print("Segments received:", stats['received'])
print("Transmission time:", env.now, "seconds")