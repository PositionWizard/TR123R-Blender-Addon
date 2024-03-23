from struct import unpack

def read_uint32(file):
    """Reads value and return an unsigned int from 4 bytes."""
    return unpack('<I', file.read(4))[0] 

def read_uint32_tuple(file, n):
    """Read values and return a tuple of 'n' unsigned ints from 4 bytes each."""
    return unpack('<%dI' % n, file.read(4 * n))

def read_ushort16(file):
    """Read value and return an unsigned short from 2 bytes."""
    return unpack('<H', file.read(2))[0]

def read_ushort16_tuple(file, n):
    """Read values and return a tuple of 'n' unsigned shorts from 2 bytes each."""
    return unpack("<%sH" % n, file.read(2 * n))

def read_uint8_tuple(file, n):
    """Read values and return a tuple of 'n' unsigned chars from a byte each."""
    return unpack('<%dB' % n, file.read(n))