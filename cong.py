
import simpy
import random

def generate(env, pending, total, size):
    for seq in range(1, total // size + 1):
        yield pending.put((seq, size))


def transmit(env, chan, pack, bandwidth, rtt, loss):
    yield env.timeout(pack[1] * 8 / (bandwidth * 1e6) + rtt / 2)
    if random.random() >= loss:
        yield chan.put(pack)


def timeout(env, ackchan, seq, attempt, attempts, inflight, rtt):
    yield env.timeout(max(2 * rtt, 0.1))
    if seq in inflight and attempts[seq] == attempt:
        yield ackchan.put(('LOSS', seq, 0))


def sender(env, pending, chan, ackchan, total, size,
           bandwidth, rtt, loss, initial_cwnd, algorithm):

    cwnd = initial_cwnd
    ssthresh = 16
    inflight = {}
    attempts = {}
    sent = 0
    retransmitted = 0
    acked = 0
    wmax = initial_cwnd
    last_loss = 0
    bw_est = 0
    min_rtt = rtt

    def receive_ack(env):
        nonlocal cwnd, ssthresh, retransmitted
        nonlocal acked, wmax, last_loss, bw_est, min_rtt

        while True:
            kind, seq, sample_rtt = yield ackchan.get()

            if kind == 'ACK' and seq in inflight:
                del inflight[seq]
                acked += 1
                min_rtt = min(min_rtt, sample_rtt)
                bw_est = max(bw_est, size * 8 / max(sample_rtt, 0.001))

                if algorithm == 'Reno':
                    if cwnd < ssthresh:
                        cwnd += 1
                    else:
                        cwnd += 1 / cwnd

                elif algorithm == 'CUBIC':
                    t = env.now - last_loss
                    k = (wmax * 0.3 / 0.4) ** (1 / 3)
                    cwnd = max(cwnd, wmax + 0.4 * (t - k) ** 3, 1)

                elif algorithm == 'BBR':
                    bdp = bw_est * min_rtt / (size * 8)
                    cwnd = max(cwnd + 0.1, min(2 * bdp, 1000))

            elif kind == 'LOSS' and seq in inflight:
                retransmitted += 1
                wmax = cwnd
                last_loss = env.now

                if algorithm == 'Reno':
                    ssthresh = max(cwnd / 2, 2)
                    cwnd = 1

                elif algorithm == 'CUBIC':
                    cwnd = max(1, cwnd * 0.7)

                # Simplified BBR does not halve cwnd on loss.

                attempts[seq] += 1
                inflight[seq] = env.now
                env.process(transmit(
                    env, chan, (seq, size, env.now),
                    bandwidth, rtt, loss))
                env.process(timeout(
                    env, ackchan, seq, attempts[seq],
                    attempts, inflight, rtt))

    env.process(receive_ack(env))

    for _ in range(total // size):
        seq, size = yield pending.get()

        while len(inflight) >= max(1, int(cwnd)):
            yield env.timeout(0.01)

        inflight[seq] = env.now
        attempts[seq] = 0
        sent += 1

        env.process(transmit(
            env, chan, (seq, size, env.now),
            bandwidth, rtt, loss))
        env.process(timeout(
            env, ackchan, seq, 0, attempts, inflight, rtt))

    while inflight:
        yield env.timeout(0.01)

    print("Algorithm:", algorithm)
    print("Packets sent:", sent)
    print("ACKs received:", acked)
    print("Retransmissions:", retransmitted)
    print("Final cwnd:", round(cwnd, 2))
    print("Estimated bandwidth (Mbps):", round(bw_est / 1e6, 2))
    print("Completion time (s):", round(env.now, 3))


def receiver(env, chan, ackchan, rtt):
    while True:
        seq, size, sent_at = yield chan.get()
        yield env.timeout(rtt / 2)
        yield ackchan.put(('ACK', seq, env.now - sent_at))


env = simpy.Environment()
pending = simpy.Store(env)
chan = simpy.Store(env)
ackchan = simpy.Store(env)

total = 1000000
size = 1000
bandwidth = 10
rtt = 0.02
loss = 0.02
initial_cwnd = 1
algorithm = input("Choose Reno, CUBIC, or BBR: ").upper()

if algorithm not in ('RENO', 'CUBIC', 'BBR'):
    raise ValueError("Invalid algorithm")

algorithm = algorithm.title()

env.process(generate(env, pending, total, size))
env.process(sender(
    env, pending, chan, ackchan, total, size,
    bandwidth, rtt, loss, initial_cwnd, algorithm))
env.process(receiver(env, chan, ackchan, rtt))

env.run()
