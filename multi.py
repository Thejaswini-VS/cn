
import simpy
import random

nodes = {
    'W1': ('Wi-Fi', 100, 50e6, 0.02, 'W2'),
    'W2': ('Wi-Fi', 100, 50e6, 0.02, None),
    'B1': ('Bluetooth', 10, 2e6, 0.05, 'B2'),
    'B2': ('Bluetooth', 10, 2e6, 0.05, None),
    'Z1': ('Zigbee', 50, 250e3, 0.03, 'Z2'),
    'Z2': ('Zigbee', 50, 250e3, 0.03, None)
}

def generate(env, pending, source, dest, total, size, interval):
    for seq in range(1, total + 1):
        yield env.timeout(interval)
        yield pending.put((seq, source, dest, size, env.now))


def transmit(env, chan, pack, rate, loss):
    seq, src, dst, size, start = pack
    yield env.timeout(size * 8 / rate + random.uniform(0.005, 0.02))
    if random.random() >= loss:
        yield chan.put(pack)


def sender(env, pending, chan, rate, loss, distance, reach, stats):
    while True:
        pack = yield pending.get()
        stats['sent'] += 1

        if distance > reach:
            stats['lost'] += 1
            continue

        env.process(transmit(env, chan, pack, rate, loss))


def receiver(env, chan, stats):
    while True:
        seq, src, dst, size, start = yield chan.get()
        delay = env.now - start
        stats['received'] += 1
        stats['delay'] += delay
        print(src, '->', dst, 'Packet:', seq,
              'Delay:', round(delay * 1000, 2), 'ms')


def run(tech, source, dest, total, size, interval, distance):
    env = simpy.Environment()
    pending = simpy.Store(env)
    chan = simpy.Store(env)

    name, reach, rate, loss, _ = nodes[source]
    stats = {'sent': 0, 'received': 0, 'lost': 0, 'delay': 0}

    env.process(generate(env, pending, source, dest, total, size, interval))
    env.process(sender(env, pending, chan, rate, loss,
                       distance, reach, stats))
    env.process(receiver(env, chan, stats))

    env.run(until=total * interval + 1)

    stats['lost'] = stats['sent'] - stats['received']
    print('\nTechnology:', tech)
    print('Sent:', stats['sent'])
    print('Received:', stats['received'])
    print('Lost:', stats['lost'])
    print('Delivery Ratio:',
          round(stats['received'] / stats['sent'] * 100, 2), '%')

    if stats['received']:
        print('Average Delay:',
              round(stats['delay'] / stats['received'] * 1000, 2), 'ms')


run('Wi-Fi', 'W1', 'W2', 20, 1000, 0.2, 5)
run('Bluetooth', 'B1', 'B2', 15, 256, 0.5, 5)
run('Zigbee', 'Z1', 'Z2', 20, 100, 1, 5)
run('Bluetooth', 'B1', 'B2', 10, 256, 0.5, 25)
