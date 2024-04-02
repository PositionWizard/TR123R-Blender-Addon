from struct import unpack
TRM_HEADER = 0x54524d02
TRM_FORMAT = '.TRM'
TRM_ANIM_FORMAT = '.TRMA'

def is_TRM_header(file) -> bool:
    """Reads first 4 bytes and returns bool whether they're a TRM header."""
    file.seek(0)
    return unpack('>I', file.read(4))[0] == TRM_HEADER

def read_float_tuple(file, size=1):
    """Reads value and return a tuple of 'size' of floats from 4 bytes each."""
    return unpack('<%df' % size, file.read(4 * size))

def read_int32(file):
    """Reads value and return an int from 4 bytes."""
    return unpack('<i', file.read(4))[0] 

def read_uint32(file):
    """Reads value and return an unsigned int from 4 bytes."""
    return unpack('<I', file.read(4))[0] 

def read_uint32_tuple(file, size=1):
    """Read values and return a tuple of 'size' unsigned ints from 4 bytes each."""
    return unpack('<%dI' % size, file.read(4 * size))

def read_ushort16(file):
    """Read value and return an unsigned short from 2 bytes."""
    return unpack('<H', file.read(2))[0]

def read_ushort16_tuple(file, size=1):
    """Read values and return a tuple of 'size' unsigned shorts from 2 bytes each."""
    return unpack("<%sH" % size, file.read(2 * size))

def read_uint8_tuple(file, size=1):
    """Read values and return a tuple of 'size' unsigned chars from a byte each."""
    return unpack('<%dB' % size, file.read(size))