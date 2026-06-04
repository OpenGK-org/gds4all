import argparse
from utils import load_messages, load_collections
from data_types import Module
from connection import EcuConnection
from selection import select_ecu_element, set_prefilled_selects
from dtc import decode_dtc_status, resolve_dtc_descriptions

def load_arguments():
    parser = argparse.ArgumentParser(description='Scan DTCs from a Hyundai ECU')
    parser.add_argument('-i', '--interactive-select', nargs='*', help='Prefill selections with indices', type=int, metavar='N')
    parser.add_argument('-k', '--kia', help='Use KIA vehicles', action='store_true')
    parser.add_argument('--interface', default='can0', help='CAN interface name (default: can0)')
    return parser.parse_args()


def main():
    args = load_arguments()
    if args.interactive_select:
       set_prefilled_selects(args.interactive_select)

    print('Loading definitions...')
    load_messages('decrypted_xef/add-ENG.xml')
    load_messages('decrypted_xef/keyvalue.xml')
    load_messages('decrypted_xef/keyvalueUnit.xml')
    load_collections('decrypted_xef/dtc-ENG.xml')

    ecu_element = select_ecu_element(args.kia)
    if ecu_element is None:
        print('[!] Failed to load ECU definition')
        return

    module = Module.from_xml(ecu_element)

    print(f'\nConnecting to {module.system_id}...')
    connection = EcuConnection(module, interface=args.interface)
    try:
        connection.connect()
        print('Reading DTCs...')
        dtcs = connection.read_dtcs()
        dtcs_with_descriptions = resolve_dtc_descriptions(dtcs, module)
        print(f'\n{len(dtcs)} DTC(s) found:')
        for dtc in dtcs_with_descriptions:
            status_labels = decode_dtc_status(dtc.status) if dtc.status is not None else []
            status_str = ', '.join(status_labels) or 'Unknown'
            print(f'  {dtc.header}: {dtc.description or "(unknown code)"} ({status_str})')
        if dtcs:
            print('\nClear DTCs? [y/n]')
            if input().strip().lower() == 'y':
                try:
                    connection.clear_dtcs()
                    print('DTCs cleared')
                except RuntimeError as e:
                    print('Error: {}'.format(e))
        else:
            print('No DTCs detected')
    finally:
        connection.disconnect()

if __name__ == '__main__':
    main()