import copy
from utils import collections
from data_types import Dtc

def decode_dtc_code(code_bytes: bytes) -> str:
    """Convert 2 raw bytes to standard P/B/C/U-prefixed string."""
    high = code_bytes[0]
    family = ['P', 'C', 'B', 'U'][high >> 6]
    number = ((high & 0x3F) << 8) | code_bytes[1]
    return f'{family}{number:04X}'

def decode_dtc_status(status: int) -> list[str]:
    """Decode the status byte of a DTC to human readable"""
    # Other bit flags indicate historical issue
    flags = [
        (0, 'Active'),
        (2, 'Pending'),
        (3, 'Confirmed'),
        (7, 'MIL on'),
    ]
    results = []
    for bit, label in flags:
        if status & (1 << bit):
            results.append(label)
    # if no meaningful bit flags set to 'History'
    if not results:
        results.append('History')

    return results

def resolve_dtc_descriptions(dtcs, module):
    """Resolve DTC descriptions to their english names"""
    dtc_table = collections.get('dtc', {})
    module_dtcs = {}
    
    for module_dtc in module.dtcs:
        module_dtcs[module_dtc.header] = module_dtc.index
    
    for dtc in dtcs:
        if dtc.description is not None:
            continue 
        if dtc.header in module_dtcs:
            dtc.index = module_dtcs[dtc.header]
        try:
            dtc.description = dtc_table[dtc.index]
        # Try suffixed variants
        except (KeyError):
            for key, desc in dtc_table.items():
                if key.startswith(dtc.header + '-'):
                    dtc.description = desc
                    break
    return dtcs

def match_dtc(code: str, module) -> Dtc | None:
    """Find a Dtc in the module's list matching this code,
    handling base-vs-suffixed code matching."""
    for dtc in module.dtcs:
        if dtc.header == code:
            # Return a copy so live scan data won't bleed back onto the module's static definitions
            return copy.copy(dtc)
    return None