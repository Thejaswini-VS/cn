
import simpy
import random

CWMIN = 4
CWMAX = 16
SLOT = 0.001
TX_TIME = 0.01
TOTAL = 10

busy = False
stats = {'generated': 0, 'success': 0, 'collisions': 0,
         'retransmissions': 0}

def generate(env, name, channel):
    global busy

    for _ in range(20):
        yield env.timeout(random.expovariate(20))
        stats['generated'] += 1
        print(name, 'Packet generated at', round(env.now, 3))

        cw = CWMIN
        attempt = 0

        while attempt <= 4:
            print(name, 'Channel', 'BUSY' if busy else 'IDLE')
            backoff = random.randint(0, cw - 1)
            print(name, 'Backoff:', backoff, 'slots')

            while busy:
                yield env.timeout(SLOT)

            yield env.timeout(backoff * SLOT)

            if busy:
                stats['collisions'] += 1
                stats['retransmissions'] += 1
                attempt += 1
                cw = min(cw * 2, CWMAX)
                print(name, 'Collision! Retry:', attempt)
                continue

            busy = True
            channel.put(name)
            print(name, 'Transmission started')

            yield env.timeout(TX_TIME)

            busy = False
            channel.get()
            stats['success'] += 1
            print(name, 'Transmission successful')
            break

def run(env, channel):
    for i in range(5):
        env.process(generate(env, 'N' + str(i + 1), channel))

env = simpy.Environment()
channel = simpy.Store(env)

run(env, channel)
env.run(until=TOTAL)

print('\nGenerated:', stats['generated'])
print('Successful:', stats['success'])
print('Collisions:', stats['collisions'])
print('Retransmissions:', stats['retransmissions'])
