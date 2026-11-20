"""G3 probe programs. Peers and monitors do not share their instructions."""

from .encoded import Image, NO_PIN, STORES, assemble, lane_words


T, TX, RX, N, FLAG, FRAMES = range(6)
CS, CLK, MOSI, MISO, UART = range(5)
SCL, SDA = range(2)


def put(pin, bit, delay=0):
    return "out", 1 << pin, bit << pin, delay


def spi_code(arch, mode, starts):
    idle, late = divmod(mode, 2)
    phase0 = 1 - idle if late else idle
    lines = ["spi"]
    for start in starts:
        lines += [("set", T, start), ("call", "spi_word")]
    lines += [("halt",), "spi_word", ("set", TX, 0x964B), ("set", RX, 0)]

    base_delta = 16 + 30 * late
    if arch == "C":
        lines += [put(CS, 0), ("lane", 0, base_delta), ("add", T, base_delta),
                  ("add", T, 16 * 60)]
        descriptor = lane_words(period=60, count=16, clock=CLK, polarity=phase0, clock_phase=30,
                                serial=MOSI, tx=TX, sample=MISO, rx=RX, sample_phase=33)
    else:
        lines += [("set", N, 16), put(CS, 0), ("add", T, base_delta), "spi_bit",
                  ("shift_out", TX, MOSI, CLK, phase0, 0), put(CLK, 1 - phase0, 30),
                  ("cap", MISO, RX, 1, 33), ("add", T, 60), ("loop", N, "spi_bit")]
        descriptor = b""
    if not late:
        lines.append(put(CLK, idle))
    lines += [put(CS, 1, 8), ("fence", 9), ("report", 0, RX), ("ret",)]
    return lines, descriptor


def uart_code(arch):
    lines = ["uart", ("set", FRAMES, 3), "uart_next", ("wait", UART, 0, 0),
             ("set", RX, 0)]
    if arch == "C":
        lines += [("add", T, 521), ("lane", 0, 0), ("add", T, 8 * 521 + 260)]
        descriptor = lane_words(period=521, count=8, sample=UART, rx=RX, sample_phase=260, lsb=True)
    else:
        lines += [("set", N, 8), ("add", T, 781), "uart_bit", ("cap", UART, RX, 2, 0),
                  ("add", T, 521), ("loop", N, "uart_bit")]
        descriptor = b""
    return lines + [("cap", UART, FLAG, 0, 0), ("jnz", FLAG, "uart_good"),
                    ("report", 2, FLAG), ("halt",), "uart_good", ("report", 1, RX),
                    ("loop", FRAMES, "uart_next"), ("halt",)], descriptor


def i2c_code():
    lines = ["i2c", ("set", T, 16), ("call", "start")]
    for byte in (0xA0, 0x96, 0x4B):
        lines += [("set", TX, byte << 8), ("call", "write"), ("jnz", FLAG, "finish")]
    lines += [put(SDA, 1, 20), ("call", "rise"), ("add", T, 48), ("call", "start"),
              ("set", TX, 0xA1 << 8), ("call", "write"), ("jnz", FLAG, "finish"),
              ("call", "read"), put(SDA, 0, 20), ("call", "rise"), ("call", "fall"),
              ("call", "read"), put(SDA, 1, 20), ("call", "rise"), ("call", "fall"),
              ("report", 3, RX), "finish", ("call", "stop"), ("report", 4, FLAG), ("halt",),
              "start", put(SDA, 0), put(SCL, 0, 48), ("add", T, 48), ("ret",),
              "stop", put(SDA, 0, 20), ("call", "rise"), put(SDA, 1, 48), ("fence", 49), ("ret",),
              "rise", put(SCL, 1, 94), ("wait", SCL, 1, 94), ("ret",),
              "fall", put(SCL, 0, 56), ("add", T, 56), ("ret",),
              "write", ("set", N, 8), "write_bit", ("shift_out", TX, SDA, NO_PIN, 0, 20),
              ("call", "rise"), ("call", "fall"), ("loop", N, "write_bit"), put(SDA, 1, 20),
              ("call", "rise"), ("cap", SDA, FLAG, 0, 14), ("call", "fall"), ("ret",),
              "read", ("set", N, 8), "read_bit", put(SDA, 1, 20), ("call", "rise"),
              ("cap", SDA, RX, 1, 14), ("call", "fall"), ("loop", N, "read_bit"), ("ret",)]
    return lines, b""


def build(arch, profile, mode=0):
    if profile == "i2c":
        sources = [i2c_code()]
        names = ("i2c",)
    elif profile == "spi":
        sources = [spi_code(arch, mode, (32,))]
        names = ("spi",)
    elif profile == "overlap":
        sources = [uart_code(arch), spi_code(arch, mode, (360, 5550))]
        names = ("uart", "spi")
    else:
        raise ValueError(f"unknown image profile {profile}")

    width, depth = STORES[arch]
    if arch == "A":
        banks = tuple(assemble(lines, width, depth) for lines, _ in sources)
        code = tuple(binary for binary, _ in banks)
        entries = tuple(labels[name] for (_, labels), name in zip(banks, names))
    else:
        binary, labels = assemble([line for lines, _ in sources for line in lines], width, depth)
        code, entries = (binary,), tuple(labels[name] for name in names)
    image = Image(code, entries, tuple(bank for _, bank in sources))
    image.validate(arch)
    return image
