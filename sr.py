import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("localhost", 5000))
s.listen(1)

conn, addr = s.accept()

while True:
    data = conn.recv(1024).decode()

    if not data:
        break

    if data.startswith("F"):
        frame = int(data[1:])
        print("Received frame:", frame)
        conn.send(str(frame).encode())

    elif data.startswith("R"):
        frame = int(data[1:])
        print("Retransmitted frame:", frame)
        conn.send(str(frame).encode())

conn.close()
s.close()



import socket

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect(("localhost", 5000))

n = int(input("N: "))
size = int(input("Window size: "))
frames = list(map(int, input("Frames: ").split()))
lost = int(input("Lost frame: "))

base = 0
transmitted = []
retransmitted = []
alr = False

while base < n:
    end = min(base + size, n)

    for f in frames[base:end]:
        if f == lost and not alr:
            alr = True
            print("Frame lost:", f)
            continue

        cli.send(("F" + str(f)).encode())
        ack = cli.recv(1024).decode()
        print("ACK:", ack)
        transmitted.append(f)

    if alr:
        cli.send(("R" + str(lost)).encode())
        ack = cli.recv(1024).decode()
        print("Retransmitted ACK:", ack)
        retransmitted.append(lost)
        alr = False

    base = end

print("Transmitted:", transmitted)
print("Retransmitted:", retransmitted)

cli.close()



import simpy
import random

WINDOW_SIZE = 3
TOTAL_PACKETS = 6
TIMEOUT = 5
PACKET_DELAY = 1
LOSS_PROBABILITY = 0.2

def sender(env, channel, ack_channel):
    base = 1
    next_seq = 1
    acked = set()
    timers = {}

    while base <= TOTAL_PACKETS:
        while next_seq < base + WINDOW_SIZE and next_seq <= TOTAL_PACKETS:
            print(f"{env.now}: Sender sends packet {next_seq}")
            yield channel.put(next_seq)
            timers[next_seq] = env.process(packet_timer(env, next_seq))
            next_seq += 1

        ack_event = ack_channel.get()
        result = yield env.any_of([ack_event, *timers.values()])

        if ack_event in result:
            ack = result[ack_event]
            print(f"{env.now}: Sender receives ACK {ack}")
            acked.add(ack)

            if ack in timers:
                timers[ack].interrupt()
                del timers[ack]

            while base in acked:
                base += 1

        else:
            for seq, timer in list(timers.items()):
                if timer in result:
                    print(f"{env.now}: Timeout! Retransmitting packet {seq}")
                    yield channel.put(seq)
                    timers[seq] = env.process(packet_timer(env, seq))
                    break

def packet_timer(env, seq):
    yield env.timeout(TIMEOUT)

def receiver(env, channel, ack_channel):
    expected = 1
    received = set()

    while True:
        packet = yield channel.get()

        if packet is None:
            break

        if random.random() < LOSS_PROBABILITY:
            print(f"{env.now}: Packet {packet} is lost")
            continue

        yield env.timeout(PACKET_DELAY)

        if packet not in received:
            received.add(packet)
            print(f"{env.now}: Receiver accepts/buffers packet {packet}")

        while expected in received:
            expected += 1

        print(f"{env.now}: Receiver sends ACK {packet}")
        yield ack_channel.put(packet)

random.seed(7)

env = simpy.Environment()
data_channel = simpy.Store(env)
ack_channel = simpy.Store(env)

sender_process = env.process(sender(env, data_channel, ack_channel))
receiver_process = env.process(receiver(env, data_channel, ack_channel))

env.run(until=sender_process)
data_channel.put(None)
env.run(until=receiver_process)