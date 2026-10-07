import numpy as np

from osciviz.core.ring_buffer import RingBuffer


def block(start, n):
    values = np.arange(start, start + n, dtype=np.float32)
    return np.stack((values, -values), axis=1)


def test_latest_returns_newest_in_order():
    rb = RingBuffer(10)
    rb.write(block(0, 4))
    rb.write(block(4, 3))
    out = rb.latest(5)
    assert out[:, 0].tolist() == [2, 3, 4, 5, 6]
    assert out[:, 1].tolist() == [-2, -3, -4, -5, -6]


def test_wraparound():
    rb = RingBuffer(8)
    for i in range(0, 20, 3):
        rb.write(block(i, 3))
    assert rb.latest(8)[:, 0].tolist() == list(range(13, 21))
    assert rb.total_written == 21


def test_zero_padding_when_not_enough_data():
    rb = RingBuffer(8)
    rb.write(block(1, 2))
    assert rb.latest(4)[:, 0].tolist() == [0, 0, 1, 2]


def test_block_larger_than_capacity():
    rb = RingBuffer(4)
    rb.write(block(0, 10))
    assert rb.latest(4)[:, 0].tolist() == [6, 7, 8, 9]
